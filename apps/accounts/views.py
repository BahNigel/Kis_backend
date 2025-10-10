"""
Complete views and urls for the accounts app with Swagger documentation.

This file contains:
 - DRF viewsets and APIViews that work with the provided models + serializers
 - Token authentication class (Authorization: Bearer <token>)
 - Owner permission helper for write operations
 - Router + urlpatterns registration for login/logout and all resources

Drop this file into your `accounts` app as `views.py`.
"""
from typing import Optional
from apps.accounts.authentication import ApiTokenDRFAuthentication
from rest_framework import viewsets, mixins, filters, status, serializers, permissions, authentication
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db import transaction
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse, OpenApiExample
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework.routers import DefaultRouter
from django.urls import path, include

from .models import (
    User,
    Profile,
    AccountTier,
    Subscription,
    Session,
    UsageQuota,
    AuditLog,
    ApiToken,
)

from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    ProfileSerializer,
    AccountTierSerializer,
    SubscriptionSerializer,
    SessionSerializer,
    ApiTokenListSerializer as ApiTokenListSerializerImported,
    ExperienceSerializer,
    EducationSerializer,
    UserSkillSerializer,
    ProjectSerializer,
    RecommendationSerializer,
)

import datetime

# -----------------------------
# Permissions
# -----------------------------
class IsOwnerOrReadOnly(permissions.BasePermission):
    """Allow full access to owners, read-only to others."""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "recommender_user", None) or getattr(obj, "owner", None)
        if owner is None:
            return False
        return owner == request.user

# -----------------------------
# Inline/simple serializers (token responses)
# -----------------------------
class PlainTokenSerializer(serializers.Serializer):
    token = serializers.CharField(read_only=True)
    token_type = serializers.CharField(default="Bearer", read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)

ApiTokenListSerializer = ApiTokenListSerializerImported

# -----------------------------
# Auth endpoints: Register/Login/Logout
# -----------------------------
@extend_schema_view(
    create=extend_schema(
        summary="Register a new account",
        description="Register a new user and return a one-time plain API token.",
        request=UserCreateSerializer,
        responses={201: OpenApiResponse(response=UserSerializer)},
        tags=["Auth", "Users"],
    )
)
class RegisterView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = (AllowAny,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = serializer.save()
            UsageQuota.objects.get_or_create(user=user, defaults={"quotas_json": {"ai_queries_per_day": 5}, "last_reset_at": timezone.now()})
            token_obj, plain = user.create_api_token(name="initial-token", scopes=["default"])
            AuditLog.log(actor=user, action="user.register", meta={"email": user.email, "token_id": str(token_obj.id)})
        resp = UserSerializer(user, context={"request": request}).data
        resp.update({"token": plain, "token_type": "Bearer", "expires_at": token_obj.expires_at})
        return Response(resp, status=status.HTTP_201_CREATED)

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    scopes = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        user = authenticate(username=email, password=password)
        if user is None:
            raise serializers.ValidationError("Invalid credentials")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled")
        attrs["user"] = user
        return attrs

@extend_schema(
    summary="Login (email + password) -> returns API token",
    request=LoginSerializer,
    responses={200: PlainTokenSerializer},
    tags=["Auth"]
)
class LoginView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        scopes = serializer.validated_data.get("scopes")
        with transaction.atomic():
            token_obj, plain = user.login_create_token(name="login-token", scopes=scopes or ["default"])
            AuditLog.log(actor=user, action="user.login", meta={"token_id": str(token_obj.id), "ip": request.META.get("REMOTE_ADDR")})
        return Response({"token": plain, "token_type": "Bearer", "expires_at": token_obj.expires_at})

@extend_schema(summary="Logout current API token", tags=["Auth"])
class LogoutView(APIView):
    authentication_classes = (ApiTokenDRFAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        api_token = getattr(request, "_api_token", None) or getattr(request, "auth", None)
        if isinstance(api_token, ApiToken):
            try:
                api_token.revoke()
                AuditLog.log(actor=request.user, action="user.logout", meta={"token_id": str(api_token.id)})
            except Exception:
                pass
        return Response(status=status.HTTP_204_NO_CONTENT)

# -----------------------------
# ApiToken management viewset
# -----------------------------
@extend_schema_view(
    list=extend_schema(summary="List API tokens for the authenticated user"),
    create=extend_schema(summary="Create a new API token"),
    revoke=extend_schema(summary="Revoke a token"),
    rotate=extend_schema(summary="Rotate an API token"),
)
class ApiTokenViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.CreateModelMixin):
    serializer_class = ApiTokenListSerializer
    authentication_classes = (ApiTokenDRFAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return ApiToken.objects.filter(user=self.request.user, is_deleted=False).order_by("-created_at")

    class CreateTokenSerializer(serializers.Serializer):
        name = serializers.CharField(required=False, allow_null=True)
        scopes = serializers.ListField(child=serializers.CharField(), required=False)
        expires_in_days = serializers.IntegerField(required=False, min_value=1)

    def create(self, request, *args, **kwargs):
        serializer = self.CreateTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_obj, plain = request.user.create_api_token(
            name=serializer.validated_data.get("name"),
            scopes=serializer.validated_data.get("scopes") or ["default"],
            expires_in_days=serializer.validated_data.get("expires_in_days")
        )
        AuditLog.log(actor=request.user, action="api_token.create", meta={"token_id": str(token_obj.id)})
        return Response({"token": plain, "token_type": "Bearer", "expires_at": token_obj.expires_at}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        token = get_object_or_404(self.get_queryset(), pk=pk)
        if token.user_id != request.user.id:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        token.revoke()
        AuditLog.log(actor=request.user, action="api_token.revoke", meta={"token_id": str(token.id)})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def rotate(self, request, pk=None):
        token = get_object_or_404(self.get_queryset(), pk=pk)
        if token.user_id != request.user.id:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        new_token_obj, plain = token.rotate(new_expires_in_days=None)
        AuditLog.log(actor=request.user, action="api_token.rotate", meta={"token_id": str(token.id)})
        return Response({"token": plain, "token_type": "Bearer", "expires_at": new_token_obj.expires_at})

# -----------------------------
# Core viewsets with Swagger docs
# -----------------------------
@extend_schema_view(
    list=extend_schema(summary="List users"),
    retrieve=extend_schema(summary="Retrieve user"),
    me=extend_schema(summary="Get current authenticated user"),
    recalc_trust=extend_schema(summary="Recalculate user's trust score")
)
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related("profile").all()
    serializer_class = UserSerializer
    authentication_classes = (ApiTokenDRFAuthentication,)
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["tier", "status"]
    search_fields = ["email", "display_name", "username"]
    ordering_fields = ["created_at", "trust_score"]

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def recalc_trust(self, request, pk=None):
        user = self.get_object()
        score = user.recalc_trust_score()
        return Response({"trust_score": score})

@extend_schema_view(
    list=extend_schema(summary="List profiles"),
    retrieve=extend_schema(summary="Retrieve profile"),
)
class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.select_related("user").all()
    serializer_class = ProfileSerializer
    authentication_classes = (ApiTokenDRFAuthentication,)
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    filter_backends = [filters.SearchFilter]
    search_fields = ["headline", "bio", "industry"]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

@extend_schema_view(
    list=extend_schema(summary="List account tiers"),
    retrieve=extend_schema(summary="Retrieve account tier"),
)
class AccountTierViewSet(viewsets.ModelViewSet):
    queryset = AccountTier.objects.all()
    serializer_class = AccountTierSerializer
    authentication_classes = (ApiTokenDRFAuthentication,)
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

@extend_schema_view(
    list=extend_schema(summary="List subscriptions"),
    retrieve=extend_schema(summary="Retrieve subscription"),
)
class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.select_related("user", "tier").all()
    serializer_class = SubscriptionSerializer
    authentication_classes = (ApiTokenDRFAuthentication,)
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["status", "tier"]

@extend_schema_view(
    list=extend_schema(summary="List sessions"),
    retrieve=extend_schema(summary="Retrieve session"),
)
class SessionViewSet(viewsets.ModelViewSet):
    queryset = Session.objects.all()
    serializer_class = SessionSerializer
    authentication_classes = (ApiTokenDRFAuthentication,)
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ["expires_at"]

# Experience / Education / Skill / Project / Recommendation viewsets
@extend_schema_view(
    list=extend_schema(summary="List experiences"),
    retrieve=extend_schema(summary="Retrieve experience"),
    create=extend_schema(summary="Create experience"),
    update=extend_schema(summary="Update experience"),
    partial_update=extend_schema(summary="Partially update experience"),
    destroy=extend_schema(summary="Delete experience"),
)
class ExperienceViewSet(viewsets.ModelViewSet):
    queryset = ExperienceSerializer.Meta.model.objects.all()
    serializer_class = ExperienceSerializer
    authentication_classes = (ApiTokenDRFAuthentication,)
    permission_classes = (IsOwnerOrReadOnly,)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

@extend_schema_view(
    list=extend_schema(summary="List educations"),
    retrieve=extend_schema(summary="Retrieve education"),
)
class EducationViewSet(viewsets.ModelViewSet):
    queryset = EducationSerializer.Meta.model.objects.all()
    serializer_class = EducationSerializer
    authentication_classes = (ApiTokenDRFAuthentication,)
    permission_classes = (IsOwnerOrReadOnly,)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

@extend_schema_view(
    list=extend_schema(summary="List user skills"),
    retrieve=extend_schema(summary="Retrieve user skill"),
)
class UserSkillViewSet(viewsets.ModelViewSet):
    queryset = UserSkillSerializer.Meta.model.objects.all()
    serializer_class = UserSkillSerializer
    authentication_classes = (ApiTokenDRFAuthentication,)
    permission_classes = (IsOwnerOrReadOnly,)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

@extend_schema_view(
    list=extend_schema(summary="List projects"),
    retrieve=extend_schema(summary="Retrieve project"),
)
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = ProjectSerializer.Meta.model.objects.all()
    serializer_class = ProjectSerializer
    authentication_classes = (ApiTokenDRFAuthentication,)
    permission_classes = (IsOwnerOrReadOnly,)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

@extend_schema_view(
    list=extend_schema(summary="List recommendations"),
    retrieve=extend_schema(summary="Retrieve recommendation"),
    create=extend_schema(summary="Create recommendation"),
    update=extend_schema(summary="Update recommendation"),
    partial_update=extend_schema(summary="Partially update recommendation"),
    destroy=extend_schema(summary="Delete recommendation"),
)
class RecommendationViewSet(viewsets.ModelViewSet):
    queryset = RecommendationSerializer.Meta.model.objects.all()
    serializer_class = RecommendationSerializer
    authentication_classes = (ApiTokenDRFAuthentication,)

    def get_permissions(self):
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsOwnerOrReadOnly()]
        return [permissions.IsAuthenticatedOrReadOnly()]

    def perform_create(self, serializer):
        serializer.save(recommender_user=self.request.user)
