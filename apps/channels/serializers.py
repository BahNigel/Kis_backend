# apps/channels/serializers.py
from rest_framework import serializers

from apps.channels.models import Channel
from apps.chat.models import (
    BaseConversationRole,
    ConversationMember,
    ConversationSettings,
    ConversationSendPolicy,
    ConversationType,
)


def _member_for(channel: Channel, user):
    if not user or not user.is_authenticated:
        return None
    return ConversationMember.objects.filter(
        conversation=channel.conversation,
        user=user,
        left_at__isnull=True,
    ).first()


def _can_send(channel: Channel, member: ConversationMember | None) -> bool:
    if not member or member.base_role == BaseConversationRole.READONLY:
        return False
    settings = ConversationSettings.objects.filter(conversation=channel.conversation).first()
    if settings and settings.send_policy == ConversationSendPolicy.ADMINS_ONLY:
        return member.base_role in (BaseConversationRole.OWNER, BaseConversationRole.ADMIN)
    return True


class ChannelListSerializer(serializers.ModelSerializer):
    conversation_id = serializers.UUIDField(source="conversation.id", read_only=True)
    is_subscribed = serializers.SerializerMethodField()
    member_role = serializers.SerializerMethodField()
    can_post = serializers.SerializerMethodField()

    class Meta:
        model = Channel
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "avatar_url",
            "invite_messages",
            "is_archived",
            "partner",
            "community",
            "is_subscribed",
            "member_role",
            "can_post",
            "conversation_id",
            "created_at",
            "updated_at",
        ]

    def get_is_subscribed(self, obj):
        member = _member_for(obj, self.context["request"].user)
        return bool(member)

    def get_member_role(self, obj):
        member = _member_for(obj, self.context["request"].user)
        return member.base_role if member else None

    def get_can_post(self, obj):
        member = _member_for(obj, self.context["request"].user)
        return _can_send(obj, member)


class ChannelDetailSerializer(serializers.ModelSerializer):
    conversation_id = serializers.UUIDField(source="conversation.id", read_only=True)
    is_subscribed = serializers.SerializerMethodField()
    member_role = serializers.SerializerMethodField()
    can_post = serializers.SerializerMethodField()

    class Meta:
        model = Channel
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "avatar_url",
            "invite_messages",
            "partner",
            "community",
            "owner",
            "is_archived",
            "is_subscribed",
            "member_role",
            "can_post",
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

    def get_is_subscribed(self, obj):
        member = _member_for(obj, self.context["request"].user)
        return bool(member)

    def get_member_role(self, obj):
        member = _member_for(obj, self.context["request"].user)
        return member.base_role if member else None

    def get_can_post(self, obj):
        member = _member_for(obj, self.context["request"].user)
        return _can_send(obj, member)


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
            "invite_messages",
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
