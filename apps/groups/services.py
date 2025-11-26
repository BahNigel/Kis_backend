# apps/groups/services.py
from typing import Optional

from django.db import transaction

from apps.accounts.models import User
from apps.chat.models import (
    Conversation,
    ConversationType,
    ConversationSettings,
    ConversationMember,
    BaseConversationRole,
)
from apps.groups.models import Group


@transaction.atomic
def create_group_with_conversation(
    *,
    owner: User,
    name: str,
    slug: str,
    partner=None,
    community=None,
) -> Group:
    """
    Service for creating a group with a backing Conversation and owner membership.
    """
    conversation = Conversation.objects.create(
        type=ConversationType.GROUP,
        title=name,
        created_by=owner,
    )

    ConversationMember.objects.create(
        conversation=conversation,
        user=owner,
        base_role=BaseConversationRole.OWNER,
    )

    ConversationSettings.objects.create(conversation=conversation)

    group = Group.objects.create(
        owner=owner,
        conversation=conversation,
        name=name,
        slug=slug,
        partner=partner,
        community=community,
    )
    return group
