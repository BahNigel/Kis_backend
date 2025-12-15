# chat/services.py
from typing import Tuple, Optional

from django.db import transaction

from apps.accounts.models import User
from .models import (
    Conversation,
    ConversationMember,
    ConversationSettings,
    BaseConversationRole,
    ConversationType,
    ConversationRequestState,
)


def _normalize_pair(user_a: User, user_b: User) -> tuple[User, User]:
    # deterministic ordering
    if user_a.id > user_b.id:
        return user_b, user_a
    return user_a, user_b


def _find_existing_direct(user_a: User, user_b: User) -> Optional[Conversation]:
    """
    Find existing DIRECT conversation where BOTH users are active members.
    """
    qs = (
        Conversation.objects
        .filter(type=ConversationType.DIRECT)
        .filter(memberships__user=user_a, memberships__left_at__isnull=True)
        .filter(memberships__user=user_b, memberships__left_at__isnull=True)
        .distinct()
    )
    return qs.first() if qs.exists() else None


def get_or_create_direct_conversation(
    user_a: User,
    user_b: User,
    initiator: Optional[User] = None,
    use_request_flow: bool = False,
) -> Tuple[Conversation, bool]:
    """
    Backward-compatible API.

    - Old callers: get_or_create_direct_conversation(user_a, user_b)
        -> creates a normal direct conversation (no request workflow)

    - New callers (your DM request system):
        get_or_create_direct_conversation(user_a, user_b, initiator=request.user, use_request_flow=True)
        -> creates a pending DM request conversation:
           request_state=PENDING, initiator/recipient set, locked by default.
    """
    user_a, user_b = _normalize_pair(user_a, user_b)

    existing = _find_existing_direct(user_a, user_b)
    if existing:
        return existing, False

    # If request flow is asked, initiator is required.
    if use_request_flow and initiator is None:
        initiator = user_a  # safe fallback, but you should pass initiator explicitly

    with transaction.atomic():
        if use_request_flow:
            if initiator.id not in (user_a.id, user_b.id):
                # initiator must be one of the participants
                initiator = user_a

            recipient = user_b if initiator.id == user_a.id else user_a

            conversation = Conversation.objects.create(
                type=ConversationType.DIRECT,
                created_by=initiator,
                is_locked=True,  # optional, but aligns with your “pending request” UX
                request_state=ConversationRequestState.PENDING,
                request_initiator=initiator,
                request_recipient=recipient,
            )

            # Roles: initiator is OWNER, recipient MEMBER (fast WhatsApp-like)
            ConversationMember.objects.bulk_create([
                ConversationMember(
                    conversation=conversation,
                    user=initiator,
                    base_role=BaseConversationRole.OWNER,
                ),
                ConversationMember(
                    conversation=conversation,
                    user=recipient,
                    base_role=BaseConversationRole.MEMBER,
                ),
            ])

        else:
            # classic direct conversation (no request workflow)
            conversation = Conversation.objects.create(
                type=ConversationType.DIRECT,
                created_by=user_a,
            )
            ConversationMember.objects.bulk_create([
                ConversationMember(
                    conversation=conversation,
                    user=user_a,
                    base_role=BaseConversationRole.OWNER,
                ),
                ConversationMember(
                    conversation=conversation,
                    user=user_b,
                    base_role=BaseConversationRole.MEMBER,
                ),
            ])

        ConversationSettings.objects.create(conversation=conversation)

    return conversation, True


def user_is_active_member(user: User, conversation: Conversation) -> bool:
    return ConversationMember.objects.filter(
        conversation=conversation,
        user=user,
        left_at__isnull=True,
        is_blocked=False,
    ).exists()
