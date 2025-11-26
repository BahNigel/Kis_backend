# chat/services.py
from typing import Tuple

from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from .models import (
    Conversation,
    ConversationMember,
    ConversationSettings,
    BaseConversationRole,
    ConversationType,
)


def get_or_create_direct_conversation(user_a: User, user_b: User) -> Tuple[Conversation, bool]:
    """
    ORIGINAL helper: Return an existing direct 1:1 conversation between user_a and user_b,
    or create a new one if none exists.
    """
    # Ensure deterministic ordering of the pair (for future caching, etc.)
    if user_a.id > user_b.id:
        user_a, user_b = user_b, user_a

    existing_qs = (
        Conversation.objects
        .filter(type=ConversationType.DIRECT)
        .filter(memberships__user=user_a, memberships__left_at__isnull=True)
        .filter(memberships__user=user_b, memberships__left_at__isnull=True)
        .distinct()
    )

    if existing_qs.exists():
        return existing_qs.first(), False

    with transaction.atomic():
        conversation = Conversation.objects.create(
            type=ConversationType.DIRECT,
            created_by=user_a,
        )
        # Ensure both members are added
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


def get_or_create_direct_conversation_with_request(
    user_a: User,
    user_b: User,
    initiator: User,
) -> Tuple[Conversation, bool]:
    """
    Extended helper used by your /api/chat/conversations/direct/ endpoint
    when we want:
      - a direct conversation between user_a and user_b
      - a *locked* conversation until receiver accepts / replies
      - two ConversationMember rows (sender + receiver)
    """
    # Ensure deterministic ordering
    if user_a.id > user_b.id:
        user_a, user_b = user_b, user_a

    existing_qs = (
        Conversation.objects
        .filter(type=ConversationType.DIRECT)
        .filter(memberships__user=user_a, memberships__left_at__isnull=True)
        .filter(memberships__user=user_b, memberships__left_at__isnull=True)
        .distinct()
    )

    if existing_qs.exists():
        return existing_qs.first(), False

    with transaction.atomic():
        # Locked by default → your policy says initiator can send "request"
        # but then cannot send again until receiver accepts / replies.
        conversation = Conversation.objects.create(
            type=ConversationType.DIRECT,
            created_by=initiator,
            is_locked=True,
        )

        # Decide roles: initiator as OWNER, peer as MEMBER
        if initiator.id == user_a.id:
            first_user = user_a
            second_user = user_b
        else:
            first_user = user_b
            second_user = user_a

        ConversationMember.objects.bulk_create([
            ConversationMember(
                conversation=conversation,
                user=first_user,
                base_role=BaseConversationRole.OWNER,
            ),
            ConversationMember(
                conversation=conversation,
                user=second_user,
                base_role=BaseConversationRole.MEMBER,
            ),
        ])

        # Default settings row
        ConversationSettings.objects.create(conversation=conversation)

        # OPTIONAL: if you later add a "ConversationRequest" model,
        # you can create the pending request here.

    return conversation, True


def user_is_active_member(user: User, conversation: Conversation) -> bool:
    return ConversationMember.objects.filter(
        conversation=conversation,
        user=user,
        left_at__isnull=True,
        is_blocked=False,
    ).exists()
