# apps/channels/serializers.py
from rest_framework import serializers

from apps.channels.models import Channel
from apps.chat.models import ConversationType


class ChannelListSerializer(serializers.ModelSerializer):
    conversation_id = serializers.UUIDField(source="conversation.id", read_only=True)

    class Meta:
        model = Channel
        fields = [
            "id",
            "name",
            "slug",
            "avatar_url",
            "is_archived",
            "partner",
            "community",
            "conversation_id",
            "created_at",
            "updated_at",
        ]


class ChannelDetailSerializer(serializers.ModelSerializer):
    conversation_id = serializers.UUIDField(source="conversation.id", read_only=True)

    class Meta:
        model = Channel
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "avatar_url",
            "partner",
            "community",
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


class ChannelCreateSerializer(serializers.ModelSerializer):
    """
    For creating a channel; automatically creates the backing Conversation
    and membership for the owner.

    For channels, we usually want send_policy=ADMINS_ONLY by default
    (announcement / broadcast style), but you can tweak it.
    """

    class Meta:
        model = Channel
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "avatar_url",
            "partner",
            "community",
        ]

    def validate(self, attrs):
        # Add any custom validation (e.g., require partner OR community) later.
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        from apps.chat.models import (
            Conversation,
            ConversationSettings,
            BaseConversationRole,
            ConversationMember,
            ConversationSendPolicy,
        )

        # 1. Create Conversation of type CHANNEL
        conversation = Conversation.objects.create(
            type=ConversationType.CHANNEL,
            title=validated_data.get("name", ""),
            description=validated_data.get("description", ""),
            avatar_url=validated_data.get("avatar_url", ""),
            created_by=user,
        )

        # 2. Add owner as conversation member with OWNER role
        ConversationMember.objects.create(
            conversation=conversation,
            user=user,
            base_role=BaseConversationRole.OWNER,
        )

        # 3. Create default settings for the conversation, but for channels
        #    we can default send_policy to ADMINS_ONLY (broadcast style).
        ConversationSettings.objects.create(
            conversation=conversation,
            send_policy=ConversationSendPolicy.ADMINS_ONLY,
        )

        # 4. Create the Channel linked to this conversation
        channel = Channel.objects.create(
            owner=user,
            conversation=conversation,
            **validated_data,
        )
        return channel
