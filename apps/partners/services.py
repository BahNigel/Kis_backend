# apps/partners/services.py
from typing import Optional

from django.db import transaction

from apps.accounts.models import User
from apps.partners.models import Partner
from apps.chat.models import (
    Conversation,
    ConversationType,
    ConversationSettings,
    ConversationMember,
    BaseConversationRole,
)


@transaction.atomic
def create_partner_with_main_conversation(
    *,
    owner: User,
    name: str,
    slug: str,
    description: str = "",
    avatar_url: str = "",
    create_main_conversation: bool = True,
) -> Partner:
    """
    Service layer for creating a Partner and (optionally) its main conversation.
    """
    main_conversation = None

    if create_main_conversation:
        main_conversation = Conversation.objects.create(
            type=ConversationType.GROUP,  # or SYSTEM
            title=name,
            description=f"Main conversation for partner {name}",
            created_by=owner,
        )

        ConversationMember.objects.create(
            conversation=main_conversation,
            user=owner,
            base_role=BaseConversationRole.OWNER,
        )

        ConversationSettings.objects.create(conversation=main_conversation)

    partner = Partner.objects.create(
        name=name,
        slug=slug,
        description=description,
        avatar_url=avatar_url,
        owner=owner,
        main_conversation=main_conversation,
    )

    return partner
