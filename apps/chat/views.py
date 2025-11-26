# chat/views.py
from django.utils import timezone

from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
from .permissions import IsConversationMember  # currently unused but kept
from .services import get_or_create_direct_conversation, user_is_active_member


class ConversationViewSet(viewsets.ModelViewSet):
    """
    /api/chat/conversations/

    - list: all conversations for the authenticated user
    - retrieve: details (members, settings)
    - create: create a group/channel/thread conversation
    - direct: (custom action) create or fetch a 1:1 direct conversation
    - accept-request: accept a pending direct message request
    - reject-request: reject a pending direct message request
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return (
            Conversation.objects
            .filter(memberships__user=user, memberships__left_at__isnull=True)
            .distinct()
            .select_related('created_by')
            .prefetch_related('memberships__user')
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
        # ConversationCreateSerializer sets created_by and membership
        serializer.save()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Ensure membership
        if not user_is_active_member(request.user, instance):
            return Response(
                {"detail": "You are not a member of this conversation."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # ---------------------------------------------------------------------
    # Direct conversations (DM request flow)
    # ---------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='direct')
    def direct(self, request, *args, **kwargs):
        """
        POST /api/chat/conversations/direct/
        {
          "peer_user_id": 123
        }

        Returns the existing or newly-created direct conversation between
        request.user and the peer.

        If no conversation exists yet, a new one is created as a *pending
        direct message request*:

          - type = DIRECT
          - request_state = PENDING
          - request_initiator = request.user
          - request_recipient = peer_user

        The actual enforcement of "initiator can only send first message"
        is handled on the message service (NestJS) side.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        peer_user_id = serializer.validated_data['peer_user_id']
        from apps.accounts.models import User
        peer_user = User.objects.get(id=peer_user_id)

        conversation, created = get_or_create_direct_conversation(
            user_a=request.user,
            user_b=peer_user,
            initiator=request.user,
        )

        detail_serializer = ConversationDetailSerializer(conversation)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(detail_serializer.data, status=status_code)

    # ---------------------------------------------------------------------
    # Membership management
    # ---------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='members')
    def add_member(self, request, pk=None):
        """
        POST /api/chat/conversations/{id}/members/
        {
          "user_id": 123,
          "base_role": "member"
        }

        Adds a user to the conversation. Permission checks can be expanded
        using RBAC and RoleDefinition in future.
        """
        conversation = self.get_object()
        # Basic check: must be an active member to add others
        if not user_is_active_member(request.user, conversation):
            return Response(
                {"detail": "You are not a member of this conversation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user_id = request.data.get('user_id')
        base_role = request.data.get('base_role', BaseConversationRole.MEMBER)

        from apps.accounts.models import User
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User does not exist."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member, created = ConversationMember.objects.get_or_create(
            conversation=conversation,
            user=user,
            defaults={'base_role': base_role},
        )
        if not created:
            # Re-activate if previously left
            if member.left_at is not None:
                member.left_at = None
            member.base_role = base_role
            member.save()

        ser = ConversationMemberSerializer(member)
        return Response(ser.data, status=status.HTTP_201_CREATED)

    # ---------------------------------------------------------------------
    # Conversation settings
    # ---------------------------------------------------------------------
    @action(detail=True, methods=['patch'], url_path='settings')
    def update_settings(self, request, pk=None):
        """
        PATCH /api/chat/conversations/{id}/settings/
        Body: any subset of ConversationSettings fields.
        """
        conversation = self.get_object()
        if not user_is_active_member(request.user, conversation):
            return Response(
                {"detail": "You are not a member of this conversation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        settings_obj, _ = ConversationSettings.objects.get_or_create(
            conversation=conversation
        )
        serializer = ConversationSettingsSerializer(
            settings_obj,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    # ---------------------------------------------------------------------
    # Direct message request: accept / reject
    # ---------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='accept-request')
    def accept_request(self, request, pk=None):
        """
        POST /api/chat/conversations/{id}/accept-request/

        Used by the recipient of a direct message request to accept it.
        After acceptance, the conversation behaves like a normal direct chat.
        """
        conversation = self.get_object()

        if conversation.type != ConversationType.DIRECT:
            return Response(
                {"detail": "Only direct conversations use the request workflow."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if conversation.request_state != ConversationRequestState.PENDING:
            return Response(
                {"detail": "This conversation is not in pending state."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only the designated recipient may accept
        if conversation.request_recipient_id != request.user.id:
            return Response(
                {"detail": "You are not the recipient of this request."},
                status=status.HTTP_403_FORBIDDEN,
            )

        conversation.request_state = ConversationRequestState.ACCEPTED
        conversation.request_accepted_at = timezone.now()
        conversation.save(update_fields=['request_state', 'request_accepted_at'])

        ser = ConversationDetailSerializer(conversation)
        return Response(ser.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reject-request')
    def reject_request(self, request, pk=None):
        """
        POST /api/chat/conversations/{id}/reject-request/

        Used by the recipient of a direct message request to reject it.
        You can also extend this to block the sender at the membership/RBAC level.
        """
        conversation = self.get_object()

        if conversation.type != ConversationType.DIRECT:
            return Response(
                {"detail": "Only direct conversations use the request workflow."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if conversation.request_state != ConversationRequestState.PENDING:
            return Response(
                {"detail": "This conversation is not in pending state."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if conversation.request_recipient_id != request.user.id:
            return Response(
                {"detail": "You are not the recipient of this request."},
                status=status.HTTP_403_FORBIDDEN,
            )

        conversation.request_state = ConversationRequestState.REJECTED
        conversation.request_rejected_at = timezone.now()
        conversation.save(update_fields=['request_state', 'request_rejected_at'])

        # OPTIONAL: also block the initiator in this conversation
        # try:
        #     initiator_member = conversation.memberships.get(
        #         user_id=conversation.request_initiator_id
        #     )
        #     initiator_member.is_blocked = True
        #     initiator_member.save(update_fields=['is_blocked'])
        # except ConversationMember.DoesNotExist:
        #     pass

        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageThreadLinkViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/chat/threads/

    Used to create and inspect thread links:
    - parent_conversation + parent_message_key -> child_conversation
    """
    queryset = MessageThreadLink.objects.all()
    serializer_class = MessageThreadLinkSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        # Ensure user is member of parent_conversation
        parent_conversation = serializer.validated_data['parent_conversation']
        request = self.request
        if not user_is_active_member(request.user, parent_conversation):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You are not a member of the parent conversation.")

        serializer.save(created_by=request.user)
