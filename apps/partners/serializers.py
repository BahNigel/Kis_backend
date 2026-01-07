# apps/partners/serializers.py
from rest_framework import serializers

from apps.partners.models import Partner, PartnerPost
from apps.chat.models import ConversationType
from apps.chat.models import ConversationMember, BaseConversationRole


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
    admins = serializers.SerializerMethodField()

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
            "admins",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "owner",
            "main_conversation_id",
            "created_at",
            "updated_at",
        ]

    def get_admins(self, obj):
        if not obj.main_conversation_id:
            return []
        members = (
            ConversationMember.objects
            .select_related("user", "user__profile")
            .filter(
                conversation_id=obj.main_conversation_id,
                left_at__isnull=True,
                base_role__in=[BaseConversationRole.OWNER, BaseConversationRole.ADMIN],
            )
        )
        admins = []
        for member in members:
            user = member.user
            profile = getattr(user, "profile", None)
            name = getattr(user, "display_name", None) or getattr(user, "username", None) or str(user.id)
            initials = "".join([part[0].upper() for part in str(name).split()[:2] if part]) or "??"
            admins.append(
                {
                    "id": str(user.id),
                    "name": name,
                    "initials": initials,
                    "position": member.base_role,
                    "avatarUrl": getattr(profile, "avatar_url", None) if profile else None,
                }
            )
        return admins


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


class PartnerPostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = PartnerPost
        fields = [
            "id",
            "partner",
            "author",
            "text",
            "styled_text",
            "attachments",
            "poll",
            "event",
            "link",
            "is_deleted",
            "created_at",
            "updated_at",
        ]

    def get_author(self, obj):
        author = obj.author
        profile = getattr(author, "profile", None)
        return {
            "id": str(author.id),
            "display_name": getattr(author, "display_name", None),
            "phone": getattr(author, "phone", None),
            "avatar_url": getattr(profile, "avatar_url", None) if profile else None,
        }


class PartnerPostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerPost
        fields = [
            "id",
            "partner",
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
        return PartnerPost.objects.create(author=user, **validated_data)
