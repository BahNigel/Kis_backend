"""
Accounts views with JWT-based auth.

Changes:
- Register & Login now issue SimpleJWT tokens (access + refresh).
- Logout blacklists refresh (if blacklist app installed), else no-op 204.
- ViewSets authenticate via JWT (explicitly or via global settings).
"""

from typing import Optional
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.contrib.auth import authenticate
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from apps.core.phone_utils import to_e164
from django.utils.translation import gettext_lazy as _

from rest_framework import viewsets, mixins, filters, status, serializers, permissions
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiResponse
)

# SimpleJWT
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    User,
    Profile,
    AccountTier,
    Subscription,
    Session,
    UsageQuota,
    AuditLog,
    # ApiToken,  # <- not used in JWT flow; keep your model if needed elsewhere
)

from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    ProfileSerializer,
    AccountTierSerializer,
    SubscriptionSerializer,
    SessionSerializer,
    ExperienceSerializer,
    EducationSerializer,
    UserSkillSerializer,
    ProjectSerializer,
    RecommendationSerializer,
    LoginSerializer,
)

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
# JWT helpers
# -----------------------------
class JWTTokensSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    token_type = serializers.CharField(default="Bearer", read_only=True)

def issue_tokens_for_user(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "token_type": "Bearer",
    }

# -----------------------------
# Auth endpoints: Register/Login/Logout (JWT)
# -----------------------------
@extend_schema_view(
    create=extend_schema(
        summary="Register a new account (returns JWT)",
        description="Create user and return access/refresh JWT tokens plus user payload.",
        request=UserCreateSerializer,
        responses={201: OpenApiResponse(response=UserSerializer)},
        tags=["Auth", "Users"],
    )
)
class RegisterView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        print(request.data)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                user = serializer.save()

                # Ensure a starting quota; avoids duplication with serializer (serializer no longer creates it)
                UsageQuota.objects.get_or_create(
                    user=user,
                    defaults={"quotas_json": {"ai_queries_per_day": 5}, "last_reset_at": timezone.now()},
                )

                AuditLog.log(actor=user, action="user.register", meta={"phone": user.phone, "country": user.country})
        except DRFValidationError:
            # Already well-formed for client
            raise
        except IntegrityError:
            # Fallback if something unique trips at DB-level unexpectedly
            raise DRFValidationError({"detail": "Duplicate or invalid data."})

        user_payload = UserSerializer(user, context={"request": request}).data
        tokens = issue_tokens_for_user(user)
        resp = {**user_payload, **tokens}
        return Response(resp, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Login (email + password) -> returns JWT",
    request=LoginSerializer,
    responses={200: JWTTokensSerializer},
    tags=["Auth"]
)
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        tokens = issue_tokens_for_user(user)  # should return {access, refresh} or similar

        # Optional bookkeeping
        AuditLog.log(actor=user, action="user.login",
                     meta={"ip": request.META.get("REMOTE_ADDR")})

        return Response(
            {
                "access": tokens.get("access"),
                "refresh": tokens.get("refresh"),
                "user": {
                    "id": user.id,
                    "phone": serializer.validated_data["phone_e164"],
                    "status": getattr(user, "status", "active"),
                    "is_active": user.is_active,
                },
            },
            status=status.HTTP_200_OK,
        )
    

class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False)

@extend_schema(
    summary="Logout (JWT)",
    description=(
        "If token blacklist is enabled, pass a refresh token to revoke it. "
        "Otherwise this endpoint simply returns 204 and clients should discard tokens."
    ),
    request=LogoutSerializer,
    tags=["Auth"],
)
class LogoutView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        data = LogoutSerializer(data=request.data or {})
        data.is_valid(raise_exception=False)
        refresh = data.validated_data.get("refresh")
        if refresh:
            try:
                token = RefreshToken(refresh)
                # Blacklist only works if 'rest_framework_simplejwt.token_blacklist' is installed
                token.blacklist()  # will no-op / raise if blacklist not configured
            except Exception:
                pass
        AuditLog.log(actor=request.user, action="user.logout", meta={})
        return Response(status=status.HTTP_204_NO_CONTENT)

# -----------------------------
# Core viewsets with Swagger docs (JWT-protected)
# -----------------------------
# Option A (explicit): set JWTAuthentication on each viewset
JWT_AUTH = (JWTAuthentication,)
IS_AUTH_OR_RO = (permissions.IsAuthenticatedOrReadOnly,)

@extend_schema_view(
    list=extend_schema(summary="List users"),
    retrieve=extend_schema(summary="Retrieve user"),
    me=extend_schema(summary="Get current authenticated user"),
    recalc_trust=extend_schema(summary="Recalculate user's trust score")
)
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related("profile").all()
    serializer_class = UserSerializer
    authentication_classes = JWT_AUTH
    permission_classes = IS_AUTH_OR_RO
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["tier", "status"]
    search_fields = ["email", "display_name", "username"]
    ordering_fields = ["created_at", "trust_score"]

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated], authentication_classes=JWT_AUTH)
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated], authentication_classes=JWT_AUTH)
    def recalc_trust(self, request, pk=None):
        user = self.get_object()
        score = user.recalc_trust_score()
        return Response({"trust_score": score})

    @action(
        detail=False,
        methods=["get"],
        url_path="check-status",
        permission_classes=[AllowAny],
        authentication_classes=[],
    )
    def check_status(self, request):
        phone = (request.query_params.get("phone") or "").strip()
        user = request.user if getattr(request.user, "is_authenticated", False) else None
        if not user and phone:
            user = User.objects.filter(phone=phone).first()

        if not user:
            return Response({"success": False, "message": "user not found"}, status=404)

        return Response(
            {
                "success": True,
                "user": {
                    "id": user.id,
                    "phone": user.phone,
                    "status": user.status,
                    "is_active": user.is_active,
                    "verification": user.verification,
                },
            },
            status=200,
        )
@extend_schema_view(
    list=extend_schema(summary="List profiles"),
    retrieve=extend_schema(summary="Retrieve profile"),
)
class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.select_related("user").all()
    serializer_class = ProfileSerializer
    authentication_classes = JWT_AUTH
    permission_classes = IS_AUTH_OR_RO
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
    authentication_classes = JWT_AUTH
    permission_classes = IS_AUTH_OR_RO
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

@extend_schema_view(
    list=extend_schema(summary="List subscriptions"),
    retrieve=extend_schema(summary="Retrieve subscription"),
)
class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.select_related("user", "tier").all()
    serializer_class = SubscriptionSerializer
    authentication_classes = JWT_AUTH
    permission_classes = IS_AUTH_OR_RO
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["status", "tier"]

@extend_schema_view(
    list=extend_schema(summary="List sessions"),
    retrieve=extend_schema(summary="Retrieve session"),
)
class SessionViewSet(viewsets.ModelViewSet):
    queryset = Session.objects.all()
    serializer_class = SessionSerializer
    authentication_classes = JWT_AUTH
    permission_classes = IS_AUTH_OR_RO
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ["expires_at"]

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
    authentication_classes = JWT_AUTH
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
    authentication_classes = JWT_AUTH
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
    authentication_classes = JWT_AUTH
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
    authentication_classes = JWT_AUTH
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
    authentication_classes = JWT_AUTH

    def get_permissions(self):
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsOwnerOrReadOnly()]
        return [permissions.IsAuthenticatedOrReadOnly()]

    def perform_create(self, serializer):
        serializer.save(recommender_user=self.request.user)

class CheckContact(APIView):
    """
    GET /api/v1/contacts/check?phone=+237676139884

    Headers:
      Authorization: Bearer <access_token>

    Response (example if user exists):
      {
        "registered": true,
        "userId": 7,
        "chatId": null   // you can wire 1–1 chat ID later if you like
      }

    If no user with that phone:
      {
        "registered": false
      }
    """
    authentication_classes = JWT_AUTH
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        phone = request.query_params.get("phone")
        print("now checking for the phone: ", phone)

        if not phone:
            return Response(
                {"detail": "phone is required"},
                status=400,
            )

        # Normalize if needed (e.g. strip spaces); your frontend already sends "+2376..."
        phone = phone.strip()

        # Look up any user with this phone
        user = User.objects.filter(phone=phone).first()

        if not user:
            # Not a KIS user
            return Response({"registered": False})

        # If you eventually create / fetch a 1-1 chat here, set chat_id accordingly
        chat_id = None

        return Response({
            "registered": True,
            "userId": user.id,
            "chatId": chat_id,
        })