# apps/groups/serializers.py
from rest_framework import serializers

from apps.groups.models import Group
from apps.chat.models import ConversationType


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
        ]

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

        return group
