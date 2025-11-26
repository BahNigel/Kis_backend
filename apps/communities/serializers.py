# apps/communities/serializers.py
from rest_framework import serializers

from apps.communities.models import Community
from apps.chat.models import ConversationType  # must include POST


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

        return community
