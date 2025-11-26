# apps/channels/models.py
import uuid

from django.db import models
from django.utils import timezone

from apps.accounts.models import User
from apps.chat.models import Conversation


class Channel(models.Model):
    """
    Channel entity (broadcast-like or topic-based stream).

    - Can belong to a Partner and/or Community.
    - Backed by a Conversation of type CHANNEL.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    partner = models.ForeignKey(
        "partners.Partner",  # string ref: avoids circular import issues
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="channels",
        help_text="Owning partner (optional).",
    )

    community = models.ForeignKey(
        "communities.Community",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="channels",
        help_text="Owning community (optional).",
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)

    avatar_url = models.URLField(
        blank=True,
        help_text="Optional avatar / icon for this channel.",
    )

    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="owned_channels",
    )

    conversation = models.OneToOneField(
        Conversation,
        on_delete=models.CASCADE,
        related_name="channel",
        help_text="The chat conversation backing this channel.",
    )

    is_archived = models.BooleanField(
        default=False,
        help_text="Soft-archive the channel (and usually its conversation).",
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "channel_channel"
        unique_together = [
            ("community", "slug"),
        ]

    def __str__(self) -> str:
        return self.name
