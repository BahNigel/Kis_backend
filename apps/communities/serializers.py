# apps/communities/serializers.py
from django.db import models
from rest_framework import serializers

from apps.communities.models import (
    Community,
    CommunityMembership,
    CommunityJoinRequest,
    CommunityBan,
    CommunityPost,
    CommunityPostComment,
    CommunityPostReaction,
    CommunityCommentReaction,
    CommunityRole,
)
from apps.chat.models import ConversationType  # must include POST
from apps.accounts.models import User


class CommunityUserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "display_name", "phone", "avatar_url"]

    def get_avatar_url(self, obj):
        profile = getattr(obj, "profile", None)
        return getattr(profile, "avatar_url", None) if profile else None


class CommunityListSerializer(serializers.ModelSerializer):
    main_conversation_id = serializers.UUIDField(
        source="main_conversation.id",
        read_only=True,
    )
    posts_conversation_id = serializers.UUIDField(
        source="posts_conversation.id",
        read_only=True,
        required=False,
    )

    class Meta:
        model = Community
        fields = [
            "id",
            "name",
            "slug",
            "avatar_url",
            "is_active",
            "partner",
            "main_conversation_id",
            "posts_conversation_id",
            "created_at",
            "updated_at",
        ]


class CommunityDetailSerializer(serializers.ModelSerializer):
    main_conversation_id = serializers.UUIDField(
        source="main_conversation.id",
        read_only=True,
    )
    posts_conversation_id = serializers.UUIDField(
        source="posts_conversation.id",
        read_only=True,
        required=False,
    )

    class Meta:
        model = Community
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "avatar_url",
            "partner",
            "owner",
            "is_active",
            "main_conversation_id",
            "posts_conversation_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "owner",
            "main_conversation_id",
            "posts_conversation_id",
            "created_at",
            "updated_at",
        ]


class CommunityCreateSerializer(serializers.ModelSerializer):
    """
    For creating a community under a partner.

    Payload example:
        {
          "partner": "<partner_id>",
          "name": "KIS Dev Community",
          "slug": "kis-dev",
          "description": "Community for devs",
          "avatar_url": "https://...",
          "create_main_conversation": true,
          "create_posts_conversation": true
        }
    """

    create_main_conversation = serializers.BooleanField(
        default=True,
        write_only=True,
        help_text="If true, create a main (chat) conversation for this community.",
    )
    create_posts_conversation = serializers.BooleanField(
        default=True,
        write_only=True,
        help_text="If true, create a posts conversation (feed) for this community.",
    )

    class Meta:
        model = Community
        fields = [
            "id",
            "partner",
            "name",
            "slug",
            "description",
            "avatar_url",
            "create_main_conversation",
            "create_posts_conversation",
        ]

    def validate(self, attrs):
        # Place for slug uniqueness per partner if needed
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        create_main_conversation = validated_data.pop(
            "create_main_conversation",
            True,
        )
        create_posts_conversation = validated_data.pop(
            "create_posts_conversation",
            True,
        )

        from apps.chat.models import (
            Conversation,
            ConversationSettings,
            ConversationMember,
            BaseConversationRole,
        )

        name = validated_data.get("name", "").strip() or "Community"

        main_conversation = None
        posts_conversation = None

        # --- Main chat / lobby (group-style) ---
        if create_main_conversation:
            main_conversation = Conversation.objects.create(
                type=ConversationType.GROUP,
                title=name,
                created_by=user,
            )

            ConversationMember.objects.create(
                conversation=main_conversation,
                user=user,
                base_role=BaseConversationRole.OWNER,
            )

            ConversationSettings.objects.create(conversation=main_conversation)

        # --- Posts feed conversation ---
        if create_posts_conversation:
            posts_conversation = Conversation.objects.create(
                type=ConversationType.POST,
                title=f"{name} posts",
                created_by=user,
            )

            ConversationMember.objects.create(
                conversation=posts_conversation,
                user=user,
                base_role=BaseConversationRole.OWNER,
            )

            ConversationSettings.objects.create(conversation=posts_conversation)

        community = Community.objects.create(
            owner=user,
            main_conversation=main_conversation,
            posts_conversation=posts_conversation,
            **validated_data,
        )

        CommunityMembership.objects.create(
            community=community,
            user=user,
            role=CommunityRole.OWNER,
        )

        return community


class CommunityMembershipSerializer(serializers.ModelSerializer):
    user = CommunityUserSerializer(read_only=True)

    class Meta:
        model = CommunityMembership
        fields = [
            "id",
            "community",
            "user",
            "role",
            "joined_at",
            "left_at",
            "is_muted",
            "is_banned",
            "can_access_all_groups",
        ]
        read_only_fields = ["joined_at", "left_at", "is_banned"]


class CommunityJoinRequestSerializer(serializers.ModelSerializer):
    user = CommunityUserSerializer(read_only=True)
    reviewed_by = CommunityUserSerializer(read_only=True)

    class Meta:
        model = CommunityJoinRequest
        fields = [
            "id",
            "community",
            "user",
            "message",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = ["status", "reviewed_by", "reviewed_at", "created_at"]


class CommunityBanSerializer(serializers.ModelSerializer):
    user = CommunityUserSerializer(read_only=True)
    banned_by = CommunityUserSerializer(read_only=True)

    class Meta:
        model = CommunityBan
        fields = [
            "id",
            "community",
            "user",
            "reason",
            "banned_by",
            "banned_at",
            "expires_at",
        ]
        read_only_fields = ["banned_at"]


class CommunityPostSerializer(serializers.ModelSerializer):
    author = CommunityUserSerializer(read_only=True)
    reactions = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = CommunityPost
        fields = [
            "id",
            "community",
            "author",
            "text",
            "styled_text",
            "attachments",
            "poll",
            "event",
            "link",
            "status",
            "is_pinned",
            "pinned_by",
            "pinned_at",
            "is_deleted",
            "created_at",
            "updated_at",
            "reactions",
            "comments_count",
        ]
        read_only_fields = [
            "author",
            "status",
            "is_pinned",
            "pinned_by",
            "pinned_at",
            "is_deleted",
            "created_at",
            "updated_at",
            "reactions",
            "comments_count",
        ]

    def get_reactions(self, obj):
        qs = obj.reactions.values("emoji").annotate(count=models.Count("id"))
        return list(qs)

    def get_comments_count(self, obj):
        return obj.comments.filter(is_deleted=False).count()


class CommunityPostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityPost
        fields = [
            "id",
            "community",
            "text",
            "styled_text",
            "attachments",
            "poll",
            "event",
            "link",
        ]

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        post = CommunityPost.objects.create(author=user, **validated_data)
        return post


class CommunityPostCommentSerializer(serializers.ModelSerializer):
    author = CommunityUserSerializer(read_only=True)

    class Meta:
        model = CommunityPostComment
        fields = [
            "id",
            "post",
            "author",
            "text",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["author", "is_deleted", "created_at", "updated_at"]


class CommunityPostReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityPostReaction
        fields = ["id", "post", "user", "emoji", "created_at"]
        read_only_fields = ["created_at", "user"]


class CommunityCommentReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityCommentReaction
        fields = ["id", "comment", "user", "emoji", "created_at"]
        read_only_fields = ["created_at", "user"]
