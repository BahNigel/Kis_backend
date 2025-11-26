# apps/partners/models.py
import uuid

from django.db import models
from django.utils import timezone

from apps.accounts.models import User
from apps.chat.models import Conversation


class Partner(models.Model):
    """
    Partner entity (e.g. organization, ministry, company).

    A Partner can own multiple Communities, Groups, Channels, etc.
    It can also have an optional main_conversation for partner-wide announcements/chat.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    avatar_url = models.URLField(
        blank=True,
        help_text="Optional logo/avatar URL for this partner.",
    )

    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="owned_partners",
        help_text="Primary owner of this partner.",
    )

    main_conversation = models.OneToOneField(
        Conversation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="partner_main",
        help_text="Optional main conversation for this partner (e.g. announcements).",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "partner_partner"

    def __str__(self) -> str:
        return self.name
