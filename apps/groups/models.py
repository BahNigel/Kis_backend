# apps/groups/models.py
import uuid

from django.db import models
from django.utils import timezone

from apps.accounts.models import User
from apps.chat.models import Conversation


class Group(models.Model):
    """
    High-level group entity.

    A Group:
    - Belongs optionally to a Partner and/or Community.
    - Has a backing Conversation (GROUP type) for actual chat.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Optional scoping to Partner or Community
    partner = models.ForeignKey(
        "partners.Partner",  # string to avoid tight coupling at import time
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="groups",
        help_text="Owning partner (optional).",
    )

    community = models.ForeignKey(
        "communities.Community",  # string reference
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="groups",
        help_text="Owning community (optional).",
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)

    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="owned_groups",
    )

    conversation = models.OneToOneField(
        Conversation,
        on_delete=models.CASCADE,
        related_name="group",
        help_text="The chat conversation backing this group.",
    )

    is_archived = models.BooleanField(
        default=False,
        help_text="Soft-archive the group (and usually its conversation).",
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "group_group"
        unique_together = [
            ("community", "slug"),
        ]

    def __str__(self) -> str:
        return self.name
