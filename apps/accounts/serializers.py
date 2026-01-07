"""
Serializers for accounts app. Advanced validations, nested create/update and read-only protections.
"""
from rest_framework import serializers
from django.db import transaction
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import authenticate
from apps.core.phone_utils import to_e164
from django.utils.translation import gettext_lazy as _

import datetime

from .models import (
    User,
    Profile,
    AccountTier,
    Subscription,
    Session,
    UsageQuota,
    ApiToken,
    Experience,
    Education,
    UserSkill,
    Project,
    Recommendation,
    ProfileFieldVisibility,
    ProfileArticle,
    ProfilePreferences,
    ProfileShowcase,
)

# -------------------------------------------------------------------
# Profile serializer
# -------------------------------------------------------------------
class ProfileSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    avatar_file = serializers.ImageField(write_only=True, required=False, allow_null=True)
    cover_file = serializers.ImageField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Profile
        fields = [
            "id",
            "user",
            "avatar_url",
            "cover_url",
            "avatar_file",
            "cover_file",
            "headline",
            "bio",
            "industry",
            "completion_score",
            "visibility",
            "branding_prefs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "user", "completion_score", "created_at", "updated_at")

    def get_avatar_url(self, obj: Profile):
        if obj.avatar_file:
            request = self.context.get("request")
            url = obj.avatar_file.url
            return request.build_absolute_uri(url) if request else url
        return obj.avatar_url

    def get_cover_url(self, obj: Profile):
        if obj.cover_file:
            request = self.context.get("request")
            url = obj.cover_file.url
            return request.build_absolute_uri(url) if request else url
        return obj.cover_url

    def update(self, instance, validated_data):
        result = super().update(instance, validated_data)
        if any(k in validated_data for k in ("avatar_url", "avatar_file", "headline", "bio")):
            try:
                instance.update_completion()
            except Exception:
                pass
        return result


class ProfileFieldVisibilitySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ProfileFieldVisibility
        fields = [
            "id",
            "user",
            "field_key",
            "visibility",
            "allow_user_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "user", "created_at", "updated_at")

    def validate_allow_user_ids(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("allow_user_ids must be a list of user ids.")
        # basic sanity: cast everything to string
        return [str(item) for item in value if item]


class ProfileArticleSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ProfileArticle
        fields = [
            "id",
            "user",
            "title",
            "summary",
            "body",
            "cover_url",
            "tags",
            "status",
            "visibility",
            "allow_user_ids",
            "published_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "user", "published_at", "created_at", "updated_at")

    def validate_allow_user_ids(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("allow_user_ids must be a list of user ids.")
        return [str(item) for item in value if item]

    def create(self, validated_data):
        if self.context.get("request"):
            validated_data["user"] = self.context["request"].user
        if validated_data.get("status") == "published" and not validated_data.get("published_at"):
            validated_data["published_at"] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if validated_data.get("status") == "published" and not instance.published_at:
            validated_data["published_at"] = timezone.now()
        return super().update(instance, validated_data)


class ProfilePreferencesSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ProfilePreferences
        fields = [
            "id",
            "user",
            "services",
            "availability",
            "skill_badges",
            "languages",
            "location",
            "compensation",
            "social_proof",
            "ask_tags",
            "highlights",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "user", "created_at", "updated_at")


class ProfileShowcaseSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    file_url = serializers.SerializerMethodField()
    file = serializers.FileField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = ProfileShowcase
        fields = [
            "id",
            "user",
            "type",
            "title",
            "summary",
            "payload",
            "file",
            "file_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "user", "file_url", "created_at", "updated_at")

    def get_file_url(self, obj: ProfileShowcase):
        if not obj.file:
            return None
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    def create(self, validated_data):
        if self.context.get("request"):
            validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


# -------------------------------------------------------------------
# User serializers
# -------------------------------------------------------------------
class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        exclude = ("password", "is_superuser", "is_staff", "user_permissions", "groups")
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "trust_score",
            "last_login_at",
            "last_password_change_at",
            "email_verified",
        )


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, required=True, trim_whitespace=False)
    display_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=True, allow_blank=False)
    country = serializers.CharField(required=True, allow_blank=False)

    class Meta:
        model = User
        fields = ("password", "password2", "display_name", "phone", "country")

    def validate(self, attrs):
        # Passwords match
        if attrs.get("password") != attrs.get("password2"):
            raise serializers.ValidationError({"password": "Password fields didn't match."})

        # Basic phone presence/format guard (manager will normalize again)
        phone = attrs.get("phone", "").strip()
        if not phone:
            raise serializers.ValidationError({"phone": "Phone number is required."})
        if not (phone.startswith("+") or phone[0].isdigit()):
            raise serializers.ValidationError({"phone": "Invalid phone format. Use digits, optional leading '+'."})

        # Country required (keep free-form unless you enforce ISO codes)
        country = attrs.get("country", "").strip()
        if not country:
            raise serializers.ValidationError({"country": "Country is required."})

        # Built-in password validators
        from django.contrib.auth.password_validation import validate_password
        try:
            validate_password(attrs.get("password"))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})

        return attrs

    def create(self, validated_data):
        # Clean payload
        validated_data.pop("password2", None)
        raw_password = validated_data.pop("password")

        try:
            user = User.objects.create_user(password=raw_password, **validated_data)
        except DjangoValidationError as exc:
            # Surface model/manager level validation clearly
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        except IntegrityError:
            # Likely a unique conflict on phone (or username if you later add it)
            raise serializers.ValidationError({"phone": "A user with this phone already exists."})

        return user

# -------------------------------------------------------------------
# ApiToken serializers
# -------------------------------------------------------------------
class ApiTokenListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiToken
        fields = [
            "id",
            "name",
            "scopes",
            "created_at",
            "expires_at",
            "last_used_at",
            "last_used_ip",
        ]
        read_only_fields = fields


# -------------------------------------------------------------------
# Account tier, subscription, session serializers
# -------------------------------------------------------------------
class AccountTierSerializer(serializers.ModelSerializer):
    feature_list = serializers.SerializerMethodField()
    feature_tagline = serializers.SerializerMethodField()
    feature_badge = serializers.SerializerMethodField()
    feature_highlight = serializers.SerializerMethodField()

    def _tier_key(self, obj: AccountTier) -> str:
        return (obj.name or "").strip().lower()

    def _from_features_json(self, obj: AccountTier):
        features = obj.features_json or {}
        feature_list = features.get("feature_list") or features.get("features")
        if isinstance(feature_list, list):
            return {
                "feature_list": [str(x) for x in feature_list],
                "feature_tagline": features.get("feature_tagline"),
                "feature_badge": features.get("feature_badge"),
                "feature_highlight": features.get("feature_highlight"),
            }
        return None

    def _default_features(self, obj: AccountTier) -> dict:
        key = self._tier_key(obj)
        if "partner" in key:
            return {
                "feature_tagline": "Organizations, ministries & enterprises",
                "feature_badge": "Partner",
                "feature_highlight": "Multi-account orgs + revenue tools",
                "feature_list": [
                    "Verified organization profile",
                    "Multiple sub-accounts under one partner org",
                    "Org-level roles & permissions",
                    "Live streaming + events",
                    "Donations & revenue tools",
                    "Advanced analytics dashboard",
                    "Community & group management at scale",
                    "Priority support & onboarding",
                ],
            }
        if "business pro" in key:
            return {
                "feature_tagline": "High-impact teams and creators",
                "feature_badge": "Most popular",
                "feature_highlight": "Advanced analytics + team workflows",
                "feature_list": [
                    "Unlimited communities & groups",
                    "Team collaboration & admin roles",
                    "Advanced insights & reporting",
                    "Campaign scheduler & post boosting",
                    "CRM-lite lead capture",
                    "Branding controls & verification",
                    "Priority moderation tools",
                    "Faster support response",
                ],
            }
        if "business" in key:
            return {
                "feature_tagline": "Teams, growth & visibility",
                "feature_highlight": "KIS Business broadcast + storefront",
                "feature_list": [
                    "KIS Business broadcast channel",
                    "Business profile + CTA buttons",
                    "Multiple admins for business page",
                    "Business insights & audience metrics",
                    "Basic catalog for services/products",
                    "Promo codes + offers",
                    "Auto-reply & business hours",
                    "Featured discovery boost",
                ],
            }
        if "pro" in key:
            return {
                "feature_tagline": "Creators and power users",
                "feature_highlight": "Enhanced profile + higher limits",
                "feature_list": [
                    "More communities & groups",
                    "Enhanced profile visibility",
                    "Higher media limits",
                    "Advanced messaging tools",
                    "Priority search ranking",
                    "Extended support",
                    "Status & story enhancements",
                    "Custom themes",
                ],
            }
        return {
            "feature_tagline": "Start free, upgrade anytime",
            "feature_highlight": "Everything you need to begin",
            "feature_list": [
                "Direct messaging",
                "Core community access",
                "Standard profile",
                "Basic storage",
                "Search & discovery",
                "Standard support",
                "Status updates",
                "Basic groups",
            ],
        }

    def get_feature_list(self, obj: AccountTier):
        override = self._from_features_json(obj)
        if override and override.get("feature_list"):
            return override["feature_list"]
        return self._default_features(obj)["feature_list"]

    def get_feature_tagline(self, obj: AccountTier):
        override = self._from_features_json(obj)
        if override and override.get("feature_tagline"):
            return override["feature_tagline"]
        return self._default_features(obj).get("feature_tagline")

    def get_feature_badge(self, obj: AccountTier):
        override = self._from_features_json(obj)
        if override and override.get("feature_badge"):
            return override["feature_badge"]
        return self._default_features(obj).get("feature_badge")

    def get_feature_highlight(self, obj: AccountTier):
        override = self._from_features_json(obj)
        if override and override.get("feature_highlight"):
            return override["feature_highlight"]
        return self._default_features(obj).get("feature_highlight")

    class Meta:
        model = AccountTier
        fields = (
            "id",
            "name",
            "price_cents",
            "features_json",
            "feature_list",
            "feature_tagline",
            "feature_badge",
            "feature_highlight",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        if not attrs.get("user"):
            raise serializers.ValidationError({"user": "Subscription must be associated with a user."})
        if not attrs.get("tier"):
            raise serializers.ValidationError({"tier": "Subscription must reference an AccountTier."})
        return attrs


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")

    def create(self, validated_data):
        if not validated_data.get("expires_at"):
            validated_data["expires_at"] = timezone.now() + datetime.timedelta(days=30)
        return super().create(validated_data)


# -------------------------------------------------------------------
# Experience / Education / Skill / Project / Recommendation serializers
# -------------------------------------------------------------------
class ExperienceSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Experience
        fields = [
            "id", "user", "title", "description",
            "start_date", "end_date", "currently_working",
            "created_at", "updated_at",
        ]
        read_only_fields = ("id", "user", "created_at", "updated_at")

    def validate(self, attrs):
        if attrs.get("start_date") and attrs.get("end_date") and attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "end_date cannot be before start_date"})
        return attrs

    def create(self, validated_data):
        if self.context.get("request"):
            validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class EducationSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Education
        fields = [
            "id", "user", "school", "description",
            "start_date", "end_date", "currently_studying",
            "created_at", "updated_at",
        ]
        read_only_fields = ("id", "user", "created_at", "updated_at")

    def validate(self, attrs):
        if attrs.get("start_date") and attrs.get("end_date") and attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "end_date cannot be before start_date"})
        return attrs

    def create(self, validated_data):
        if self.context.get("request"):
            validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class UserSkillSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    endorsements = serializers.IntegerField(min_value=0, required=False)

    class Meta:
        model = UserSkill
        fields = [
            "id", "user", "skill_id", "verified",
            "endorsements", "description", "created_at", "updated_at",
        ]
        read_only_fields = ("id", "user", "created_at", "updated_at")

    def create(self, validated_data):
        if self.context.get("request"):
            validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class ProjectSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id", "user", "name", "description",
            "start_date", "end_date", "project_url", "technologies",
            "created_at", "updated_at",
        ]
        read_only_fields = ("id", "user", "created_at", "updated_at")

    def validate(self, attrs):
        if attrs.get("start_date") and attrs.get("end_date") and attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "end_date cannot be before start_date"})
        return attrs

    def create(self, validated_data):
        if self.context.get("request"):
            validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class RecommendationSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    recommended_user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    recommender_user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Recommendation
        fields = [
            "id", "recommended_user", "recommender_user",
            "content", "created_at", "updated_at", "approved",
        ]
        read_only_fields = ("id", "recommender_user", "created_at", "updated_at")

    def create(self, validated_data):
        if self.context.get("request"):
            validated_data["recommender_user"] = self.context["request"].user
        return super().create(validated_data)

class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    country = serializers.CharField(write_only=True, default="CM", required=False)
    device_id = serializers.CharField(write_only=True)
    device_platform = serializers.CharField(write_only=True, required=False, allow_blank=True)
    device_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    otp_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate(self, attrs):
        phone_raw = (attrs.get("phone") or "").strip()
        password = attrs.get("password") or ""
        country = (attrs.get("country") or "CM").upper()

        # Prefer passing a Django HttpRequest to auth backends
        req = self.context.get("request")
        if hasattr(req, "_request"):
            req = req._request

        if not phone_raw or not password:
            raise serializers.ValidationError({"detail": _("Phone and password are required.")})

        device_id = (attrs.get("device_id") or "").strip()
        if not device_id:
            raise serializers.ValidationError({"detail": _("Device id is required.")})

        # 1) Let the auth backend handle phone/email normalization.
        user = authenticate(request=req, username=phone_raw, password=password)

        # 2) Legacy fallback (numbers saved without +country or separators)
        if user is None:
            digits_only = ''.join(ch for ch in phone_raw if ch.isdigit())
            if digits_only and digits_only != phone_raw:
                user = authenticate(request=req, username=digits_only, password=password)

        # 3) E.164 fallback (for clients that send national digits + country)
        phone_e164 = None
        if user is None:
            try:
                phone_e164 = to_e164(phone_raw, default_region=country)
            except Exception:
                phone_e164 = None
            if phone_e164:
                user = authenticate(request=req, username=str(phone_e164), password=password)

        if user is None:
            raise serializers.ValidationError({"detail": _("Invalid credentials.")})
        if not user.is_active:
            raise serializers.ValidationError({"detail": _("User account is disabled.")})

        if not phone_e164:
            try:
                phone_e164 = to_e164(user.phone or phone_raw, default_region=(user.country or country))
            except Exception:
                phone_e164 = user.phone or phone_raw

        attrs["user"] = user
        attrs["phone_e164"] = phone_e164
        return attrs
