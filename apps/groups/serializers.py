# apps/groups/serializers.py
from rest_framework import serializers

from apps.groups.models import (
    Group,
    GroupMembership,
    GroupJoinRequest,
    GroupBan,
    GroupRole,
)
from apps.accounts.models import User
from apps.chat.models import ConversationType
from apps.communities.models import CommunityMembership, CommunityRole


class GroupListSerializer(serializers.ModelSerializer):
    conversation_id = serializers.UUIDField(source="conversation.id", read_only=True)

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "slug",
            "is_archived",
            "partner",
            "community",
            "channel",
            "conversation_id",
            "created_at",
            "updated_at",
        ]


class GroupDetailSerializer(serializers.ModelSerializer):
    conversation_id = serializers.UUIDField(source="conversation.id", read_only=True)

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "slug",
            "partner",
            "community",
            "channel",
            "owner",
            "is_archived",
            "conversation_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "owner",
            "conversation_id",
            "created_at",
            "updated_at",
        ]


class GroupCreateSerializer(serializers.ModelSerializer):
    """
    For creating a Group.

    This ALWAYS:
      - creates a Conversation(type=GROUP),
      - creates ConversationMember for the owner with base_role=OWNER,
      - creates ConversationSettings for that conversation,
      - then creates the Group pointing to that conversation.
    """

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "slug",
            "partner",
            "community",
            "channel",
            "conversation_id",
        ]

    conversation_id = serializers.UUIDField(source="conversation.id", read_only=True)

    def validate(self, attrs):
        # You can add custom validation here (e.g. require partner or community)
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        from apps.chat.models import (
            Conversation,
            ConversationSettings,
            ConversationMember,
            BaseConversationRole,
        )

        # 1) Create Conversation of type GROUP for this group
        conversation = Conversation.objects.create(
            type=ConversationType.GROUP,
            title=validated_data.get("name", ""),
            created_by=user,
        )

        # 2) Add the creator as a member with OWNER role
        ConversationMember.objects.create(
            conversation=conversation,
            user=user,
            base_role=BaseConversationRole.OWNER,
        )

        # 3) Create default settings row for this conversation
        ConversationSettings.objects.create(conversation=conversation)

        # 4) Create the Group linked to this conversation
        group = Group.objects.create(
            owner=user,
            conversation=conversation,
            **validated_data,
        )

        GroupMembership.objects.create(
            group=group,
            user=user,
            role=GroupRole.OWNER,
        )

        if group.community_id:
            CommunityMembership.objects.update_or_create(
                community_id=group.community_id,
                user=user,
                defaults={"role": CommunityRole.MEMBER, "left_at": None, "is_banned": False},
            )
            community = group.community
            if community and community.main_conversation_id:
                ConversationMember.objects.get_or_create(
                    conversation=community.main_conversation,
                    user=user,
                    defaults={"base_role": BaseConversationRole.MEMBER},
                )
            if community and community.posts_conversation_id:
                ConversationMember.objects.get_or_create(
                    conversation=community.posts_conversation,
                    user=user,
                    defaults={"base_role": BaseConversationRole.MEMBER},
                )

        return group


class GroupUserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "display_name", "phone", "avatar_url"]

    def get_avatar_url(self, obj):
        profile = getattr(obj, "profile", None)
        return getattr(profile, "avatar_url", None) if profile else None


class GroupMembershipSerializer(serializers.ModelSerializer):
    user = GroupUserSerializer(read_only=True)

    class Meta:
        model = GroupMembership
        fields = [
            "id",
            "group",
            "user",
            "role",
            "joined_at",
            "left_at",
            "is_muted",
            "is_banned",
        ]
        read_only_fields = ["joined_at", "left_at", "is_banned"]


class GroupJoinRequestSerializer(serializers.ModelSerializer):
    user = GroupUserSerializer(read_only=True)
    reviewed_by = GroupUserSerializer(read_only=True)

    class Meta:
        model = GroupJoinRequest
        fields = [
            "id",
            "group",
            "user",
            "message",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = ["status", "reviewed_by", "reviewed_at", "created_at"]


class GroupBanSerializer(serializers.ModelSerializer):
    user = GroupUserSerializer(read_only=True)
    banned_by = GroupUserSerializer(read_only=True)

    class Meta:
        model = GroupBan
        fields = [
            "id",
            "group",
            "user",
            "reason",
            "banned_by",
            "banned_at",
            "expires_at",
        ]
        read_only_fields = ["banned_at"]
