# chat/serializers.py
from apps.accounts.serializers import UserSerializer
from rest_framework import serializers

from .models import (
    Conversation,
    ConversationMember,
    ConversationSettings,
    MessageThreadLink,
    BaseConversationRole,
)


# ---------------------------------------------------------------------------
#  SETTINGS & MEMBERS
# ---------------------------------------------------------------------------

class ConversationSettingsSerializer(serializers.ModelSerializer):
    """Per-conversation settings (policies, retention, feature flags)."""

    class Meta:
        model = ConversationSettings
        fields = [
            "send_policy",
            "join_policy",
            "info_edit_policy",
            "subroom_policy",
            "max_subroom_depth",
            "message_retention_days",
            "allow_reactions",
            "allow_stickers",
            "allow_attachments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class ConversationMemberSerializer(serializers.ModelSerializer):
    """
    Member view: exposes full user info + membership metadata.
    All user information is now nested under the `user` field.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = ConversationMember
        fields = [
            "id",
            "user",  # nested user info
            "base_role",
            "display_name",
            "notification_level",
            "color",
            "is_muted",
            "is_blocked",
            "joined_at",
            "left_at",
            "is_active",
        ]
        read_only_fields = ["joined_at", "left_at", "is_active"]


# ---------------------------------------------------------------------------
#  CONVERSATION LIST & DETAIL
# ---------------------------------------------------------------------------

class ConversationListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing conversations in the chat list.

    - `participants` now includes full user info via ConversationMemberSerializer.
    """

    last_message_at = serializers.DateTimeField(allow_null=True)
    participants = ConversationMemberSerializer(
        source="memberships",
        many=True,
        read_only=True,
    )

    # DM request initiator / recipient as nested users
    request_initiator = UserSerializer(read_only=True)
    request_recipient = UserSerializer(read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "type",
            "title",
            "description",
            "avatar_url",
            "is_archived",
            "is_locked",
            "last_message_at",
            "last_message_preview",
            "created_at",
            "updated_at",
            # Request/lock state for DM flows
            "request_state",
            "request_initiator",
            "request_recipient",
            "participants",
        ]


class ConversationDetailSerializer(serializers.ModelSerializer):
    """
    Detailed view including settings and member list.

    `members` uses ConversationMemberSerializer, so each member
    also includes full nested user info.
    """

    settings = ConversationSettingsSerializer(read_only=True)
    members = ConversationMemberSerializer(
        source="memberships",
        many=True,
        read_only=True,
    )

    request_initiator = UserSerializer(read_only=True)
    request_recipient = UserSerializer(read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "type",
            "title",
            "description",
            "avatar_url",
            "created_by",
            "is_archived",
            "is_locked",
            "last_message_at",
            "last_message_preview",
            "created_at",
            "updated_at",
            "settings",
            "members",
            # DM request state
            "request_state",
            "request_initiator",
            "request_recipient",
            "request_accepted_at",
            "request_rejected_at",
        ]
        read_only_fields = [
            "created_by",
            "is_archived",
            "last_message_at",
            "last_message_preview",
            "created_at",
            "updated_at",
            # Request fields are backend-driven
            "request_state",
            "request_initiator",
            "request_recipient",
            "request_accepted_at",
            "request_rejected_at",
        ]


# ---------------------------------------------------------------------------
#  CONVERSATION CREATE (groups / channels / threads)
# ---------------------------------------------------------------------------

class ConversationCreateSerializer(serializers.ModelSerializer):
    """
    Used for creating new group/channel/thread conversations from Django side.

    Direct conversations (1:1) use a separate serializer below.
    """

    # Accept flexible participant payload so DRF doesn’t reject the request
    participants = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        write_only=True,
        allow_empty=True,
    )
    user_id = serializers.DictField(required=False, write_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "type",
            "title",
            "description",
            "avatar_url",
            "is_locked",
            # NOTE: participants & user_id are write-only extras, not model fields
            "participants",
            "user_id",
        ]

    def create(self, validated_data):
        from apps.accounts.models import User  # local to avoid circulars

        request = self.context["request"]
        user = request.user

        # pop write-only extras so they are not passed into Conversation()
        validated_data.pop("participants", None)
        validated_data.pop("user_id", None)

        # 1) Create the conversation itself
        conversation = Conversation.objects.create(
            created_by=user,
            **validated_data,
        )

        # 2) Ensure creator is a member (OWNER) by default
        ConversationMember.objects.create(
            conversation=conversation,
            user=user,
            base_role=BaseConversationRole.OWNER,
        )

        # 3) Extract participants (phone strings) from raw request.data
        raw_data = getattr(request, "data", {}) or {}

        # Preferred:
        #   raw_data["user_id"]["participant"] -> ["+2376...", "+2376..."]
        # Fallbacks:
        #   raw_data["user_id"]["participants"]
        #   raw_data["participants"]
        participants = []

        user_id_block = raw_data.get("user_id") or {}
        if isinstance(user_id_block, dict):
            participants = user_id_block.get("participant") or []
            if not participants:
                participants = user_id_block.get("participants") or []

        if not participants:
            participants = raw_data.get("participants") or []

        if not isinstance(participants, (list, tuple)):
            participants = []

        print("checking participants now: ", participants)

        phone_numbers = [
            str(p).strip()
            for p in participants
            if p is not None and str(p).strip() != ""
        ]
        phone_numbers = list(dict.fromkeys(phone_numbers))  # unique

        print("checking phone number: ", phone_numbers)

        # 4) Look up users by phone and create memberships
        if phone_numbers:
            # IMPORTANT: your User model uses `phone`, not `phone_number`
            users = User.objects.filter(phone__in=phone_numbers).distinct()

            for participant_user in users:
                if participant_user == user:
                    continue

                ConversationMember.objects.get_or_create(
                    conversation=conversation,
                    user=participant_user,
                    defaults={"base_role": BaseConversationRole.MEMBER},
                )

        # 5) Create default settings row
        ConversationSettings.objects.create(conversation=conversation)

        return conversation


# ---------------------------------------------------------------------------
#  DIRECT CONVERSATION CREATE (1:1)
# ---------------------------------------------------------------------------

class DirectConversationCreateSerializer(serializers.Serializer):
    """
    Payload for creating/fetching a direct 1:1 conversation.
    """

    # Optional, for legacy / direct ID usage
    peer_user_id = serializers.IntegerField(required=False)

    # New fields to match mobile payload, but we keep them optional
    type = serializers.CharField(required=False, allow_blank=True)
    title = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    last_message_preview = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    participants = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    user_id = serializers.DictField(required=False)
    client_context = serializers.DictField(required=False)

    # ---- helpers -----------------------------------------------------------

    def _extract_phone_participants(self, raw_data):
        """
        Extract a list of phone numbers from the flexible request shape.
        Mirrors the logic in ConversationCreateSerializer.
        """
        participants = []

        user_id_block = raw_data.get("user_id") or {}
        if isinstance(user_id_block, dict):
            participants = user_id_block.get("participant") or []
            if not participants:
                participants = user_id_block.get("participants") or []

        if not participants:
            participants = raw_data.get("participants") or []

        if not isinstance(participants, (list, tuple)):
            participants = []

        phone_numbers = [
            str(p).strip()
            for p in participants
            if p is not None and str(p).strip() != ""
        ]

        phone_numbers = list(dict.fromkeys(phone_numbers))  # unique
        return phone_numbers

    # ---- main validation ---------------------------------------------------

    def validate(self, attrs):
        from apps.accounts.models import User

        request = self.context["request"]
        raw_data = getattr(request, "data", {}) or {}

        # 1) If peer_user_id is given directly, validate that path
        peer_id = raw_data.get("peer_user_id") or attrs.get("peer_user_id")
        if peer_id is not None:
            peer_id = int(peer_id)

            if peer_id == request.user.id:
                raise serializers.ValidationError(
                    {"peer_user_id": "Cannot create a direct chat with yourself."}
                )

            try:
                User.objects.get(id=peer_id)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    {"peer_user_id": "Peer user does not exist."}
                )

            attrs["peer_user_id"] = peer_id
            return attrs

        # 2) Otherwise, derive peer from phone numbers
        phone_numbers = self._extract_phone_participants(raw_data)
        if not phone_numbers:
            raise serializers.ValidationError(
                "Either 'peer_user_id' or at least one participant phone number is required."
            )

        # For a direct chat we only consider the first phone number
        first_phone = phone_numbers[0]

        try:
            # IMPORTANT: your User model uses `phone`, not `phone_number`
            peer_user = User.objects.get(phone=first_phone)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"participants": f"User with phone number {first_phone} does not exist."}
            )

        if peer_user.id == request.user.id:
            raise serializers.ValidationError(
                {"participants": "Cannot create a direct chat with yourself."}
            )

        attrs["peer_user_id"] = peer_user.id
        return attrs

    def validate_peer_user_id(self, value):
        """
        Kept for compatibility in case DRF calls this when peer_user_id
        is present in the incoming payload.
        """
        from apps.accounts.models import User

        request = self.context["request"]

        if value == request.user.id:
            raise serializers.ValidationError("Cannot create a direct chat with yourself.")

        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Peer user does not exist.")

        return value
    
    def create(self, validated_data):
        from apps.accounts.models import User
        from .models import (
            Conversation,
            ConversationMember,
            ConversationSettings,
            ConversationType,
            ConversationRequestState,
            BaseConversationRole,
        )

        request = self.context["request"]
        user: User = request.user
        peer_user_id = validated_data["peer_user_id"]
        peer_user = User.objects.get(id=peer_user_id)

        # 1) If a direct conversation between these 2 users already exists, reuse it
        existing = (
            Conversation.objects.filter(
                type=ConversationType.DIRECT,
                memberships__user=user,
            )
            .filter(memberships__user=peer_user)
            .distinct()
            .first()
        )
        if existing:
            return existing

        # 2) Otherwise create a new direct conversation
        print("thids is working Nigel 88888888888888888888888888888888888888cs")
        conv = Conversation.objects.create(
            type=ConversationType.DIRECT,
            created_by=user,
            # ✅ DM request fields – creator is initiator, peer is recipient
            request_state=ConversationRequestState.PENDING,
            request_initiator=user,
            request_recipient=peer_user,
            # optional title/preview if you like:
            # title=f"{user.display_name} & {peer_user.display_name}",
            # last_message_preview="",
        )

        # 3) Create memberships
        ConversationMember.objects.create(
            conversation=conv,
            user=user,
            base_role=BaseConversationRole.OWNER,
        )
        ConversationMember.objects.create(
            conversation=conv,
            user=peer_user,
            base_role=BaseConversationRole.MEMBER,
        )

        # 4) Default settings row
        ConversationSettings.objects.create(conversation=conv)

        return conv


# ---------------------------------------------------------------------------
#  MESSAGE THREAD LINKS
# ---------------------------------------------------------------------------

class MessageThreadLinkSerializer(serializers.ModelSerializer):
    """Link between a parent message and a child conversation (sub-room)."""

    class Meta:
        model = MessageThreadLink
        fields = [
            "id",
            "parent_conversation",
            "parent_message_key",
            "child_conversation",
            "parent_thread",
            "depth",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["created_by", "created_at"]
