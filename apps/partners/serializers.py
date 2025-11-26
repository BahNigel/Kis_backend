# apps/partners/serializers.py
from rest_framework import serializers

from apps.partners.models import Partner
from apps.chat.models import ConversationType


class PartnerListSerializer(serializers.ModelSerializer):
    main_conversation_id = serializers.UUIDField(
        source="main_conversation.id",
        read_only=True,
    )

    class Meta:
        model = Partner
        fields = [
            "id",
            "name",
            "slug",
            "avatar_url",
            "is_active",
            "main_conversation_id",
            "created_at",
            "updated_at",
        ]


class PartnerDetailSerializer(serializers.ModelSerializer):
    main_conversation_id = serializers.UUIDField(
        source="main_conversation.id",
        read_only=True,
    )

    class Meta:
        model = Partner
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "avatar_url",
            "owner",
            "is_active",
            "main_conversation_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "owner",
            "main_conversation_id",
            "created_at",
            "updated_at",
        ]


class PartnerCreateSerializer(serializers.ModelSerializer):
    """
    Used for creating a Partner. Optionally also creates a main POST Conversation.

    Payload example:
        {
          "name": "Kingdom Impact Global",
          "slug": "kingdom-impact-global",
          "description": "...",
          "avatar_url": "https://...",
          "create_main_conversation": true
        }
    """

    create_main_conversation = serializers.BooleanField(
        default=True,
        required=False,          # 👈 important: don't force client to send it
        write_only=True,
        help_text="If true, create a main POST conversation for this partner.",
    )

    class Meta:
        model = Partner
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "avatar_url",
            "create_main_conversation",
        ]

    def validate_slug(self, value):
        # Optionally add custom slug rules here
        return value

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        # Default to True if not provided
        create_main_conversation = validated_data.pop("create_main_conversation", True)

        from apps.chat.models import (
            Conversation,
            ConversationSettings,
            ConversationMember,
            BaseConversationRole,
        )

        main_conversation = None

        if create_main_conversation:
            # Create a POST-style conversation for this partner
            main_conversation = Conversation.objects.create(
                type=ConversationType.POST,  # 👈 POST conversation as requested
                title=validated_data.get("name", ""),
                description=f"Post space for partner {validated_data.get('name', '')}",
                created_by=user,
            )

            # Make the creator the owner/primary member
            ConversationMember.objects.create(
                conversation=main_conversation,
                user=user,
                base_role=BaseConversationRole.OWNER,
            )

            # Default settings for this conversation
            ConversationSettings.objects.create(conversation=main_conversation)

        # Create the Partner linked to this main_conversation
        partner = Partner.objects.create(
            owner=user,
            main_conversation=main_conversation,
            **validated_data,
        )

        return partner
