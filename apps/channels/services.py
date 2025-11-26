# apps/channels/services.py
from django.db import transaction

from apps.accounts.models import User
from apps.channels.models import Channel
from apps.chat.models import (
    Conversation,
    ConversationType,
    ConversationSettings,
    ConversationMember,
    BaseConversationRole,
    ConversationSendPolicy,
)


@transaction.atomic
def create_channel_with_conversation(
    *,
    owner: User,
    name: str,
    slug: str,
    description: str = "",
    avatar_url: str = "",
    partner=None,
    community=None,
) -> Channel:
    """
    Service for creating a Channel with a backing Conversation and owner membership.
    """
    conversation = Conversation.objects.create(
        type=ConversationType.CHANNEL,
        title=name,
        description=description,
        avatar_url=avatar_url,
        created_by=owner,
    )

    ConversationMember.objects.create(
        conversation=conversation,
        user=owner,
        base_role=BaseConversationRole.OWNER,
    )

    ConversationSettings.objects.create(
        conversation=conversation,
        send_policy=ConversationSendPolicy.ADMINS_ONLY,
    )

    channel = Channel.objects.create(
        owner=owner,
        conversation=conversation,
        name=name,
        slug=slug,
        description=description,
        avatar_url=avatar_url,
        partner=partner,
        community=community,
    )

    return channel
