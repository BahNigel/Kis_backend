# apps/groups/models.py
import uuid

from django.db import models
from django.utils import timezone

from apps.accounts.models import User
from apps.chat.models import Conversation


class GroupJoinPolicy(models.TextChoices):
    OPEN = "open", "Open"
    REQUEST = "request", "Request approval"
    INVITE_ONLY = "invite_only", "Invite only"


class GroupRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MOD = "mod", "Moderator"
    MEMBER = "member", "Member"


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

    channel = models.ForeignKey(
        "channels.Channel",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="groups",
        help_text="Owning channel (optional).",
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

    join_policy = models.CharField(
        max_length=16,
        choices=GroupJoinPolicy.choices,
        default=GroupJoinPolicy.REQUEST,
        db_index=True,
    )
    allow_media = models.BooleanField(default=True)
    allow_polls = models.BooleanField(default=True)
    allow_events = models.BooleanField(default=True)
    allow_links = models.BooleanField(default=True)
    require_post_approval = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "group_group"
        unique_together = [
            ("community", "slug"),
        ]

    def __str__(self) -> str:
        return self.name


class GroupMembership(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )
    role = models.CharField(
        max_length=16,
        choices=GroupRole.choices,
        default=GroupRole.MEMBER,
    )
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)
    is_banned = models.BooleanField(default=False)

    class Meta:
        db_table = "group_membership"
        unique_together = [("group", "user")]
        indexes = [
            models.Index(fields=["group", "user"]),
            models.Index(fields=["user", "joined_at"]),
        ]

    @property
    def is_active(self) -> bool:
        return self.left_at is None and not self.is_banned


class GroupJoinRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class GroupJoinRequest(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="join_requests",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="group_join_requests",
    )
    message = models.CharField(max_length=500, blank=True)
    status = models.CharField(
        max_length=16,
        choices=GroupJoinRequestStatus.choices,
        default=GroupJoinRequestStatus.PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="group_join_requests_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "group_join_request"
        unique_together = [("group", "user")]
        indexes = [
            models.Index(fields=["group", "status"]),
        ]


class GroupBan(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="bans",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="group_bans",
    )
    reason = models.CharField(max_length=500, blank=True)
    banned_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="group_bans_made",
    )
    banned_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "group_ban"
        unique_together = [("group", "user")]
        indexes = [
            models.Index(fields=["group", "user"]),
        ]
