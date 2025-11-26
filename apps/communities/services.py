# apps/communities/services.py
from django.db import transaction

from apps.accounts.models import User
from apps.partners.models import Partner
from apps.communities.models import Community
from apps.chat.models import (
    Conversation,
    ConversationType,
    ConversationSettings,
    ConversationMember,
    BaseConversationRole,
)


@transaction.atomic
def create_community_with_main_conversation(
    *,
    owner: User,
    partner: Partner,
    name: str,
    slug: str,
    description: str = "",
    avatar_url: str = "",
    create_main_conversation: bool = True,
) -> Community:
    """
    Service for creating a Community under a Partner, and optionally its main conversation.
    """
    main_conversation = None

    if create_main_conversation:
        main_conversation = Conversation.objects.create(
            type=ConversationType.GROUP,
            title=name,
            description=f"Main conversation for community {name}",
            created_by=owner,
        )

        ConversationMember.objects.create(
            conversation=main_conversation,
            user=owner,
            base_role=BaseConversationRole.OWNER,
        )

        ConversationSettings.objects.create(conversation=main_conversation)

    community = Community.objects.create(
        partner=partner,
        name=name,
        slug=slug,
        description=description,
        avatar_url=avatar_url,
        owner=owner,
        main_conversation=main_conversation,
    )

    return community
