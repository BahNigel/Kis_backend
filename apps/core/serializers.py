# core/serializers.py
import uuid
from datetime import datetime
from typing import Any, Dict

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from rest_framework import serializers

from . import models

# Helper: default user model (accounts app provides it)
from django.conf import settings
UserModel = apps.get_model(settings.AUTH_USER_MODEL)


# ---------------------------
# GenericRelatedField
# ---------------------------
class GenericRelatedField(serializers.Field):
    """
    Serializes GenericForeignKey as:
      {"type": "app_label.ModelName", "id": "<pk>"}
    Accepts same structure for deserialization. If `allow_null=True` and value is null,
    returns None.

    Example:
      {"type":"accounts.User","id":"1234-..."}
    """
    def to_representation(self, value):
        if value is None:
            return None
        # value is model instance
        ct = ContentType.objects.get_for_model(value.__class__)
        return {"type": f"{ct.app_label}.{ct.model.capitalize()}", "id": str(getattr(value, "pk"))}

    def to_internal_value(self, data):
        # Accept None
        if data is None:
            return None

        if not isinstance(data, dict):
            raise serializers.ValidationError("Generic reference must be an object with 'type' and 'id'.")

        type_str = data.get("type")
        obj_id = data.get("id")

        if not type_str or not obj_id:
            raise serializers.ValidationError("Both 'type' and 'id' are required for generic references.")

        # type_str may be "app_label.ModelName" or "app_label.modelname"
        try:
            app_label, model_name = type_str.split(".", 1)
        except ValueError:
            raise serializers.ValidationError("Invalid 'type' format. Use 'app_label.ModelName'.")

        # normalize model name to lower for ContentType lookup
        ct = ContentType.objects.filter(app_label=app_label, model=model_name.lower()).first()
        if not ct:
            raise serializers.ValidationError(f"Unknown content type '{type_str}'.")

        model_class = ct.model_class()
        if model_class is None:
            raise serializers.ValidationError(f"Model class for '{type_str}' could not be resolved.")

        try:
            obj = model_class.objects.get(pk=obj_id)
        except ObjectDoesNotExist:
            raise serializers.ValidationError(f"Referenced object '{type_str}' with id '{obj_id}' not found.")

        return obj


# ---------------------------
# Short / Utilities serializers
# ---------------------------
class IDSerializer(serializers.Serializer):
    id = serializers.UUIDField()


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Permission
        fields = ["id", "codename", "description", "created_at", "updated_at"]


class RoleShortSerializer(serializers.ModelSerializer):
    permissions = serializers.SlugRelatedField(many=True, slug_field="codename", queryset=models.Permission.objects.all())

    class Meta:
        model = models.Role
        fields = ["id", "name", "scope", "is_default", "permissions"]


# ---------------------------
# RoleAssignment serializer
# ---------------------------
class RoleAssignmentSerializer(serializers.ModelSerializer):
    principal = GenericRelatedField(allow_null=False)
    target = GenericRelatedField(allow_null=True)

    role = serializers.PrimaryKeyRelatedField(queryset=models.Role.objects.all())

    class Meta:
        model = models.RoleAssignment
        fields = ["id", "role", "principal", "target", "expires_at", "created_at", "updated_at"]

    def create(self, validated_data):
        principal_obj = validated_data.pop("principal")
        target_obj = validated_data.pop("target", None)
        role = validated_data.pop("role")

        principal_ct = ContentType.objects.get_for_model(principal_obj.__class__)
        principal_id = str(getattr(principal_obj, "pk"))

        if target_obj is None:
            target_ct = None
            target_id = None
        else:
            target_ct = ContentType.objects.get_for_model(target_obj.__class__)
            target_id = str(getattr(target_obj, "pk"))

        ra = models.RoleAssignment.objects.create(
            role=role,
            principal_content_type=principal_ct,
            principal_object_id=principal_id,
            target_content_type=target_ct,
            target_object_id=target_id,
            expires_at=validated_data.get("expires_at"),
        )
        return ra

    def update(self, instance, validated_data):
        # allow changing expires_at and role, but not principal/target
        instance.role = validated_data.get("role", instance.role)
        instance.expires_at = validated_data.get("expires_at", instance.expires_at)
        instance.save()
        return instance


# ---------------------------
# AccessControlEntry serializer
# ---------------------------
class AccessControlEntrySerializer(serializers.ModelSerializer):
    principal = GenericRelatedField(allow_null=True)  # null + principal_object_id="PUBLIC" indicates public
    target = GenericRelatedField(allow_null=True)

    # allow permissions as list of strings
    permissions = serializers.ListField(child=serializers.CharField(), allow_empty=False)

    effect = serializers.ChoiceField(choices=models.AccessControlEntry.EFFECT_CHOICES)

    class Meta:
        model = models.AccessControlEntry
        fields = ["id", "principal", "target", "permissions", "effect", "expires_at", "created_at", "updated_at"]

    def to_internal_ace(self, validated_data):
        """
        Helper to build normalized ACE fields (content types and ids) from input.
        """
        principal_obj = validated_data.pop("principal", None)
        target_obj = validated_data.pop("target", None)
        permissions = validated_data.pop("permissions", [])
        effect = validated_data.pop("effect", models.AccessControlEntry.EFFECT_ALLOW)
        expires_at = validated_data.pop("expires_at", None)

        if principal_obj is None:
            principal_ct = None
            principal_id = "PUBLIC"
        else:
            principal_ct = ContentType.objects.get_for_model(principal_obj.__class__)
            principal_id = str(getattr(principal_obj, "pk"))

        if target_obj is None:
            target_ct = None
            target_id = None
        else:
            target_ct = ContentType.objects.get_for_model(target_obj.__class__)
            target_id = str(getattr(target_obj, "pk"))

        return {
            "principal_ct": principal_ct,
            "principal_id": principal_id,
            "target_ct": target_ct,
            "target_id": target_id,
            "permissions": sorted(set(map(str, permissions))),
            "effect": effect,
            "expires_at": expires_at,
        }

    def create(self, validated_data):
        ace_data = self.to_internal_ace(validated_data)
        ace = models.AccessControlEntry.objects.create(
            principal_content_type=ace_data["principal_ct"],
            principal_object_id=ace_data["principal_id"],
            target_content_type=ace_data["target_ct"],
            target_object_id=ace_data["target_id"],
            permissions=ace_data["permissions"],
            effect=ace_data["effect"],
            expires_at=ace_data["expires_at"],
        )
        return ace

    def update(self, instance, validated_data):
        ace_data = self.to_internal_ace(validated_data)
        instance.principal_content_type = ace_data["principal_ct"]
        instance.principal_object_id = ace_data["principal_id"]
        instance.target_content_type = ace_data["target_ct"]
        instance.target_object_id = ace_data["target_id"]
        instance.permissions = ace_data["permissions"]
        instance.effect = ace_data["effect"]
        instance.expires_at = ace_data["expires_at"]
        instance.save()
        return instance


# ---------------------------
# Community / Group / Channel serializers
# ---------------------------
class GroupSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GroupSettings
        exclude = ("id", "group", "created_at", "updated_at")


class ChannelSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ChannelSettings
        exclude = ("id", "channel", "created_at", "updated_at")


class MembershipShortSerializer(serializers.ModelSerializer):
    user = GenericRelatedField()
    role = RoleShortSerializer(read_only=True)

    class Meta:
        model = models.Membership
        fields = ["id", "user", "role", "status", "joined_at", "expires_at", "is_moderator"]


class CommunitySerializer(serializers.ModelSerializer):
    owner = GenericRelatedField(allow_null=True)
    metadata = serializers.JSONField(required=False)
    groups = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = models.Community
        fields = ["id", "slug", "name", "description", "owner", "visibility", "metadata", "archived", "groups", "created_at", "updated_at"]

    def create(self, validated_data):
        # owner is model instance from GenericRelatedField
        owner_obj = validated_data.pop("owner", None)
        if owner_obj is not None:
            owner_ct = ContentType.objects.get_for_model(owner_obj.__class__)
            owner_id = str(getattr(owner_obj, "pk"))
            validated_data["owner_content_type"] = owner_ct
            validated_data["owner_object_id"] = owner_id
        return super().create(validated_data)

    def update(self, instance, validated_data):
        owner_obj = validated_data.pop("owner", None) if "owner" in validated_data else None
        if owner_obj is not None:
            instance.owner_content_type = ContentType.objects.get_for_model(owner_obj.__class__)
            instance.owner_object_id = str(getattr(owner_obj, "pk"))
        return super().update(instance, validated_data)


class GroupSerializer(serializers.ModelSerializer):
    community = serializers.PrimaryKeyRelatedField(queryset=models.Community.objects.all(), allow_null=True, required=False)
    settings = GroupSettingsSerializer(read_only=True)
    memberships = MembershipShortSerializer(many=True, read_only=True)
    metadata = serializers.JSONField(required=False)

    class Meta:
        model = models.Group
        fields = [
            "id", "slug", "name", "description", "community", "is_public", "archived",
            "member_count", "metadata", "settings", "memberships", "created_at", "updated_at"
        ]
        read_only_fields = ["member_count", "settings", "memberships"]

    def create(self, validated_data):
        # create group + attach default GroupSettings if not provided
        with transaction.atomic():
            group = super().create(validated_data)
            # create default settings if not present
            if not hasattr(group, "settings"):
                models.GroupSettings.objects.create(group=group)
            return group

    def update(self, instance, validated_data):
        # normal update; settings managed via separate endpoint
        return super().update(instance, validated_data)


class ChannelSerializer(serializers.ModelSerializer):
    communities = serializers.PrimaryKeyRelatedField(queryset=models.Community.objects.all(), many=True, required=False)
    groups = serializers.PrimaryKeyRelatedField(queryset=models.Group.objects.all(), many=True, required=False)
    settings = ChannelSettingsSerializer(read_only=True)
    metadata = serializers.JSONField(required=False)

    class Meta:
        model = models.Channel
        fields = [
            "id", "slug", "name", "description", "is_public", "archived",
            "communities", "groups", "metadata", "settings", "created_at", "updated_at"
        ]
        read_only_fields = ["settings"]

    def create(self, validated_data):
        comms = validated_data.pop("communities", [])
        groups = validated_data.pop("groups", [])
        with transaction.atomic():
            ch = super().create(validated_data)
            if comms:
                ch.communities.set(comms)
            if groups:
                ch.groups.set(groups)
            # ensure settings exist
            if not hasattr(ch, "settings"):
                models.ChannelSettings.objects.create(channel=ch)
            return ch

    def update(self, instance, validated_data):
        comms = validated_data.pop("communities", None)
        groups = validated_data.pop("groups", None)
        with transaction.atomic():
            ch = super().update(instance, validated_data)
            if comms is not None:
                ch.communities.set(comms)
            if groups is not None:
                ch.groups.set(groups)
            return ch


# ---------------------------
# Membership-related serializers
# ---------------------------
class MembershipSerializer(serializers.ModelSerializer):
    user = GenericRelatedField()
    role = serializers.PrimaryKeyRelatedField(queryset=models.Role.objects.all(), allow_null=True, required=False)
    group = serializers.PrimaryKeyRelatedField(queryset=models.Group.objects.all())

    class Meta:
        model = models.Membership
        fields = [
            "id", "group", "user", "role", "status", "joined_at", "expires_at", "is_moderator", "preferences", "created_at", "updated_at"
        ]
        read_only_fields = ["joined_at", "created_at", "updated_at"]

    def validate(self, data):
        # If status is ACTIVE then joined_at must be set (it will be automatically)
        status = data.get("status", None)
        if status == models.Membership.STATUS_ACTIVE and not data.get("joined_at"):
            data["joined_at"] = timezone.now()
        return data

    def create(self, validated_data):
        user_obj = validated_data.pop("user")
        group = validated_data.get("group")
        role = validated_data.get("role", None)

        user_ct = ContentType.objects.get_for_model(user_obj.__class__)
        user_id = str(getattr(user_obj, "pk"))

        with transaction.atomic():
            # ensure unique membership constraint is respected by using get_or_create
            mem, created = models.Membership.objects.update_or_create(
                group=group,
                user_content_type=user_ct,
                user_object_id=user_id,
                defaults={
                    "role": role,
                    "status": validated_data.get("status", models.Membership.STATUS_ACTIVE),
                    "joined_at": validated_data.get("joined_at", timezone.now()),
                    "expires_at": validated_data.get("expires_at", None),
                    "is_moderator": validated_data.get("is_moderator", False),
                    "preferences": validated_data.get("preferences", {}),
                }
            )
            # update group's member_count
            group.recalc_member_count()
            return mem

    def update(self, instance, validated_data):
        # update membership fields; recalc group member_count if status changes
        prev_active = instance.is_active()
        instance.role = validated_data.get("role", instance.role)
        instance.status = validated_data.get("status", instance.status)
        instance.expires_at = validated_data.get("expires_at", instance.expires_at)
        instance.is_moderator = validated_data.get("is_moderator", instance.is_moderator)
        instance.preferences = validated_data.get("preferences", instance.preferences)
        instance.save()
        post_active = instance.is_active()
        if prev_active != post_active:
            instance.group.recalc_member_count()
        return instance


class MembershipInviteSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=models.Group.objects.all(), allow_null=True, required=False)
    community = serializers.PrimaryKeyRelatedField(queryset=models.Community.objects.all(), allow_null=True, required=False)
    created_by = GenericRelatedField(allow_null=True)

    class Meta:
        model = models.MembershipInvite
        fields = [
            "id", "token", "group", "community", "created_by", "expires_at", "max_uses", "uses", "created_at", "updated_at"
        ]
        read_only_fields = ["uses", "created_at", "updated_at", "token"]

    def validate(self, attrs):
        # must have either group or community (or neither for global invite) but not both simultaneously in some setups.
        if not attrs.get("group") and not attrs.get("community"):
            # allow global invites — you may prefer to require at least one
            pass
        # validate max_uses positive if provided
        max_uses = attrs.get("max_uses", None)
        if max_uses is not None and max_uses <= 0:
            raise serializers.ValidationError({"max_uses": "max_uses must be positive or null for unlimited."})
        return attrs

    def create(self, validated_data):
        # create token if not provided
        token = validated_data.get("token") or uuid.uuid4().hex
        created_by = validated_data.pop("created_by", None)
        if created_by is not None:
            cbt = ContentType.objects.get_for_model(created_by.__class__)
            created_by_ct = cbt
            created_by_id = str(getattr(created_by, "pk"))
        else:
            created_by_ct = None
            created_by_id = None

        invite = models.MembershipInvite.objects.create(
            token=token,
            group=validated_data.get("group", None),
            community=validated_data.get("community", None),
            created_by_content_type=created_by_ct,
            created_by_object_id=created_by_id,
            expires_at=validated_data.get("expires_at", None),
            max_uses=validated_data.get("max_uses", None),
        )
        return invite


class MembershipRequestSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=models.Group.objects.all())
    user = GenericRelatedField()
    reviewed_by = GenericRelatedField(allow_null=True, required=False)

    class Meta:
        model = models.MembershipRequest
        fields = [
            "id", "group", "user", "message", "status", "reviewed_by", "created_at"
        ]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        # ensure user not already member
        user_obj = attrs.get("user")
        group = attrs.get("group")
        user_ct = ContentType.objects.get_for_model(user_obj.__class__)
        exists = models.Membership.objects.filter(group=group, user_content_type=user_ct, user_object_id=str(getattr(user_obj, "pk"))).exists()
        if exists:
            raise serializers.ValidationError("User is already a member of the group.")
        return attrs

    def create(self, validated_data):
        return super().create(validated_data)


# ---------------------------
# ModerationAction serializer
# ---------------------------
class ModerationActionSerializer(serializers.ModelSerializer):
    target = GenericRelatedField()
    subject = GenericRelatedField()
    performed_by = GenericRelatedField(allow_null=True)

    class Meta:
        model = models.ModerationAction
        fields = [
            "id", "target", "subject", "action", "reason", "performed_by", "expires_at", "created_at", "updated_at"
        ]


# ---------------------------
# Settings serializers (update only)
# ---------------------------
class GroupSettingsUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GroupSettings
        fields = "__all__"
        read_only_fields = ("group", "id", "created_at", "updated_at")


class ChannelSettingsUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ChannelSettings
        fields = "__all__"
        read_only_fields = ("channel", "id", "created_at", "updated_at")


# ---------------------------
# Top-level convenient serializers for admin / read-heavy endpoints
# ---------------------------
class GroupDetailSerializer(GroupSerializer):
    # extend group serializer with nested data for detail endpoints
    community = CommunitySerializer(read_only=True)
    settings = GroupSettingsSerializer(read_only=True)
    memberships = MembershipShortSerializer(many=True, read_only=True)


class ChannelDetailSerializer(ChannelSerializer):
    communities = CommunitySerializer(many=True, read_only=True)
    groups = GroupSerializer(many=True, read_only=True)
    settings = ChannelSettingsSerializer(read_only=True)


# ---------------------------
# Final notes for use
# ---------------------------
"""
Notes & tips:
- GenericRelatedField expects the referenced object to exist. In most endpoints you'll pass:
    {"type":"accounts.User","id":"<user_pk>"}
  or for a role:
    {"type":"core.Role","id":"<role_uuid>"}

- For create endpoints you may prefer to accept simpler shapes for user references (e.g., user_id)
  — if so, make small wrapper serializers or override .to_internal_value to accept ints/uuids for
  specific content types such as accounts.User.

- Use separate endpoints for RoleAssignment and ACE management, and use the serializers above
  to validate/serialize data. Be sure to secure these endpoints heavily (only admins allowed).

- You can add view-level permission classes that call the domain object's `.can_user(user, permission)` methods
  before allowing create/update/delete operations.

"""
