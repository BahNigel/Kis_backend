"""
Accounts views with JWT-based auth.

Changes:
- Register & Login now issue SimpleJWT tokens (access + refresh).
- Logout blacklists refresh (if blacklist app installed), else no-op 204.
- ViewSets authenticate via JWT (explicitly or via global settings).
"""

from typing import Optional
import os
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Sum
from django.contrib.auth import authenticate
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from apps.core.phone_utils import to_e164
from django.utils.translation import gettext_lazy as _
import pyotp

from rest_framework import viewsets, mixins, filters, status, serializers, permissions
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiResponse
)

# SimpleJWT
from rest_framework_simplejwt.authentication import JWTAuthentication
from .jwt_auth import DeviceBoundJWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    User,
    Profile,
    AccountTier,
    Subscription,
    Session,
    Device,
    TwoFactor,
    E2EDeviceKey,
    E2EPreKey,
    UsageQuota,
    AuditLog,
    Experience,
    Education,
    UserSkill,
    Project,
    Recommendation,
    ProfileFieldVisibility,
    ProfileArticle,
    ProfilePreferences,
    ProfileShowcase,
    # ApiToken,  # <- not used in JWT flow; keep your model if needed elsewhere
)

from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    ProfileSerializer,
    ProfileFieldVisibilitySerializer,
    ProfileArticleSerializer,
    ProfilePreferencesSerializer,
    ProfileShowcaseSerializer,
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
from apps.commerce.models import LoyaltyPoint
from apps.billing.models import WalletAccount, CreditAccount
from apps.billing.services import credits_to_cents

PROFILE_FIELD_KEYS = {
    "avatar",
    "cover",
    "headline",
    "bio",
    "industry",
    "contact_phone",
    "contact_email",
    "experience",
    "education",
    "projects",
    "skills",
    "recommendations",
    "articles",
    "activity",
}


def _can_view_field(owner: User, viewer: Optional[User], rule: Optional[ProfileFieldVisibility]) -> bool:
    if not rule:
        return True
    viewer_id = str(getattr(viewer, "id", ""))
    owner_id = str(owner.id)
    allow_list = set(str(v) for v in (rule.allow_user_ids or []))
    if viewer_id == owner_id:
        return True
    if rule.visibility == "public":
        return True
    if rule.visibility == "private":
        return False
    if rule.visibility in ("custom", "contacts"):
        return viewer_id in allow_list
    return False


def _resolve_media_url(request, file_field, fallback_url):
    if file_field:
        url = file_field.url
        return request.build_absolute_uri(url) if request else url
    return fallback_url


def _build_profile_payload(profile: Profile, viewer: Optional[User], request=None) -> dict:
    owner = profile.user
    rules = {
        item.field_key: item
        for item in ProfileFieldVisibility.objects.filter(user=owner)
        if item.field_key in PROFILE_FIELD_KEYS
    }

    def can_view(key: str) -> bool:
        return _can_view_field(owner, viewer, rules.get(key))

    def maybe(value, key: str):
        return value if can_view(key) else None

    experiences = []
    if can_view("experience"):
        experiences = ExperienceSerializer(Experience.objects.filter(user=owner), many=True).data

    educations = []
    if can_view("education"):
        educations = EducationSerializer(Education.objects.filter(user=owner), many=True).data

    skills = []
    if can_view("skills"):
        skills = UserSkillSerializer(UserSkill.objects.filter(user=owner), many=True).data

    projects = []
    if can_view("projects"):
        projects = ProjectSerializer(Project.objects.filter(user=owner), many=True).data

    recommendations = []
    if can_view("recommendations"):
        rec_qs = Recommendation.objects.filter(recommended_user=owner, approved=True)
        recommendations = RecommendationSerializer(rec_qs, many=True).data

    articles = []
    if can_view("articles"):
        article_qs = ProfileArticle.objects.filter(user=owner)
        if not viewer or viewer != owner:
            article_qs = article_qs.filter(status="published")
        articles = ProfileArticleSerializer(article_qs, many=True).data

    activity = []
    if can_view("activity"):
        activity_qs = AuditLog.objects.filter(actor_id=owner.id).order_by("-created_at")[:25]
        activity = [
            {
                "id": str(item.id),
                "action": item.action,
                "meta": item.meta,
                "created_at": item.created_at,
            }
            for item in activity_qs
        ]

    subscription = Subscription.objects.filter(user=owner, status="active").select_related("tier").first()
    tier = subscription.tier if subscription and subscription.tier else AccountTier.objects.filter(name__iexact=owner.tier).first()
    wallet = WalletAccount.objects.filter(user=owner).first()
    wallet_balance_cents = getattr(wallet, "balance_cents", 0)
    credit_account = CreditAccount.objects.filter(user=owner).first()
    credits_balance = getattr(credit_account, "credits", 0)
    credits_value_cents = credits_to_cents(credits_balance)
    points_total = LoyaltyPoint.objects.filter(user=owner).aggregate(total=Sum("points")).get("total") or 0

    preferences = ProfilePreferences.objects.filter(user=owner).first()
    preferences_data = ProfilePreferencesSerializer(preferences).data if preferences else None
    showcases = ProfileShowcase.objects.filter(user=owner).order_by("-created_at")
    showcases_data = ProfileShowcaseSerializer(showcases, many=True, context={"request": request}).data

    grouped_showcases = {}
    for item in showcases_data:
        grouped_showcases.setdefault(item["type"], []).append(item)

    account_payload = {
        "tier": AccountTierSerializer(tier).data if tier else None,
        "subscription": SubscriptionSerializer(subscription).data if subscription else None,
        "wallet_balance_cents": wallet_balance_cents,
        "credits": credits_balance,
        "credits_value_cents": credits_value_cents,
        "points": points_total,
    }

    if viewer and viewer != owner:
        account_payload = {
            "tier": AccountTierSerializer(tier).data if tier else None,
            "subscription": SubscriptionSerializer(subscription).data if subscription else None,
        }

    return {
        "user": {
            "id": owner.id,
            "display_name": owner.display_name,
            "avatar_url": maybe(
                _resolve_media_url(request, profile.avatar_file, profile.avatar_url),
                "avatar",
            ),
            "phone": maybe(owner.phone, "contact_phone"),
            "email": maybe(owner.email, "contact_email"),
        },
        "profile": {
            "id": profile.id,
            "avatar_url": maybe(
                _resolve_media_url(request, profile.avatar_file, profile.avatar_url),
                "avatar",
            ),
            "cover_url": maybe(
                _resolve_media_url(request, profile.cover_file, profile.cover_url),
                "cover",
            ),
            "headline": maybe(profile.headline, "headline"),
            "bio": maybe(profile.bio, "bio"),
            "industry": maybe(profile.industry, "industry"),
            "completion_score": profile.completion_score,
            "visibility": profile.visibility,
            "branding_prefs": profile.branding_prefs,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        },
        "sections": {
            "experiences": experiences,
            "educations": educations,
            "skills": skills,
            "projects": projects,
            "recommendations": recommendations,
            "articles": articles,
            "activity": activity,
            "showcases": grouped_showcases,
        },
        "stats": {
            "experiences": len(experiences),
            "educations": len(educations),
            "skills": len(skills),
            "projects": len(projects),
            "recommendations": len(recommendations),
            "articles": len(articles),
        },
        "preferences": preferences_data,
        "account": account_payload,
    }

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

def issue_tokens_for_user(user: User, device_id: Optional[str] = None) -> dict:
    refresh = RefreshToken.for_user(user)
    if device_id:
        refresh["device_id"] = device_id
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "token_type": "Bearer",
    }

def upsert_device(
    user: User,
    device_id: str,
    platform: Optional[str],
    name: Optional[str],
    request,
) -> Device:
    device, _ = Device.objects.update_or_create(
        user=user,
        device_id=str(device_id),
        defaults={
            "platform": platform or "unknown",
            "name": name or None,
            "last_seen_at": timezone.now(),
            "last_ip": request.META.get("REMOTE_ADDR") if request else None,
            "user_agent": request.META.get("HTTP_USER_AGENT") if request else None,
        },
    )
    return device


def get_or_create_totp(user: User) -> TwoFactor:
    tf, _ = TwoFactor.objects.get_or_create(
        user=user,
        type="totp",
        defaults={"enabled": False, "meta": {}},
    )
    meta = tf.meta or {}
    if not meta.get("secret"):
        meta["secret"] = pyotp.random_base32()
        meta["verified"] = False
        tf.meta = meta
        tf.save(update_fields=["meta", "updated_at"])
    return tf


def verify_totp(user: User, code: str) -> bool:
    tf = TwoFactor.objects.filter(user=user, type="totp", enabled=True).first()
    if not tf:
        return True
    secret = (tf.meta or {}).get("secret")
    if not secret:
        return False
    totp = pyotp.TOTP(secret)
    return bool(code) and totp.verify(code, valid_window=1)

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
        device_id = (request.data.get("device_id") or "").strip()
        device_platform = (request.data.get("device_platform") or "").strip()
        device_name = (request.data.get("device_name") or "").strip()
        if not device_id:
            return Response({"detail": "Device id is required."}, status=status.HTTP_400_BAD_REQUEST)

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

        upsert_device(user, device_id, device_platform or None, device_name or None, request)
        user_payload = UserSerializer(user, context={"request": request}).data
        tokens = issue_tokens_for_user(user, device_id=device_id)
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
        otp_code = (serializer.validated_data.get("otp_code") or "").strip()
        if TwoFactor.objects.filter(user=user, type="totp", enabled=True).exists():
            if not otp_code:
                return Response(
                    {"detail": "OTP required", "two_factor_required": True},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if not verify_totp(user, otp_code):
                return Response(
                    {"detail": "Invalid OTP", "two_factor_required": True},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        device_id = serializer.validated_data.get("device_id")
        device_platform = serializer.validated_data.get("device_platform") or None
        device_name = serializer.validated_data.get("device_name") or None
        upsert_device(user, device_id, device_platform, device_name, request)
        tokens = issue_tokens_for_user(user, device_id=device_id)  # should return {access, refresh} or similar

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
                    "device_id": device_id,
                    "two_factor_enabled": TwoFactor.objects.filter(user=user, type="totp", enabled=True).exists(),
                },
            },
            status=status.HTTP_200_OK,
        )
    

class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False)


class TwoFactorCodeSerializer(serializers.Serializer):
    code = serializers.CharField(write_only=True)


class SignedPreKeySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    key = serializers.CharField()
    signature = serializers.CharField()


class PreKeySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    key = serializers.CharField()


class E2EERegisterSerializer(serializers.Serializer):
    device_id = serializers.CharField()
    identity_key = serializers.CharField()
    signed_prekey = SignedPreKeySerializer()
    prekeys = PreKeySerializer(many=True, required=False)
    registration_id = serializers.IntegerField(required=False)

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
    authentication_classes = (DeviceBoundJWTAuthentication,)
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


@extend_schema(
    summary="Start TOTP setup",
    description="Create or return a TOTP secret and provisioning URI.",
    tags=["Auth"],
)
class TwoFactorSetupView(APIView):
    authentication_classes = (DeviceBoundJWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        tf = get_or_create_totp(request.user)
        if tf.enabled:
            return Response({"enabled": True}, status=status.HTTP_200_OK)

        secret = (tf.meta or {}).get("secret")
        issuer = os.environ.get("TOTP_ISSUER", "KIS")
        label = request.user.phone or request.user.email or str(request.user.id)
        uri = pyotp.totp.TOTP(secret).provisioning_uri(name=label, issuer_name=issuer)

        return Response(
            {"enabled": False, "secret": secret, "provisioning_uri": uri},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    summary="Enable TOTP",
    request=TwoFactorCodeSerializer,
    tags=["Auth"],
)
class TwoFactorEnableView(APIView):
    authentication_classes = (DeviceBoundJWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        data = TwoFactorCodeSerializer(data=request.data or {})
        data.is_valid(raise_exception=True)
        code = data.validated_data["code"]

        tf = get_or_create_totp(request.user)
        secret = (tf.meta or {}).get("secret")
        if not secret:
            return Response({"detail": "Missing TOTP secret"}, status=status.HTTP_400_BAD_REQUEST)

        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            return Response({"detail": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        tf.enabled = True
        meta = tf.meta or {}
        meta["verified"] = True
        meta["enabled_at"] = timezone.now().isoformat()
        tf.meta = meta
        tf.save(update_fields=["enabled", "meta", "updated_at"])
        AuditLog.log(actor=request.user, action="2fa.enabled", meta={"type": "totp"})
        return Response({"enabled": True}, status=status.HTTP_200_OK)


@extend_schema(
    summary="Disable TOTP",
    request=TwoFactorCodeSerializer,
    tags=["Auth"],
)
class TwoFactorDisableView(APIView):
    authentication_classes = (DeviceBoundJWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        data = TwoFactorCodeSerializer(data=request.data or {})
        data.is_valid(raise_exception=True)
        code = data.validated_data["code"]

        tf = TwoFactor.objects.filter(user=request.user, type="totp").first()
        if not tf or not tf.enabled:
            return Response({"enabled": False}, status=status.HTTP_200_OK)

        secret = (tf.meta or {}).get("secret")
        if not secret:
            return Response({"detail": "Missing TOTP secret"}, status=status.HTTP_400_BAD_REQUEST)

        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            return Response({"detail": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        tf.enabled = False
        tf.meta = {"disabled_at": timezone.now().isoformat()}
        tf.save(update_fields=["enabled", "meta", "updated_at"])
        AuditLog.log(actor=request.user, action="2fa.disabled", meta={"type": "totp"})
        return Response({"enabled": False}, status=status.HTTP_200_OK)


@extend_schema(
    summary="Register E2EE keys for this device",
    request=E2EERegisterSerializer,
    tags=["Auth"],
)
class E2EERegisterKeysView(APIView):
    authentication_classes = (DeviceBoundJWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        data = E2EERegisterSerializer(data=request.data or {})
        data.is_valid(raise_exception=True)

        device_id = data.validated_data["device_id"]
        header_device_id = (
            request.headers.get("X-Device-Id")
            or request.headers.get("X-Device-ID")
            or request.headers.get("X-DeviceId")
        )
        if header_device_id and str(header_device_id) != str(device_id):
            return Response({"detail": "Device mismatch"}, status=status.HTTP_400_BAD_REQUEST)

        device, _ = Device.objects.get_or_create(
            user=request.user,
            device_id=str(device_id),
            defaults={
                "platform": "unknown",
                "last_seen_at": timezone.now(),
            },
        )

        signed = data.validated_data["signed_prekey"]
        registration_id = data.validated_data.get("registration_id")

        E2EDeviceKey.objects.update_or_create(
            user=request.user,
            device=device,
            defaults={
                "identity_key": data.validated_data["identity_key"],
                "signed_prekey_id": signed["id"],
                "signed_prekey": signed["key"],
                "signed_prekey_signature": signed["signature"],
                "registration_id": registration_id,
            },
        )

        prekeys = data.validated_data.get("prekeys") or []
        if prekeys:
            E2EPreKey.objects.filter(user=request.user, device=device).delete()
            E2EPreKey.objects.bulk_create(
                [
                    E2EPreKey(
                        user=request.user,
                        device=device,
                        prekey_id=item["id"],
                        prekey=item["key"],
                    )
                    for item in prekeys
                ]
            )

        AuditLog.log(actor=request.user, action="e2ee.keys.register", meta={"device_id": device_id})
        return Response({"ok": True}, status=status.HTTP_200_OK)


@extend_schema(
    summary="Fetch E2EE bundle for a user/device",
    tags=["Auth"],
)
class E2EEFetchBundleView(APIView):
    authentication_classes = (DeviceBoundJWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request, user_id: str):
        target = get_object_or_404(User, id=user_id)
        device_id = request.query_params.get("device_id")

        device_qs = Device.objects.filter(user=target)
        if device_id:
            device_qs = device_qs.filter(device_id=str(device_id))
        device = device_qs.order_by("-last_seen_at").first()
        if not device:
            return Response({"detail": "No device keys"}, status=status.HTTP_404_NOT_FOUND)

        key = E2EDeviceKey.objects.filter(user=target, device=device).first()
        if not key:
            return Response({"detail": "No keys registered"}, status=status.HTTP_404_NOT_FOUND)

        prekey = None
        with transaction.atomic():
            candidate = (
                E2EPreKey.objects.select_for_update()
                .filter(user=target, device=device, consumed_at__isnull=True)
                .order_by("created_at")
                .first()
            )
            if candidate:
                candidate.consumed_at = timezone.now()
                candidate.save(update_fields=["consumed_at", "updated_at"])
                prekey = {"id": candidate.prekey_id, "key": candidate.prekey}

        return Response(
            {
                "user_id": str(target.id),
                "device_id": device.device_id,
                "identity_key": key.identity_key,
                "signed_prekey": {
                    "id": key.signed_prekey_id,
                    "key": key.signed_prekey,
                    "signature": key.signed_prekey_signature,
                },
                "one_time_prekey": prekey,
                "registration_id": key.registration_id,
            },
            status=status.HTTP_200_OK,
        )

# -----------------------------
# Core viewsets with Swagger docs (JWT-protected)
# -----------------------------
# Option A (explicit): set JWTAuthentication on each viewset
JWT_AUTH = (DeviceBoundJWTAuthentication,)
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
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = [filters.SearchFilter]
    search_fields = ["headline", "bio", "industry"]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated], authentication_classes=JWT_AUTH)
    def me(self, request):
        profile = Profile.objects.select_related("user").get(user=request.user)
        payload = _build_profile_payload(profile, request.user, request=request)
        payload["privacy"] = ProfileFieldVisibilitySerializer(
            ProfileFieldVisibility.objects.filter(user=request.user), many=True
        ).data
        payload["tiers"] = AccountTierSerializer(AccountTier.objects.all(), many=True).data
        return Response(payload)

    @action(detail=True, methods=["get"], permission_classes=[permissions.AllowAny], authentication_classes=JWT_AUTH)
    def view(self, request, pk=None):
        profile = self.get_object()
        viewer = request.user if getattr(request.user, "is_authenticated", False) else None
        payload = _build_profile_payload(profile, viewer, request=request)
        return Response(payload)


@extend_schema_view(
    list=extend_schema(summary="List profile privacy rules"),
    retrieve=extend_schema(summary="Retrieve profile privacy rule"),
    create=extend_schema(summary="Create profile privacy rule"),
    update=extend_schema(summary="Update profile privacy rule"),
    partial_update=extend_schema(summary="Partially update profile privacy rule"),
    destroy=extend_schema(summary="Delete profile privacy rule"),
)
class ProfileFieldVisibilityViewSet(viewsets.ModelViewSet):
    queryset = ProfileFieldVisibility.objects.all()
    serializer_class = ProfileFieldVisibilitySerializer
    authentication_classes = JWT_AUTH
    permission_classes = (IsAuthenticated, IsOwnerOrReadOnly)

    def get_queryset(self):
        if getattr(self.request.user, "is_authenticated", False):
            return ProfileFieldVisibility.objects.filter(user=self.request.user)
        return ProfileFieldVisibility.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@extend_schema_view(
    list=extend_schema(summary="List profile articles"),
    retrieve=extend_schema(summary="Retrieve profile article"),
    create=extend_schema(summary="Create profile article"),
    update=extend_schema(summary="Update profile article"),
    partial_update=extend_schema(summary="Partially update profile article"),
    destroy=extend_schema(summary="Delete profile article"),
)
class ProfileArticleViewSet(viewsets.ModelViewSet):
    queryset = ProfileArticle.objects.all()
    serializer_class = ProfileArticleSerializer
    authentication_classes = JWT_AUTH
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    filter_backends = [filters.SearchFilter]
    search_fields = ["title", "summary", "body"]

    def get_queryset(self):
        user = getattr(self.request.user, "is_authenticated", False) and self.request.user or None
        qs = ProfileArticle.objects.all()
        if not user:
            return qs.filter(status="published", visibility="public")
        if self.action == "list":
            return qs.filter(user=user)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@extend_schema_view(
    list=extend_schema(summary="List profile preferences"),
    retrieve=extend_schema(summary="Retrieve profile preferences"),
    create=extend_schema(summary="Create profile preferences"),
    update=extend_schema(summary="Update profile preferences"),
    partial_update=extend_schema(summary="Partially update profile preferences"),
)
class ProfilePreferencesViewSet(viewsets.ModelViewSet):
    queryset = ProfilePreferences.objects.all()
    serializer_class = ProfilePreferencesSerializer
    authentication_classes = JWT_AUTH
    permission_classes = (IsAuthenticated, IsOwnerOrReadOnly)

    def get_queryset(self):
        if getattr(self.request.user, "is_authenticated", False):
            return ProfilePreferences.objects.filter(user=self.request.user)
        return ProfilePreferences.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated], authentication_classes=JWT_AUTH)
    def me(self, request):
        pref = ProfilePreferences.objects.filter(user=request.user).first()
        if not pref:
            pref = ProfilePreferences.objects.create(user=request.user)
        serializer = self.get_serializer(pref)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(summary="List profile showcases"),
    retrieve=extend_schema(summary="Retrieve profile showcase"),
    create=extend_schema(summary="Create profile showcase"),
    update=extend_schema(summary="Update profile showcase"),
    partial_update=extend_schema(summary="Partially update profile showcase"),
    destroy=extend_schema(summary="Delete profile showcase"),
)
class ProfileShowcaseViewSet(viewsets.ModelViewSet):
    queryset = ProfileShowcase.objects.all()
    serializer_class = ProfileShowcaseSerializer
    authentication_classes = JWT_AUTH
    permission_classes = (IsAuthenticated, IsOwnerOrReadOnly)
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["type"]

    def get_queryset(self):
        if getattr(self.request.user, "is_authenticated", False):
            return ProfileShowcase.objects.filter(user=self.request.user)
        return ProfileShowcase.objects.none()

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
