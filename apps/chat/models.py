# chat/models.py
import uuid
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from apps.accounts.models import User


# ---------------------------------------------------------------------------
# Conversation & Membership
# ---------------------------------------------------------------------------

class ConversationType(models.TextChoices):
    DIRECT = 'direct', 'Direct (1:1)'
    GROUP = 'group', 'Group'
    CHANNEL = 'channel', 'Channel'
    POST = 'post', 'Post'
    THREAD = 'thread', 'Thread / Sub-room'
    SYSTEM = 'system', 'System/Internal'


class ConversationRequestState(models.TextChoices):
    NONE = 'none', 'Not a request'
    PENDING = 'pending', 'Pending acceptance'
    ACCEPTED = 'accepted', 'Accepted'
    REJECTED = 'rejected', 'Rejected / blocked'


class ConversationSendPolicy(models.TextChoices):
    ALL_MEMBERS = 'all_members', 'All members can send'
    ADMINS_ONLY = 'admins_only', 'Only admins/owners can send'


class ConversationJoinPolicy(models.TextChoices):
    INVITE_ONLY = 'invite_only', 'Invite only'
    LINK_JOIN = 'link_join', 'Join via share link'
    OPEN = 'open', 'Anyone within parent scope'


class ConversationInfoEditPolicy(models.TextChoices):
    ADMINS_ONLY = 'admins_only', 'Only admins/owners can edit'
    ALL_MEMBERS = 'all_members', 'All members can edit'


class ConversationSubroomPolicy(models.TextChoices):
    ADMINS_ONLY = 'admins_only', 'Only admins/owners can create sub-rooms'
    ALL_MEMBERS = 'all_members', 'Any member can create sub-rooms'


class Conversation(models.Model):
    """
    Universal chat room. Higher-level models (Group, Channel, Community, etc.)
    attach to this via FK/OneToOne.

    Messages themselves live in Mongo via NestJS; this just describes the room.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    type = models.CharField(
        max_length=16,
        choices=ConversationType.choices,
        default=ConversationType.DIRECT,
        db_index=True,
    )

    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Display name for group/channel/thread. Optional for direct chats.",
    )

    description = models.TextField(
        blank=True,
        help_text="Longer description / about text for this conversation.",
    )

    avatar_url = models.URLField(
        blank=True,
        help_text="Optional URL for conversation avatar (group/channel icon).",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='conversations_created',
    )

    request_state = models.CharField(
        max_length=16,
        choices=ConversationRequestState.choices,
        default=ConversationRequestState.NONE,
        db_index=True,
        help_text="Direct chat request workflow state.",
    )
    request_initiator = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='dm_requests_initiated',
        help_text="User who sent the first message / initiated the direct chat request.",
    )
    request_recipient = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='dm_requests_received',
        help_text="User who receives the direct chat request.",
    )
    request_accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the recipient accepted the request (or replied).",
    )
    request_rejected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the recipient rejected/blocked the request.",
    )

    is_archived = models.BooleanField(default=False, db_index=True)
    is_locked = models.BooleanField(
        default=False,
        help_text="When locked, only admins/owners may send messages (plus send_policy).",
    )

    # Denormalized activity metadata for fast chat list queries
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp of the last message in this conversation (from message service).",
    )
    last_message_preview = models.CharField(
        max_length=255,
        blank=True,
        help_text="Short preview of the last message for UI lists (optional, denormalized).",
    )

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chat_conversation'
        indexes = [
            models.Index(fields=['type', 'created_at']),
            models.Index(fields=['is_archived', 'last_message_at']),
        ]

    def __str__(self) -> str:
        return f"{self.get_type_display()}:{self.id}"


class BaseConversationRole(models.TextChoices):
    """
    Fast, handshake-level role for NestJS & front-end decisions.
    The full, flexible RBAC lives in RoleDefinition etc.
    """
    OWNER = 'owner', 'Owner'
    ADMIN = 'admin', 'Admin'
    MEMBER = 'member', 'Member'
    READONLY = 'readonly', 'Read-only'


class ConversationNotificationLevel(models.TextChoices):
    ALL = 'all', 'All messages'
    MENTIONS = 'mentions', 'Mentions only'
    NONE = 'none', 'No notifications'


class ConversationMember(models.Model):
    """
    Membership of a user in a conversation.

    - base_role is fast + WhatsApp-style.
    - role (FK RoleDefinition) can provide arbitrarily complex permissions.
    """
    id = models.BigAutoField(primary_key=True)

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='memberships',
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='conversation_memberships',
    )

    base_role = models.CharField(
        max_length=16,
        choices=BaseConversationRole.choices,
        default=BaseConversationRole.MEMBER,
    )

    # Per-conversation user settings
    display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional per-conversation nickname for this member.",
    )
    notification_level = models.CharField(
        max_length=16,
        choices=ConversationNotificationLevel.choices,
        default=ConversationNotificationLevel.ALL,
        help_text="Notification preference for this conversation.",
    )
    color = models.CharField(
        max_length=16,
        blank=True,
        help_text="Optional color/tag for UI (e.g. avatar color).",
    )

    is_muted = models.BooleanField(default=False)
    is_blocked = models.BooleanField(
        default=False,
        help_text="If true, user shouldn't receive messages from this conversation.",
    )

    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'chat_conversation_member'
        unique_together = [('conversation', 'user')]
        indexes = [
            models.Index(fields=['conversation', 'user']),
            models.Index(fields=['user', 'joined_at']),
            models.Index(fields=['conversation', 'base_role']),
            models.Index(fields=['user', 'notification_level']),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}@{self.conversation_id} ({self.base_role})"

    @property
    def is_active(self) -> bool:
        return self.left_at is None


class ConversationSettings(models.Model):
    """
    WhatsApp/Telegram-like group settings per conversation.
    These are enforced in the permission engine *after* role checks.
    """
    conversation = models.OneToOneField(
        Conversation,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='settings',
    )

    send_policy = models.CharField(
        max_length=32,
        choices=ConversationSendPolicy.choices,
        default=ConversationSendPolicy.ALL_MEMBERS,
    )
    join_policy = models.CharField(
        max_length=32,
        choices=ConversationJoinPolicy.choices,
        default=ConversationJoinPolicy.INVITE_ONLY,
    )
    info_edit_policy = models.CharField(
        max_length=32,
        choices=ConversationInfoEditPolicy.choices,
        default=ConversationInfoEditPolicy.ADMINS_ONLY,
    )
    subroom_policy = models.CharField(
        max_length=32,
        choices=ConversationSubroomPolicy.choices,
        default=ConversationSubroomPolicy.ALL_MEMBERS,
    )

    # Soft limit for nested sub-rooms depth (0 = top-level).
    max_subroom_depth = models.PositiveIntegerField(
        default=8,
        help_text="Soft limit for nested sub-rooms depth (0 = top-level).",
    )

    # Advanced feature toggles / policies
    message_retention_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "If set, messages older than this should be auto-deleted by the message service. "
            "Null means keep forever."
        ),
    )
    allow_reactions = models.BooleanField(
        default=True,
        help_text="Whether message reactions are allowed in this conversation.",
    )
    allow_stickers = models.BooleanField(
        default=True,
        help_text="Whether stickers are allowed in this conversation.",
    )
    allow_attachments = models.BooleanField(
        default=True,
        help_text="Whether file/media attachments are allowed in this conversation.",
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chat_conversation_settings'

    def __str__(self) -> str:
        return f"Settings for {self.conversation_id}"


# ---------------------------------------------------------------------------
# Threads / Sub-rooms
# ---------------------------------------------------------------------------

class MessageThreadLink(models.Model):
    """
    Links a message in one conversation to a child conversation (sub-room).
    - parent_conversation: where the message lives.
    - parent_message_key: message identifier (string from Nest/Mongo).
    - child_conversation: sub-room conversation.
    - depth: nesting depth for analytics/limits.
    - parent_thread: optional link if this thread is a sub-thread of another thread.
    """
    id = models.BigAutoField(primary_key=True)

    parent_conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='outgoing_threads',
    )
    parent_message_key = models.CharField(
        max_length=255,
        help_text="Message ID/key from the message storage (e.g., Mongo _id).",
    )

    child_conversation = models.OneToOneField(
        Conversation,
        on_delete=models.CASCADE,
        related_name='origin_message_thread',
    )

    parent_thread = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subthreads',
        help_text="If this thread is created from a message inside another thread.",
    )

    depth = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='threads_created',
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'chat_message_thread_link'
        unique_together = [
            ('parent_conversation', 'parent_message_key'),
        ]
        indexes = [
            models.Index(fields=['parent_conversation', 'parent_message_key']),
            models.Index(fields=['child_conversation']),
        ]

    def __str__(self) -> str:
        return f"Thread for msg={self.parent_message_key} in conv={self.parent_conversation_id}"


# ---------------------------------------------------------------------------
# RBAC: Permissions, Roles & Assignments
# ---------------------------------------------------------------------------

class RoleScopeType(models.TextChoices):
    GLOBAL = 'global', 'Global'
    PARTNER = 'partner', 'Partner'
    COMMUNITY = 'community', 'Community'
    CHANNEL = 'channel', 'Channel'
    GROUP = 'group', 'Group'
    CONVERSATION = 'conversation', 'Conversation'


class PermissionDefinition(models.Model):
    """
    Catalog of permission codes across the system.
    Example: chat.send_message, chat.add_member, chat.create_subroom
    """
    code = models.CharField(
        max_length=64,
        primary_key=True,
        help_text="Machine-readable permission code (e.g. chat.send_message).",
    )
    description = models.TextField(blank=True)
    category = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = 'rbac_permission_definition'

    def __str__(self) -> str:
        return self.code


class RoleDefinition(models.Model):
    """
    Logical role (Owner, Admin, Member, or any custom role).
    Scopes:
      - global: across whole platform
      - partner/community/channel/group/conversation: scoped roles.
    """
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=64)
    slug = models.SlugField(max_length=64)

    scope_type = models.CharField(
        max_length=32,
        choices=RoleScopeType.choices,
        default=RoleScopeType.CONVERSATION,
        db_index=True,
    )

    # If non-null, role is bound to a particular scope instance.
    # For conversation-scoped roles, we store conversation_id; for others, the scope_id.
    scope_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="ID of the scope instance (UUID or int, stored as string).",
    )

    is_system = models.BooleanField(
        default=False,
        help_text="If true, role is system-defined and cannot be deleted by users.",
    )
    is_default_for_scope = models.BooleanField(
        default=False,
        help_text="Used as auto-assign default role for new members in that scope.",
    )
    rank = models.IntegerField(
        default=100,
        help_text="Lower = more privileged, used for UI sorting & conflict resolution.",
    )

    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='roles_created',
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'rbac_role_definition'
        unique_together = [
            ('slug', 'scope_type', 'scope_id'),
        ]

    def __str__(self) -> str:
        return f"{self.scope_type}:{self.slug}"


class RolePermission(models.Model):
    """
    Mapping: Role -> Permission (allow/deny).
    """
    id = models.BigAutoField(primary_key=True)
    role = models.ForeignKey(
        RoleDefinition,
        on_delete=models.CASCADE,
        related_name='permissions',
    )
    permission = models.ForeignKey(
        PermissionDefinition,
        on_delete=models.CASCADE,
        related_name='role_bindings',
    )
    allowed = models.BooleanField(default=True)

    class Meta:
        db_table = 'rbac_role_permission'
        unique_together = [('role', 'permission')]


class PrincipalRole(models.Model):
    """
    Assigns a role to a user in a given scope.
    Example:
      - user U is 'owner' role in conversation C.
      - user U is 'admin' role in partner P.
    """
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='principal_roles',
    )
    role = models.ForeignKey(
        RoleDefinition,
        on_delete=models.CASCADE,
        related_name='principal_assignments',
    )

    # Redundant but helps with querying without joining RoleDefinition
    scope_type = models.CharField(
        max_length=32,
        choices=RoleScopeType.choices,
        db_index=True,
    )
    scope_id = models.CharField(
        max_length=64,
        help_text="ID of the scope instance as string; must match role.scope_id (if set).",
        db_index=True,
    )

    assigned_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'rbac_principal_role'
        indexes = [
            models.Index(fields=['user', 'scope_type', 'scope_id']),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.role_id} @ {self.scope_type}:{self.scope_id}"
