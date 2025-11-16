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
)

# -------------------------------------------------------------------
# Profile serializer
# -------------------------------------------------------------------
class ProfileSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "id",
            "user",
            "avatar_url",
            "cover_url",
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

    def update(self, instance, validated_data):
        result = super().update(instance, validated_data)
        if any(k in validated_data for k in ("avatar_url", "headline", "bio")):
            try:
                instance.update_completion()
            except Exception:
                pass
        return result


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
    class Meta:
        model = AccountTier
        fields = "__all__"
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

    def validate(self, attrs):
        phone_raw = attrs.get("phone") or ""
        password = attrs.get("password") or ""
        country = (attrs.get("country") or "CM").upper()

        try:
            phone_e164 = to_e164(phone_raw, default_region=country)
        except Exception:
            raise serializers.ValidationError({"detail": _("Invalid phone number format.")})

        # Prefer passing a Django HttpRequest to auth backends
        req = self.context.get("request")
        if hasattr(req, "_request"):
            req = req._request

        # 1) Try E.164 (future-proof)
        user = authenticate(request=req, username=str(phone_e164), password=password)

        # 2) Legacy fallback (numbers saved without +country)
        if user is None:
            digits_only = ''.join(ch for ch in phone_raw if ch.isdigit())
            if digits_only and digits_only != phone_e164:
                user = authenticate(request=req, username=digits_only, password=password)

        if user is None:
            raise serializers.ValidationError({"detail": _("Invalid credentials.")})
        if not user.is_active:
            raise serializers.ValidationError({"detail": _("User account is disabled.")})

        attrs["user"] = user
        attrs["phone_e164"] = phone_e164
        return attrs