# apps/communities/models.py
import uuid
from django.db import models
from django.utils import timezone

from apps.accounts.models import User
from apps.chat.models import Conversation


class Community(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    partner = models.ForeignKey(
        "partners.Partner",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="communities",
    )

    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="communities_owned",
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    avatar_url = models.URLField(blank=True)

    is_active = models.BooleanField(default=True)

    # existing main chat / lobby
    main_conversation = models.OneToOneField(
        Conversation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="community_main",
    )

    # 🔥 NEW: posts / feed conversation for the community
    posts_conversation = models.OneToOneField(
        Conversation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="community_posts",
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "kis_community"  # or whatever you already use

    def __str__(self) -> str:
        return self.name
