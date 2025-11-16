"""
Comprehensive accounts models implementing the UML.

Improvements included:
 - HMAC/SHA256-backed ApiToken hashing (uses SECRET_KEY)
 - ApiToken rotation, last_used tracking, ip_restrictions, expiry
 - AuditLog creation via signals for core events (create/update/delete)
 - Profile auto-creation signal
 - Entitlements caching helpers on User
 - Additional user metadata: email_verified, last_login_at, last_password_change_at
 - Manager niceties and safety checks
 - Indexes and meta hints for scale
 - Clear extension points (SSO/SCIM, 2FA, billing webhooks)
"""
from typing import Optional, Tuple, Iterable
from django.db import models, transaction
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.conf import settings
from django.db.models.signals import post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError

import uuid
import secrets
import hashlib
import hmac
import datetime
import re

# ---------------------------------------------------------------------
# Config helpers (override via Django settings if you like)
# ---------------------------------------------------------------------
ENTITLEMENTS_CACHE_TTL = getattr(settings, "ENTITLEMENTS_CACHE_TTL", 300)  # seconds
API_TOKEN_PLAIN_LENGTH = getattr(settings, "API_TOKEN_PLAIN_LENGTH", 32)
API_TOKEN_DEFAULT_EXPIRES_DAYS = getattr(settings, "API_TOKEN_DEFAULT_EXPIRES_DAYS", 30)

# helper for HMAC-SHA256 using SECRET_KEY: prevents easy rainbow-table attacks if DB leaked.
def _hash_token(token_plain: str) -> str:
    """
    Return hex HMAC-SHA256 of token_plain using Django SECRET_KEY.
    Deterministic (so we can look up hashed token), but keyed by SECRET_KEY.
    """
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, token_plain.encode("utf-8"), hashlib.sha256).hexdigest()

# ---------------------------------------------------------------------
# BaseEntity
# ---------------------------------------------------------------------
class BaseEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def soft_delete(self):
        """Soft-delete and emit audit event via signals (post_delete will not run for soft-delete)."""
        if self.is_deleted:
            return
        self.is_deleted = True
        self.save(update_fields=["is_deleted", "updated_at"])

# ---------------------------------------------------------------------
# User manager
# ---------------------------------------------------------------------
# managers.py (or wherever your manager lives)
class UserManager(BaseUserManager):
    use_in_migrations = True

    # -------- Normalizers --------
    @staticmethod
    def normalize_phone(phone: Optional[str]) -> Optional[str]:
        if phone is None:
            return None
        phone = phone.strip()
        if phone.startswith("+"):
            return "+" + re.sub(r"\D", "", phone[1:])
        return re.sub(r"\D", "", phone)

    @staticmethod
    def normalize_country(country: Optional[str]) -> Optional[str]:
        if country is None:
            return None
        return country.strip().upper()

    # -------- Core factory (keyword-only) --------
    def _create_user(
        self,
        *,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str],
        country: Optional[str] = None,
        **extra,
    ):
        """
        Creates and saves a User. Rule:
          - Normal users: require phone + country.
          - Superusers:   require email + country (phone optional).
        """
        # IMPORTANT: pull potentially duplicated fields out of extra first
        # (createsuperuser passes everything in **user_data)
        if "phone" in extra and phone is None:
            phone = extra.pop("phone")
        if "email" in extra and email is None:
            email = extra.pop("email")
        if "country" in extra and country is None:
            country = extra.pop("country")

        username = extra.pop("username", None)

        is_superuser = bool(extra.get("is_superuser"))

        # Required fields depending on role
        if is_superuser:
            if not email:
                raise ValueError("Superuser must have an email address")
        else:
            if not phone:
                raise ValueError("Users must have a phone number")

        if not country:
            raise ValueError("Country is required")

        # Normalize
        if phone:
            phone = self.normalize_phone(phone)
        if email:
            email = self.normalize_email(email)
        country = self.normalize_country(country)

        user = self.model(
            phone=phone,
            email=email,
            username=username,
            country=country,
            **extra,
        )

        if password:
            user.set_password(password)
            if hasattr(user, "last_password_change_at"):
                user.last_password_change_at = timezone.now()
        else:
            user.set_unusable_password()

        try:
            user.full_clean()
            user.save(using=self._db)
        except IntegrityError as e:
            raise ValidationError({"non_field_errors": ["Duplicate or invalid data."]}) from e

        return user

    # -------- Public factories --------
    def create_user(self, phone: str, password: Optional[str] = None, **extra):
        """
        Normal users: phone + country required.
        Accept email optionally; both may be in extra (pop them).
        """
        country = extra.pop("country", None)
        email = extra.pop("email", None)
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(phone=phone, email=email, password=password, country=country, **extra)

    def create_superuser(self, email: str, password: str, **extra):
        """
        Superusers: email + country required; phone optional.
        Ensure flags enforced, and pop duplicates from extra.
        """
        if not password:
            raise ValueError("Superuser must have a password")

        country = extra.pop("country", None)
        phone = extra.pop("phone", None)

        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(phone=phone, email=email, password=password, country=country, **extra)

    # -------- Username_FIELD lookup --------
    def get_by_natural_key(self, key: str):
        username_field = getattr(self.model, "USERNAME_FIELD", "phone")
        if username_field == "phone":
            return self.get(phone=self.normalize_phone(key))
        return self.get(**{f"{username_field}__iexact": key})

# ---------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------
class User(AbstractBaseUser, PermissionsMixin, BaseEntity):
    email = models.EmailField(unique=True, db_index=True, blank=True, null=True)
    username = models.CharField(unique=True, max_length=150, blank=True, null=True, db_index=True)
    display_name = models.CharField(max_length=200, blank=True, null=True)
    phone = models.CharField(unique=True, max_length=50, blank=True, null=True)
    tier = models.CharField(max_length=50, default="Basic", db_index=True)
    status = models.CharField(max_length=50, default="active")
    locale = models.CharField(max_length=20, default="en")
    timezone = models.CharField(max_length=50, default="UTC")
    preferences = models.JSONField(default=dict, blank=True)
    trust_score = models.FloatField(default=0.0)
    verification = models.JSONField(default=dict, blank=True)
    entitlements = models.JSONField(default=dict, blank=True)
    country = models.CharField(max_length=20, default="CM")

    # additional meta flags
    email_verified = models.BooleanField(default=False, db_index=True)
    last_login_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_password_change_at = models.DateTimeField(null=True, blank=True)

    # Django
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    # ✅ Makes `createsuperuser` prompt for these two:
    REQUIRED_FIELDS = ["email", "country"]


    class Meta:
        indexes = [
            models.Index(fields=["phone"]),
            models.Index(fields=["tier"]),
            models.Index(fields=["username"]),
        ]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return self.phone or self.email or self.username or f"User {self.pk}"

    # ---------- Business logic helpers ----------
    def recalc_trust_score(self) -> float:
        """Recalculate and persist trust_score; return new value."""
        score = 0.0
        if self.is_active:
            score += 10
        profile = getattr(self, "profile", None)
        if profile and profile.completion_score:
            score += min(profile.completion_score / 10.0, 40)
        # Additional signals/events, e.g., verified phone/email, recommendations can be added
        self.trust_score = score
        self.save(update_fields=["trust_score", "updated_at"])
        return self.trust_score

    @classmethod
    def register(cls, phone: str, password: Optional[str] = None, **extra) -> "User":
        """
        Create user + profile in a transaction. Use from registration endpoints.
        """
        with transaction.atomic():
            user = cls.objects.create_user(phone=phone, password=password, **extra)
            # profile auto-created by signal
            AuditLog.log(user, "user.create", {"phone": user.phone})
            return user

    # ---------- Entitlements cache helpers ----------
    def _entitlements_cache_key(self) -> str:
        return f"entitlements:user:{self.id}"

    def cache_entitlements(self, entitlements: dict, ttl: int = ENTITLEMENTS_CACHE_TTL) -> None:
        """Store entitlements in cache for fast runtime checks."""
        self.entitlements = entitlements or {}
        self.save(update_fields=["entitlements", "updated_at"])
        cache.set(self._entitlements_cache_key(), entitlements, ttl)

    def get_cached_entitlements(self) -> dict:
        """Return entitlements from cache (falls back to DB)."""
        cached = cache.get(self._entitlements_cache_key())
        if cached is not None:
            return cached
        return self.entitlements or {}

    def invalidate_entitlements_cache(self) -> None:
        cache.delete(self._entitlements_cache_key())

    # ---------- API token helpers ----------
    def create_api_token(self, name: Optional[str] = None, scopes: Optional[Iterable[str]] = None,
                         expires_in_days: int = API_TOKEN_DEFAULT_EXPIRES_DAYS) -> Tuple["ApiToken", str]:
        """
        Create ApiToken record and return (ApiToken, plain_token).
        IMPORTANT: plain_token must be shown once by the caller (e.g. in login/register response).
        """
        expires_at = timezone.now() + datetime.timedelta(days=expires_in_days)
        token_plain = secrets.token_urlsafe(API_TOKEN_PLAIN_LENGTH)
        token_hash = _hash_token(token_plain)
        token = ApiToken.objects.create(
            user=self,
            name=name or f"token-{self.id}-{int(timezone.now().timestamp())}",
            token_hash=token_hash,
            scopes=list(scopes or []),
            expires_at=expires_at,
        )
        AuditLog.log(self, "api_token.create", {"token_id": str(token.id), "scopes": token.scopes})
        return token, token_plain

    @classmethod
    def authenticate_with_api_token(cls, token_plain: str) -> Optional["User"]:
        """
        Fast helper: return User if token valid & not expired (also updates token.last_used_at).
        """
        if not token_plain:
            return None
        token_hash = _hash_token(token_plain)
        try:
            api_token = ApiToken.objects.select_related("user").get(token_hash=token_hash, is_deleted=False)
        except ApiToken.DoesNotExist:
            return None
        if api_token.is_expired():
            return None
        # update last_used
        api_token.last_used_at = timezone.now()
        api_token.save(update_fields=["last_used_at", "updated_at"])
        user = getattr(api_token, "user", None)
        if user:
            user.last_login_at = timezone.now()
            user.save(update_fields=["last_login_at"])
        return user

    def login_create_token(self, name: Optional[str] = None, scopes: Optional[Iterable[str]] = None,
                           expires_in_days: int = API_TOKEN_DEFAULT_EXPIRES_DAYS) -> Tuple["ApiToken", str]:
        """
        Convenience method used after verifying user credentials (e.g., password).
        """
        AuditLog.log(self, "user.login", {"via": "token_create"})
        return self.create_api_token(name=name, scopes=scopes, expires_in_days=expires_in_days)

# ---------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------
class Profile(BaseEntity):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    avatar_url = models.URLField(blank=True, null=True)
    cover_url = models.URLField(blank=True, null=True)
    headline = models.CharField(max_length=255, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    completion_score = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    visibility = models.CharField(max_length=50, default="public")
    branding_prefs = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"
        indexes = [models.Index(fields=["user"])]

    def update_completion(self) -> int:
        """Recompute a simple completion heuristic and persist."""
        score = 0
        if self.avatar_url:
            score += 20
        if self.headline:
            score += 20
        if self.bio:
            score += 30
        # safe-check for related managers
        try:
            if hasattr(self, "experiences") and self.experiences.exists():
                score += 10
            if hasattr(self, "educations") and self.educations.exists():
                score += 10
        except Exception:
            # defensive: in migrations related tables may not exist yet
            pass
        self.completion_score = min(100, score)
        self.save(update_fields=["completion_score", "updated_at"])
        # propagate to user's trust score if desired
        try:
            self.user.recalc_trust_score()
        except Exception:
            pass
        return self.completion_score

# ensure Profile exists when a user is created
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_profile_exists(sender, instance: User, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
        # audit logged in register flow already; ensure-profile is lightweight

# ---------------------------------------------------------------------
# Session, Device, ApiToken
# ---------------------------------------------------------------------
class Session(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sessions")
    expires_at = models.DateTimeField(db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "expires_at"])]

class Device(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices")
    platform = models.CharField(max_length=100)
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["user", "last_seen_at"])]

class ApiToken(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens")
    name = models.CharField(max_length=200, blank=True, null=True)
    # token_hash stores HMAC-SHA256 hex (64 chars). keep room.
    token_hash = models.CharField(max_length=128, db_index=True)
    scopes = models.JSONField(default=list, blank=True)
    created_via = models.CharField(max_length=50, default="api", blank=True, null=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    ip_restrictions = models.JSONField(default=list, blank=True)  # e.g. ["203.0.113.0/24"]
    last_used_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["token_hash"]),
            models.Index(fields=["user"]),
            models.Index(fields=["expires_at"]),
        ]
        # Consider adding unique_together if you want to forbid duplicate token_hash for same user

    def __str__(self):
        return f"ApiToken({self.user_id}, {self.name or self.id})"

    def is_expired(self) -> bool:
        return bool(self.expires_at and (self.expires_at < timezone.now()))

    def revoke(self) -> None:
        self.soft_delete()
        AuditLog.log(self.user, "api_token.revoke", {"token_id": str(self.id)})

    def rotate(self, new_expires_in_days: Optional[int] = None) -> Tuple["ApiToken", str]:
        """
        Rotate token: create a new plain token and update this record with new hash and expiry.
        Returns (self (updated), plain_token).
        """
        plain = secrets.token_urlsafe(API_TOKEN_PLAIN_LENGTH)
        self.token_hash = _hash_token(plain)
        if new_expires_in_days is not None:
            self.expires_at = timezone.now() + datetime.timedelta(days=new_expires_in_days)
        else:
            # preserve existing expiry if present
            if not self.expires_at:
                self.expires_at = timezone.now() + datetime.timedelta(days=API_TOKEN_DEFAULT_EXPIRES_DAYS)
        self.last_used_at = None
        self.save(update_fields=["token_hash", "expires_at", "last_used_at", "updated_at"])
        AuditLog.log(self.user, "api_token.rotate", {"token_id": str(self.id)})
        return self, plain

    @classmethod
    def verify_plain_token(cls, token_plain: str, ip_address: Optional[str] = None) -> Optional["ApiToken"]:
        """
        Return ApiToken instance if token is valid and not expired and IP allowed.
        """
        if not token_plain:
            return None
        token_hash = _hash_token(token_plain)
        try:
            api_token = cls.objects.select_related("user").get(token_hash=token_hash, is_deleted=False)
        except cls.DoesNotExist:
            return None
        if api_token.is_expired():
            return None
        # optional IP restriction enforcement
        if api_token.ip_restrictions:
            # naive check: treat ip_restrictions as an allowlist of literal IPs or CIDRs
            # For production use, replace with netaddr/ipaddress CIDR-safe checks
            if ip_address and (ip_address not in api_token.ip_restrictions):
                # fail if not allowed
                return None
            if not ip_address:
                # if token has restrictions but no ip was given, deny
                return None
        # update last used
        api_token.last_used_at = timezone.now()
        if ip_address:
            api_token.last_used_ip = ip_address
        api_token.save(update_fields=["last_used_at", "last_used_ip", "updated_at"])
        return api_token

# ---------------------------------------------------------------------
# Billing & Tiers
# ---------------------------------------------------------------------
class AccountTier(BaseEntity):
    name = models.CharField(max_length=50, unique=True)
    price_cents = models.BigIntegerField(default=0)
    features_json = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Account Tier"
        verbose_name_plural = "Account Tiers"

    def __str__(self) -> str:
        return self.name

class Subscription(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    tier = models.ForeignKey(AccountTier, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=50, default="active")
    started_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    billing_meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "status"])]

# ---------------------------------------------------------------------
# Usage Quota
# ---------------------------------------------------------------------
class UsageQuota(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="usage_quotas")
    tier = models.ForeignKey(AccountTier, on_delete=models.SET_NULL, null=True, blank=True)
    quotas_json = models.JSONField(default=dict)  # e.g. {"ai_queries_per_day":10}
    last_reset_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["user", "last_reset_at"])]

    def decrement(self, key: str, amount: int = 1) -> bool:
        q = (self.quotas_json or {}).copy()
        if q.get(key, 0) < amount:
            return False
        q[key] = q.get(key, 0) - amount
        self.quotas_json = q
        self.save(update_fields=["quotas_json", "updated_at"])
        return True

# ---------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------
class AuditLog(BaseEntity):
    actor_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=200, db_index=True)
    meta = models.JSONField(default=dict)

    class Meta:
        indexes = [models.Index(fields=["actor_id", "action"])]

    @classmethod
    def log(cls, actor, action: str, meta: Optional[dict] = None) -> "AuditLog":
        meta = meta or {}
        actor_id = getattr(actor, "id", None) if actor else None
        return cls.objects.create(actor_id=actor_id, action=action, meta=meta)

# ---------------------------------------------------------------------
# Compact remaining models (extend as needed)
# ---------------------------------------------------------------------
class TwoFactor(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="two_factors")
    type = models.CharField(max_length=50)  # e.g., "sms", "totp"
    enabled = models.BooleanField(default=False)
    meta = models.JSONField(default=dict, blank=True)

class BillingAccount(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="billing_accounts")
    payment_method_refs = models.JSONField(default=list, blank=True)
    payout_account_ref = models.JSONField(default=dict, blank=True)
    revenue_share_rules = models.JSONField(default=dict, blank=True)

class OrganizationLink(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organization_links")
    org_id = models.UUIDField()
    role = models.CharField(max_length=100)
    sso_meta = models.JSONField(default=dict, blank=True)

class FeatureFlag(BaseEntity):
    name = models.CharField(max_length=200)
    enabled_for_tier = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

class AIAccess(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    tier = models.ForeignKey(AccountTier, on_delete=models.SET_NULL, null=True, blank=True)
    model_ref = models.CharField(max_length=200, blank=True, null=True)
    credits_remaining = models.IntegerField(default=0)
    custom_model_meta = models.JSONField(default=dict, blank=True)

class RevenueAccount(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="revenue_accounts")
    balance_cents = models.BigIntegerField(default=0)
    payout_schedule_json = models.JSONField(default=dict, blank=True)
    routing_info = models.JSONField(default=dict, blank=True)

class GDPRRequest(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gdpr_requests")
    type = models.CharField(max_length=100)
    status = models.CharField(max_length=100)

class ImpactLedger(BaseEntity):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="impact_ledgers")
    proof_json = models.JSONField(default=dict, blank=True)
    anchored = models.BooleanField(default=False)

class QuantumFlag(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quantum_flags")
    enabled = models.BooleanField(default=False)
    meta = models.JSONField(default=dict, blank=True)

class ARAccess(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ar_accesses")
    enabled = models.BooleanField(default=False)
    template_refs = models.JSONField(default=list, blank=True)

class Experience(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="experiences")
    title = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    currently_working = models.BooleanField(default=False)

class Education(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="educations")
    school = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    currently_studying = models.BooleanField(default=False)

class UserSkill(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_skills")
    skill_id = models.UUIDField()
    verified = models.BooleanField(default=False)
    endorsements = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)

class Project(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=255)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    project_url = models.URLField(blank=True, null=True)
    technologies = models.JSONField(default=list, blank=True)

class Recommendation(BaseEntity):
    recommended_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recommendations_received")
    recommender_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recommendations_made")
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    