"""
Serializers for accounts app. Advanced validations, nested create/update and read-only protections.
"""
from rest_framework import serializers
from django.db import transaction
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.core.exceptions import ValidationError
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
    password = serializers.CharField(write_only=True, required=True)
    password2 = serializers.CharField(write_only=True, required=True)
    # username = serializers.CharField(required=False, allow_blank=True)
    display_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("email", "password", "password2", "display_name", "phone")

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password2"):
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        try:
            validate_password(attrs.get("password"))
        except ValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2", None) 
        raw_password = validated_data.pop("password")
        user = User.objects.create_user(password=raw_password, **validated_data)
        try:
            if not UsageQuota.objects.filter(user=user).exists():
                UsageQuota.objects.create(user=user, quotas_json={"ai_queries_per_day": 10}, last_reset_at=timezone.now())
        except Exception:
            pass
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

