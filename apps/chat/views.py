# chat/views.py
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import DatabaseError

from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied

from .models import (
    Conversation,
    ConversationMember,
    ConversationSettings,
    MessageThreadLink,
    ConversationType,
    BaseConversationRole,
    ConversationRequestState,
)
from .serializers import (
    ConversationListSerializer,
    ConversationDetailSerializer,
    ConversationCreateSerializer,
    DirectConversationCreateSerializer,
    ConversationMemberSerializer,
    ConversationSettingsSerializer,
    MessageThreadLinkSerializer,
)
from .services import get_or_create_direct_conversation, user_is_active_member

from apps.accounts.models import User


def _extract_phone_participants(raw_data) -> list[str]:
    """
    Accepts flexible shapes from RN:
      - participants: ["+237..."]
      - user_id: { participants: ["+237..."] }
      - user_id: { participant: ["+237..."] }
    Returns list of normalized phone strings.
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

    phones = []
    for p in participants:
        if p is None:
            continue
        s = str(p).strip()
        if s:
            phones.append(s)

    # unique preserve order
    seen = set()
    out = []
    for ph in phones:
        if ph not in seen:
            seen.add(ph)
            out.append(ph)
    return out


def _resolve_peer_user(request_user: User, raw_data: dict) -> User:
    """
    Resolves the peer user for a direct chat.
    Priority:
      1) peer_user_id (if provided)
      2) first phone number in participants payload
    """
    peer_user_id = raw_data.get("peer_user_id")
    if peer_user_id is not None:
        try:
            peer_id = int(peer_user_id)
        except Exception:
            raise ValidationError({"peer_user_id": "peer_user_id must be an integer"})

        if peer_id == request_user.id:
            raise ValidationError({"peer_user_id": "Cannot create a direct chat with yourself."})

        try:
            return User.objects.get(id=peer_id)
        except User.DoesNotExist:
            raise ValidationError({"peer_user_id": "Peer user does not exist."})

    phones = _extract_phone_participants(raw_data)
    if not phones:
        raise ValidationError(
            "Either 'peer_user_id' or at least one participant phone number is required."
        )

    # For direct chat, use the first phone only
    first_phone = phones[0]
    try:
        peer = User.objects.get(phone=first_phone)
    except User.DoesNotExist:
        raise ValidationError({"participants": f"User with phone number {first_phone} does not exist."})

    if peer.id == request_user.id:
        raise ValidationError({"participants": "Cannot create a direct chat with yourself."})

    return peer


class ConversationViewSet(viewsets.ModelViewSet):
    """
    /api/chat/conversations/

    - list/retrieve/create/update
    - direct: create/fetch 1:1 DM using request workflow
    - accept-request / reject-request
    - update-last-message: internal endpoint called by Nest
    """
    permission_classes = [IsAuthenticated]

    # ------------------------------------------------------------------
    # Query / serializers
    # ------------------------------------------------------------------
    def get_queryset(self):
        user = self.request.user
        return (
            Conversation.objects
            .filter(memberships__user=user, memberships__left_at__isnull=True)
            .distinct()
            .select_related('created_by', 'request_initiator', 'request_recipient')
            .prefetch_related('memberships__user', 'memberships')  # memberships itself too
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return ConversationListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return ConversationCreateSerializer
        if self.action == 'direct':
            return DirectConversationCreateSerializer
        return ConversationDetailSerializer

    def perform_create(self, serializer):
        serializer.save()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not user_is_active_member(request.user, instance):
            return Response(
                {"detail": "You are not a member of this conversation."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(self.get_serializer(instance).data)

    # ------------------------------------------------------------------
    # Direct conversations (DM request flow)
    # ------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='direct')
    def direct(self, request):
        """
        POST /api/v1/conversations/direct/

        Supports:
          - {"peer_user_id": 123}
          - {"participants": ["+237..."], "user_id": {"participants": ["+237..."]}, ...}

        If new, it creates a pending DM request:
          - request_state=PENDING
          - request_initiator=request.user
          - request_recipient=peer_user
        """
        # Still validate basic shape using your serializer (keeps compatibility),
        # but we also support phone payloads.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=False)  # do not hard fail; we resolve ourselves

        peer_user = _resolve_peer_user(request.user, request.data)

        conversation, created = get_or_create_direct_conversation(
            user_a=request.user,
            user_b=peer_user,
            initiator=request.user,
            use_request_flow=True,
        )

        # Safety: ensure requester is actually a member (should always be true)
        if not user_is_active_member(request.user, conversation):
            # This indicates corrupted state; better to fail loudly than create ghost conversations.
            raise PermissionDenied("You are not a member of this conversation.")

        data = ConversationDetailSerializer(conversation).data
        return Response(
            data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # Members
    # ------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='members')
    def add_member(self, request, pk=None):
        conversation = self.get_object()
        if not user_is_active_member(request.user, conversation):
            return Response({"detail": "You are not a member of this conversation."}, status=403)

        user_id = request.data.get('user_id')
        base_role = request.data.get('base_role', BaseConversationRole.MEMBER)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User does not exist."}, status=400)

        member, created = ConversationMember.objects.get_or_create(
            conversation=conversation,
            user=user,
            defaults={'base_role': base_role},
        )

        if not created and member.left_at:
            member.left_at = None
            member.base_role = base_role
            member.save(update_fields=["left_at", "base_role"])

        return Response(ConversationMemberSerializer(member).data, status=201)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    @action(detail=True, methods=['patch'], url_path='settings')
    def update_settings(self, request, pk=None):
        conversation = self.get_object()
        if not user_is_active_member(request.user, conversation):
            return Response({"detail": "You are not a member of this conversation."}, status=403)

        settings_obj, _ = ConversationSettings.objects.get_or_create(conversation=conversation)
        serializer = ConversationSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    # ------------------------------------------------------------------
    # DM request accept / reject
    # ------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='accept-request')
    def accept_request(self, request, pk=None):
        conversation = self.get_object()

        if conversation.type != ConversationType.DIRECT:
            return Response({"detail": "Not a direct conversation"}, status=400)
        if conversation.request_state != ConversationRequestState.PENDING:
            return Response({"detail": "Not pending"}, status=400)
        if conversation.request_recipient_id != request.user.id:
            return Response({"detail": "Not recipient"}, status=403)

        conversation.request_state = ConversationRequestState.ACCEPTED
        conversation.request_accepted_at = timezone.now()
        conversation.save(update_fields=['request_state', 'request_accepted_at'])

        return Response(ConversationDetailSerializer(conversation).data, status=200)

    @action(detail=True, methods=['get'], url_path='block_chat')
    def block_chat(self, request, pk=None):
        conversation = Conversation.objects.get(pk=pk)
        if conversation.type != ConversationType.DIRECT:
            return Response({"detail": "Not a direct conversation"}, status=400)
        conversation.is_locked = True
        conversation.locked_by = request.user
        conversation.save(update_fields=['is_locked', 'locked_by'])
        response = ConversationDetailSerializer(conversation).data
        print("see Response: ", response)
        return Response(response, status=200)

    # ------------------------------------------------------------------
    # 🔐 INTERNAL: last-message update (called by NestJS)
    # ------------------------------------------------------------------
    @action(
        detail=True,
        methods=['patch'],
        url_path='update-last-message',
        permission_classes=[],  # internal only
        authentication_classes=[],
    )
    def update_last_message(self, request, pk=None):
       
        try:
            conversation = Conversation.objects.get(pk=pk)
        except Conversation.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)

        incoming_at = request.data.get('last_message_at')
        preview = (request.data.get('last_message_preview') or '')[:255]

        if not incoming_at:
            return Response({"detail": "last_message_at required"}, status=400)

        dt = parse_datetime(incoming_at)
        if not dt:
            return Response({"detail": "Invalid datetime"}, status=400)

        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone=timezone.utc)

        if conversation.last_message_at and dt < conversation.last_message_at:
            return Response({"ok": True, "ignored": True})

        print("checking data:", request.data, "pk:", pk)
        conversation.last_message_at = dt
        conversation.last_message_preview = preview
        conversation.save(update_fields=['last_message_at', 'last_message_preview'])

        return Response({"ok": True})

# ----------------------------------------------------------------------
# Threads
# ----------------------------------------------------------------------
class MessageThreadLinkViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = MessageThreadLink.objects.all()
    serializer_class = MessageThreadLinkSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        parent = serializer.validated_data['parent_conversation']
        if not user_is_active_member(self.request.user, parent):
            raise PermissionDenied("Not a member")
        serializer.save(created_by=self.request.user)
