# apps/communities/models.py
import uuid
from django.db import models
from django.utils import timezone

from apps.accounts.models import User
from apps.chat.models import Conversation


class CommunityVisibility(models.TextChoices):
    PUBLIC = "public", "Public"
    PRIVATE = "private", "Private"
    HIDDEN = "hidden", "Hidden"


class CommunityJoinPolicy(models.TextChoices):
    OPEN = "open", "Open"
    REQUEST = "request", "Request approval"
    INVITE_ONLY = "invite_only", "Invite only"


class CommunityPostPolicy(models.TextChoices):
    ALL_MEMBERS = "all_members", "All members"
    ADMINS_ONLY = "admins_only", "Admins only"
    MODS_ONLY = "mods_only", "Moderators and admins"


class CommunityRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MOD = "mod", "Moderator"
    MEMBER = "member", "Member"


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

    visibility = models.CharField(
        max_length=16,
        choices=CommunityVisibility.choices,
        default=CommunityVisibility.PUBLIC,
        db_index=True,
    )
    join_policy = models.CharField(
        max_length=16,
        choices=CommunityJoinPolicy.choices,
        default=CommunityJoinPolicy.REQUEST,
        db_index=True,
    )
    post_policy = models.CharField(
        max_length=16,
        choices=CommunityPostPolicy.choices,
        default=CommunityPostPolicy.ALL_MEMBERS,
    )
    allow_comments = models.BooleanField(default=True)
    allow_reactions = models.BooleanField(default=True)
    allow_media = models.BooleanField(default=True)
    allow_polls = models.BooleanField(default=True)
    allow_events = models.BooleanField(default=True)
    allow_links = models.BooleanField(default=True)
    require_post_approval = models.BooleanField(default=False)

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


class CommunityMembership(models.Model):
    id = models.BigAutoField(primary_key=True)
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="community_memberships",
    )
    role = models.CharField(
        max_length=16,
        choices=CommunityRole.choices,
        default=CommunityRole.MEMBER,
    )
    can_access_all_groups = models.BooleanField(
        default=False,
        help_text="If true, member can access all groups in the community.",
    )
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)
    is_banned = models.BooleanField(default=False)

    class Meta:
        db_table = "community_membership"
        unique_together = [("community", "user")]
        indexes = [
            models.Index(fields=["community", "user"]),
            models.Index(fields=["user", "joined_at"]),
        ]

    @property
    def is_active(self) -> bool:
        return self.left_at is None and not self.is_banned


class CommunityJoinRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class CommunityJoinRequest(models.Model):
    id = models.BigAutoField(primary_key=True)
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="join_requests",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="community_join_requests",
    )
    message = models.CharField(max_length=500, blank=True)
    status = models.CharField(
        max_length=16,
        choices=CommunityJoinRequestStatus.choices,
        default=CommunityJoinRequestStatus.PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="community_join_requests_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "community_join_request"
        unique_together = [("community", "user")]
        indexes = [
            models.Index(fields=["community", "status"]),
        ]


class CommunityBan(models.Model):
    id = models.BigAutoField(primary_key=True)
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="bans",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="community_bans",
    )
    reason = models.CharField(max_length=500, blank=True)
    banned_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="community_bans_made",
    )
    banned_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "community_ban"
        unique_together = [("community", "user")]
        indexes = [
            models.Index(fields=["community", "user"]),
        ]


class CommunityPostStatus(models.TextChoices):
    PUBLISHED = "published", "Published"
    PENDING = "pending", "Pending approval"
    REJECTED = "rejected", "Rejected"


class CommunityPost(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="community_posts",
    )
    text = models.TextField(blank=True)
    styled_text = models.JSONField(default=dict, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    poll = models.JSONField(default=dict, blank=True)
    event = models.JSONField(default=dict, blank=True)
    link = models.URLField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=CommunityPostStatus.choices,
        default=CommunityPostStatus.PUBLISHED,
        db_index=True,
    )
    is_pinned = models.BooleanField(default=False)
    pinned_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="community_posts_pinned",
    )
    pinned_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "community_post"
        indexes = [
            models.Index(fields=["community", "created_at"]),
            models.Index(fields=["community", "status"]),
            models.Index(fields=["community", "is_pinned"]),
        ]


class CommunityPostComment(models.Model):
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(
        CommunityPost,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="community_post_comments",
    )
    text = models.TextField()
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "community_post_comment"
        indexes = [
            models.Index(fields=["post", "created_at"]),
        ]


class CommunityPostReaction(models.Model):
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(
        CommunityPost,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="community_post_reactions",
    )
    emoji = models.CharField(max_length=32)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "community_post_reaction"
        unique_together = [("post", "user")]
        indexes = [
            models.Index(fields=["post", "created_at"]),
        ]


class CommunityCommentReaction(models.Model):
    id = models.BigAutoField(primary_key=True)
    comment = models.ForeignKey(
        CommunityPostComment,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="community_comment_reactions",
    )
    emoji = models.CharField(max_length=32)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "community_comment_reaction"
        unique_together = [("comment", "user")]
        indexes = [
            models.Index(fields=["comment", "created_at"]),
        ]
