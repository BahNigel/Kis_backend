import uuid
from typing import Iterable, Optional, Set, List, Dict

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.db.models import Q, UniqueConstraint
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

# Use JSONField from Django (3.1+)
JSONField = models.JSONField


# ---------------------------
# Base entity (audit fields)
# ---------------------------
class BaseEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ---------------------------
# Permission, Role, RoleAssignment, ACE (scoped)
# ---------------------------
class Permission(BaseEntity):
    """
    Canonical permission codename (e.g. "group.post", "group.invite", "channel.create_thread").
    Keep a unique codename and optional description for admin UIs.
    """
    codename = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "core_permission"
        ordering = ("codename",)

    def __str__(self):
        return self.codename


class Role(BaseEntity):
    """
    Role is a named collection of permissions. Roles can be global or scoped by an intended
    'scope' string (e.g., "GROUP", "COMMUNITY", "CHANNEL") to clarify usage.
    """
    SCOPE_GROUP = "GROUP"
    SCOPE_COMMUNITY = "COMMUNITY"
    SCOPE_CHANNEL = "CHANNEL"
    SCOPE_GLOBAL = "GLOBAL"

    SCOPE_CHOICES = [
        (SCOPE_GLOBAL, "Global"),
        (SCOPE_COMMUNITY, "Community"),
        (SCOPE_GROUP, "Group"),
        (SCOPE_CHANNEL, "Channel"),
    ]

    name = models.CharField(max_length=128)
    scope = models.CharField(max_length=32, choices=SCOPE_CHOICES, default=SCOPE_GLOBAL)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True, related_name="roles")
    parent_role = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="child_roles")
    is_default = models.BooleanField(default=False, help_text="Auto-assigned role for new members in a scope")

    class Meta:
        db_table = "core_role"
        unique_together = (("name", "scope"),)

    def __str__(self):
        return f"{self.scope}:{self.name}"

    def clean(self):
        # prevent cycles in parent_role
        p = self.parent_role
        visited = set()
        while p:
            if p.id == self.id:
                raise ValidationError("Role parent chain would create a cycle.")
            if p.id in visited:
                break
            visited.add(p.id)
            p = p.parent_role

    def all_permissions(self) -> Set[str]:
        """
        Return a set of permission codenames from this role and its parent chain.
        """
        perms: Set[str] = set()
        node = self
        visited = set()
        while node and node.id not in visited:
            visited.add(node.id)
            perms.update(node.permissions.values_list("codename", flat=True))
            node = node.parent_role
        return perms


class RoleAssignment(BaseEntity):
    """
    Assign a Role to a principal (user, team, service account, etc). Can be optionally
    scoped to a target object (Community/Group/Channel) via GenericForeignKey.
    - principal_content_type / principal_object_id : who gets the role
    - target_content_type / target_object_id : optional object the role applies to
    """
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="assignments")

    principal_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="+")
    principal_object_id = models.CharField(max_length=255)
    principal = GenericForeignKey("principal_content_type", "principal_object_id")

    target_content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    target_object_id = models.CharField(max_length=255, null=True, blank=True)
    target = GenericForeignKey("target_content_type", "target_object_id")

    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "core_role_assignment"
        indexes = [
            models.Index(fields=["principal_content_type", "principal_object_id"]),
            models.Index(fields=["target_content_type", "target_object_id"]),
        ]

    def is_active(self) -> bool:
        return not (self.expires_at and timezone.now() > self.expires_at)


class AccessControlEntry(BaseEntity):
    """
    Fine-grained allow/deny (ACE) for a principal on a target object.
    - principal: user/role/team/public (represented via ContentType or NULL for PUBLIC)
    - target: any object (Community/Group/Channel) or NULL for global
    - permissions: list of permission codenames.
    Deny entries override allows when evaluating permissions.
    """
    EFFECT_ALLOW = "ALLOW"
    EFFECT_DENY = "DENY"
    EFFECT_CHOICES = [(EFFECT_ALLOW, "Allow"), (EFFECT_DENY, "Deny")]

    principal_content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    principal_object_id = models.CharField(max_length=255, null=True, blank=True)
    principal = GenericForeignKey("principal_content_type", "principal_object_id")

    target_content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    target_object_id = models.CharField(max_length=255, null=True, blank=True)
    target = GenericForeignKey("target_content_type", "target_object_id")

    permissions = JSONField(default=list)  # list[str]
    effect = models.CharField(max_length=8, choices=EFFECT_CHOICES, default=EFFECT_ALLOW)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "core_ace"
        indexes = [
            models.Index(fields=["principal_content_type", "principal_object_id"]),
            models.Index(fields=["target_content_type", "target_object_id"]),
        ]

    def clean(self):
        if not isinstance(self.permissions, list):
            raise ValidationError("permissions must be a list of codename strings.")
        self.permissions = sorted(set(map(str, self.permissions)))

    def is_active(self) -> bool:
        return not (self.expires_at and timezone.now() > self.expires_at)


# ---------------------------
# Core domain models: Community, Group, Channel
# ---------------------------
class Community(BaseEntity):
    """
    A Community is a top-level collection which may contain multiple Groups.
    Visibility controls who can discover/join.
    """
    VISIBILITY_PUBLIC = "PUBLIC"
    VISIBILITY_PRIVATE = "PRIVATE"
    VISIBILITY_HIDDEN = "HIDDEN"  # discoverable only by invite or direct link

    VISIBILITY_CHOICES = [
        (VISIBILITY_PUBLIC, "Public"),
        (VISIBILITY_PRIVATE, "Private"),
        (VISIBILITY_HIDDEN, "Hidden"),
    ]

    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    owner_content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    owner_object_id = models.CharField(max_length=255, null=True, blank=True)
    owner = GenericForeignKey("owner_content_type", "owner_object_id")  # optional owner (user or org)
    visibility = models.CharField(max_length=16, choices=VISIBILITY_CHOICES, default=VISIBILITY_PUBLIC)
    metadata = JSONField(default=dict, blank=True)  # arbitrary metadata
    archived = models.BooleanField(default=False, help_text="If archived, new activity is restricted.")

    class Meta:
        db_table = "core_community"
        indexes = [models.Index(fields=["slug"]), models.Index(fields=["archived"])]

    def __str__(self):
        return self.name

    def active_groups(self):
        return self.groups.filter(archived=False)

    def add_group(self, group):
        group.community = self
        group.save()


class Group(BaseEntity):
    """
    Group may exist standalone or inside a Community (community nullable).
    It represents the primary membership & discussion unit.
    """
    slug = models.SlugField(max_length=64)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    community = models.ForeignKey(Community, null=True, blank=True, on_delete=models.CASCADE, related_name="groups")
    is_public = models.BooleanField(default=True, help_text="If false, group is invite-only or request-only depending on membership settings.")
    archived = models.BooleanField(default=False)
    # Basic aggregated counters for fast queries (maintain via signals or code)
    member_count = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    metadata = JSONField(default=dict, blank=True)

    class Meta:
        db_table = "core_group"
        unique_together = (("community", "slug"),)
        indexes = [models.Index(fields=["community", "slug"]), models.Index(fields=["archived"])]

    def __str__(self):
        return self.name

    def recalc_member_count(self):
        self.member_count = self.memberships.filter(status=Membership.STATUS_ACTIVE).count()
        self.save(update_fields=["member_count"])

    def is_member(self, user) -> bool:
        return self.memberships.filter(user_content_type=ContentType.objects.get_for_model(user.__class__),
                                       user_object_id=str(user.pk),
                                       status=Membership.STATUS_ACTIVE).exists()

    def can_user(self, user, permission_codename: str) -> bool:
        """
        High-level helper: checks whether a user has given permission on this Group.
        This checks:
         - role assignments that target this group
         - ACEs targeted to this group (deny overrides)
         - membership-specific role/permissions
         - member is owner/superuser
        """
        # quick superuser check
        if getattr(user, "is_superuser", False):
            return True

        # 1) membership role checks
        try:
            m = self.memberships.get(user_content_type=ContentType.objects.get_for_model(user.__class__),
                                     user_object_id=str(user.pk),
                                     status=Membership.STATUS_ACTIVE)
        except Membership.DoesNotExist:
            m = None

        if m:
            # evaluate membership role's permissions if assigned
            if m.role and permission_codename in m.role.all_permissions():
                return True

        # 2) role assignments to user scoped to this group
        role_ct = ContentType.objects.get_for_model(Role)
        user_ct = ContentType.objects.get_for_model(user.__class__)
        assigned_role_ids = RoleAssignment.objects.filter(
            principal_content_type=user_ct,
            principal_object_id=str(user.pk),
            target_content_type=ContentType.objects.get_for_model(self.__class__),
            target_object_id=str(self.pk),
            role__isnull=False,
            expires_at__isnull=True
        ).values_list("role_id", flat=True)
        if assigned_role_ids:
            roles = Role.objects.filter(id__in=assigned_role_ids)
            for r in roles:
                if permission_codename in r.all_permissions():
                    return True

        # 3) ACEs
        now = timezone.now()
        # principal candidates: user, roles assigned to user, public
        principals = []
        principals.append((user_ct, str(user.pk)))
        # include role principals by role assignments to user (global or targetless)
        role_asgs = RoleAssignment.objects.filter(principal_content_type=user_ct, principal_object_id=str(user.pk))
        for ra in role_asgs:
            principals.append((ContentType.objects.get_for_model(Role), str(ra.role_id)))
        principals.append((None, "PUBLIC"))

        # collect ACEs that apply to this group: exact target, type-wide, or global
        ace_q = Q()
        p_q = Q()
        for ct, pid in principals:
            if ct is None:
                p_q |= (Q(principal_content_type__isnull=True) & Q(principal_object_id="PUBLIC"))
            else:
                p_q |= (Q(principal_content_type=ct) & Q(principal_object_id=str(pid)))
        ace_q &= p_q

        ace_q &= (
            Q(target_content_type=ContentType.objects.get_for_model(self.__class__), target_object_id=str(self.pk))
            | (Q(target_content_type=ContentType.objects.get_for_model(self.__class__)) & Q(target_object_id__isnull=True))
            | (Q(target_content_type__isnull=True) & Q(target_object_id__isnull=True))
        )
        ace_q &= (Q(expires_at__isnull=True) | Q(expires_at__gt=now))

        aces = AccessControlEntry.objects.filter(ace_q)
        denies = set()
        allows = set()
        for ace in aces:
            perms = set(ace.permissions or [])
            if ace.effect == AccessControlEntry.EFFECT_DENY:
                denies.update(perms)
            else:
                allows.update(perms)

        if permission_codename in denies:
            return False
        if permission_codename in allows:
            return True

        return False  # default deny


class Channel(BaseEntity):
    """
    Channel: content spaces that can be linked to multiple Communities and/or multiple Groups.
    Channels can be public or private; they are often used for topic-based discussion within groups/communities.
    """
    slug = models.SlugField(max_length=64)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)
    archived = models.BooleanField(default=False)
    # A channel can belong to many communities and many groups (many-to-many)
    communities = models.ManyToManyField(Community, blank=True, related_name="channels")
    groups = models.ManyToManyField(Group, blank=True, related_name="channels")
    metadata = JSONField(default=dict, blank=True)

    class Meta:
        db_table = "core_channel"
        unique_together = (("slug",),)
        indexes = [models.Index(fields=["slug"]), models.Index(fields=["archived"])]

    def __str__(self):
        return self.name

    def can_user(self, user, permission_codename: str) -> bool:
        """
        Composite permission check for channels. A user can gain permission through:
         - membership/role in any linked group/community
         - channel role assignments / ACEs
         - global roles
         - superuser bypass
        Deny ACEs take precedence.
        """
        if getattr(user, "is_superuser", False):
            return True

        # collect principals and check ACEs that target channel specifically
        user_ct = ContentType.objects.get_for_model(user.__class__)
        principals = [(user_ct, str(user.pk))]
        # roles assigned directly to user
        for ra in RoleAssignment.objects.filter(principal_content_type=user_ct, principal_object_id=str(user.pk)):
            principals.append((ContentType.objects.get_for_model(Role), str(ra.role_id)))
        principals.append((None, "PUBLIC"))

        now = timezone.now()
        # ACEs on channel:
        ace_q = Q()
        p_q = Q()
        for ct, pid in principals:
            if ct is None:
                p_q |= (Q(principal_content_type__isnull=True) & Q(principal_object_id="PUBLIC"))
            else:
                p_q |= (Q(principal_content_type=ct) & Q(principal_object_id=str(pid)))
        ace_q &= p_q
        ace_q &= (
            Q(target_content_type=ContentType.objects.get_for_model(self.__class__), target_object_id=str(self.pk))
            | (Q(target_content_type=ContentType.objects.get_for_model(self.__class__)) & Q(target_object_id__isnull=True))
            | (Q(target_content_type__isnull=True) & Q(target_object_id__isnull=True))
        )
        ace_q &= (Q(expires_at__isnull=True) | Q(expires_at__gt=now))

        aces = AccessControlEntry.objects.filter(ace_q)
        denies = set()
        allows = set()
        for ace in aces:
            perms = set(ace.permissions or [])
            if ace.effect == AccessControlEntry.EFFECT_DENY:
                denies.update(perms)
            else:
                allows.update(perms)

        if permission_codename in denies:
            return False
        if permission_codename in allows:
            return True

        # fallback: if the user has the permission in any linked group/community
        # Check group membership roles
        user_ct = ContentType.objects.get_for_model(user.__class__)
        group_qs = self.groups.all()
        for g in group_qs:
            if g.can_user(user, permission_codename):
                return True
        for c in self.communities.all():
            # check community-level role assignments/aces similarly (reuse Group.can_user pattern adapted)
            # simple default: community owner or community-level roles might grant permission
            # For brevity, check RoleAssignment + ACEs for community like Group.can_user implementation
            # (implementation mirrored from Group.can_user if required)
            if CommunityPermissionHelper.can_user_on_community(user, c, permission_codename):
                return True

        return False


# ---------------------------
# Memberships, Invites, Requests, Moderation
# ---------------------------
class Membership(BaseEntity):
    """
    Membership of a User in a Group.
    The user is represented with GenericForeignKey to support different principal types (user, service account).
    Role is optional (e.g., moderator, member).
    """
    STATUS_ACTIVE = "ACTIVE"
    STATUS_PENDING = "PENDING"  # e.g., awaiting approval
    STATUS_INVITED = "INVITED"
    STATUS_BANNED = "BANNED"
    STATUS_LEFT = "LEFT"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_PENDING, "Pending"),
        (STATUS_INVITED, "Invited"),
        (STATUS_BANNED, "Banned"),
        (STATUS_LEFT, "Left"),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    user_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="+")
    user_object_id = models.CharField(max_length=255)
    user = GenericForeignKey("user_content_type", "user_object_id")

    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL, related_name="memberships")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    joined_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)  # for temporary memberships
    is_moderator = models.BooleanField(default=False)
    preferences = JSONField(default=dict, blank=True)  # per-member settings (notifications, etc)

    class Meta:
        db_table = "core_membership"
        indexes = [
            models.Index(fields=["group", "status"]),
            models.Index(fields=["user_content_type", "user_object_id"]),
        ]
        constraints = [
            UniqueConstraint(fields=["group", "user_content_type", "user_object_id"], name="unique_group_user_membership")
        ]

    def is_active(self) -> bool:
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def promote_to_role(self, role: Role):
        self.role = role
        self.is_moderator = "moderator" in role.name.lower() or role.scope == Role.SCOPE_GROUP
        self.save(update_fields=["role", "is_moderator"])

    def demote(self):
        self.role = None
        self.is_moderator = False
        self.save(update_fields=["role", "is_moderator"])


class MembershipInvite(BaseEntity):
    """
    Invite token issued by a group/community for a principal to join.
    """
    token = models.CharField(max_length=128, unique=True)
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.CASCADE, related_name="invites")
    community = models.ForeignKey(Community, null=True, blank=True, on_delete=models.CASCADE, related_name="invites")
    created_by_content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_by_object_id = models.CharField(max_length=255, null=True, blank=True)
    created_by = GenericForeignKey("created_by_content_type", "created_by_object_id")
    expires_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)  # None = unlimited
    uses = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "core_membership_invite"

    def is_valid(self) -> bool:
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.max_uses is not None and self.uses >= self.max_uses:
            return False
        return True

    def use(self):
        if not self.is_valid():
            raise ValidationError("Invite is no longer valid")
        self.uses += 1
        self.save(update_fields=["uses"])


class MembershipRequest(BaseEntity):
    """
    A user requests to join a group (if group is request-only).
    """
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="join_requests")
    user_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="+")
    user_object_id = models.CharField(max_length=255)
    user = GenericForeignKey("user_content_type", "user_object_id")
    message = models.TextField(blank=True)
    reviewed_by_content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_by_object_id = models.CharField(max_length=255, null=True, blank=True)
    reviewed_by = GenericForeignKey("reviewed_by_content_type", "reviewed_by_object_id")
    status = models.CharField(max_length=16, choices=[
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected")
    ], default="PENDING")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "core_membership_request"
        indexes = [models.Index(fields=["group", "status"])]


class ModerationAction(BaseEntity):
    """
    Records moderation actions (ban, mute, remove post, warn, etc.) applied by moderators/admins.
    """
    ACTION_BAN = "BAN"
    ACTION_UNBAN = "UNBAN"
    ACTION_MUTE = "MUTE"
    ACTION_UNMUTE = "UNMUTE"
    ACTION_WARN = "WARN"
    ACTION_REMOVE = "REMOVE"

    ACTION_CHOICES = [
        (ACTION_BAN, "Ban"),
        (ACTION_UNBAN, "Unban"),
        (ACTION_MUTE, "Mute"),
        (ACTION_UNMUTE, "Unmute"),
        (ACTION_WARN, "Warn"),
        (ACTION_REMOVE, "Remove content"),
    ]

    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="+")
    target_object_id = models.CharField(max_length=255)
    target = GenericForeignKey("target_content_type", "target_object_id")

    subject_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="+")
    subject_object_id = models.CharField(max_length=255)
    subject = GenericForeignKey("subject_content_type", "subject_object_id")  # the user being acted upon

    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    reason = models.TextField(blank=True)
    performed_by_content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    performed_by_object_id = models.CharField(max_length=255, null=True, blank=True)
    performed_by = GenericForeignKey("performed_by_content_type", "performed_by_object_id")
    expires_at = models.DateTimeField(null=True, blank=True)  # e.g., temporary ban/mute

    class Meta:
        db_table = "core_moderation_action"
        indexes = [models.Index(fields=["action"]), models.Index(fields=["target_content_type", "target_object_id"])]


# ---------------------------
# Settings: GroupSettings / ChannelSettings
# ---------------------------
class GroupSettings(BaseEntity):
    """
    Per-group settings controlling membership behavior and messaging restrictions.
    These are separate to make them easy to edit and version independently.
    """
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name="settings")
    allow_attachments = models.BooleanField(default=True)
    allowed_mimetypes = JSONField(default=list, blank=True, help_text="If non-empty, only these mimetypes are allowed.")
    message_rate_limit_seconds = models.PositiveIntegerField(default=0, help_text="Minimum seconds between messages (0 = no slow mode)")
    max_message_length = models.PositiveIntegerField(default=10000, validators=[MinValueValidator(1)])
    join_policy = models.CharField(max_length=16, choices=[
        ("OPEN", "Open: anyone can join"),
        ("INVITE", "Invite-only"),
        ("REQUEST", "Request to join (pending approval)")
    ], default="OPEN")
    discoverability = models.CharField(max_length=16, choices=[
        ("VISIBLE", "Visible in search"),
        ("HIDDEN", "Hidden from search")
    ], default="VISIBLE")
    profanity_filter = models.BooleanField(default=False)
    max_attachments_per_message = models.PositiveIntegerField(default=5, validators=[MinValueValidator(0)])

    class Meta:
        db_table = "core_group_settings"


class ChannelSettings(BaseEntity):
    """
    Per-channel settings. Example: topic-only channels can prevent posting of images/files etc.
    """
    channel = models.OneToOneField(Channel, on_delete=models.CASCADE, related_name="settings")
    is_read_only = models.BooleanField(default=False)
    allow_threads = models.BooleanField(default=True)
    allow_attachments = models.BooleanField(default=True)
    allowed_mimetypes = JSONField(default=list, blank=True)
    slow_mode_seconds = models.PositiveIntegerField(default=0)
    max_message_length = models.PositiveIntegerField(default=5000)
    moderation_queue_enabled = models.BooleanField(default=False, help_text="If true, new messages may require moderator approval.")

    class Meta:
        db_table = "core_channel_settings"


# ---------------------------
# Small helpers
# ---------------------------
class CommunityPermissionHelper:
    @staticmethod
    def can_user_on_community(user, community: Community, permission_codename: str) -> bool:
        """
        Permission check for community-level permissions. Mirrors the logic used in Group.can_user.
        This is intentionally compact; extend similarly to Group.can_user if you need more nuance.
        """
        if getattr(user, "is_superuser", False):
            return True

        user_ct = ContentType.objects.get_for_model(user.__class__)
        principals = [(user_ct, str(user.pk))]
        for ra in RoleAssignment.objects.filter(principal_content_type=user_ct, principal_object_id=str(user.pk)):
            principals.append((ContentType.objects.get_for_model(Role), str(ra.role_id)))
        principals.append((None, "PUBLIC"))

        now = timezone.now()
        p_q = Q()
        for ct, pid in principals:
            if ct is None:
                p_q |= (Q(principal_content_type__isnull=True) & Q(principal_object_id="PUBLIC"))
            else:
                p_q |= (Q(principal_content_type=ct) & Q(principal_object_id=str(pid)))

        ace_q = Q()
        ace_q &= p_q
        ace_q &= (
            Q(target_content_type=ContentType.objects.get_for_model(community.__class__), target_object_id=str(community.pk))
            | (Q(target_content_type=ContentType.objects.get_for_model(community.__class__)) & Q(target_object_id__isnull=True))
            | (Q(target_content_type__isnull=True) & Q(target_object_id__isnull=True))
        )
        ace_q &= (Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        aces = AccessControlEntry.objects.filter(ace_q)
        denies = set()
        allows = set()
        for ace in aces:
            perms = set(ace.permissions or [])
            if ace.effect == AccessControlEntry.EFFECT_DENY:
                denies.update(perms)
            else:
                allows.update(perms)
        if permission_codename in denies:
            return False
        if permission_codename in allows:
            return True

        return False


# ---------------------------
# Usage examples (in comments)
# ---------------------------
"""
Examples:

# assign role to a user for a group:
from django.contrib.contenttypes.models import ContentType
user_ct = ContentType.objects.get_for_model(user.__class__)
group_ct = ContentType.objects.get_for_model(Group)

ra = RoleAssignment.objects.create(
    role=moderator_role,
    principal_content_type=user_ct,
    principal_object_id=str(user.pk),
    target_content_type=group_ct,
    target_object_id=str(group.pk)
)

# grant an allow ACE to a role on a channel:
role_ct = ContentType.objects.get_for_model(Role)
channel_ct = ContentType.objects.get_for_model(Channel)

ace = AccessControlEntry.objects.create(
    principal_content_type=role_ct,
    principal_object_id=str(moderator_role.id),
    target_content_type=channel_ct,
    target_object_id=str(channel.pk),
    permissions=["channel.post", "channel.delete_message"],
    effect=AccessControlEntry.EFFECT_ALLOW
)

# check permission:
if group.can_user(user, "group.post"):
    # allow posting

# invite flow:
invite = MembershipInvite.objects.create(token="abc123", group=group, created_by=inviter)
if invite.is_valid():
    invite.use()
    Membership.objects.create(group=group, user_content_type=user_ct, user_object_id=str(user.pk), status=Membership.STATUS_ACTIVE)

"""
