# chat/admin.py
from django.contrib import admin

from .models import (
    Conversation,
    ConversationMember,
    ConversationSettings,
    MessageThreadLink,
    PermissionDefinition,
    RoleDefinition,
    RolePermission,
    PrincipalRole,
    ConversationType,
    BaseConversationRole,
)


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class ConversationSettingsInline(admin.StackedInline):
    """
    One-to-one settings for each conversation.
    Shown inline on the Conversation detail page.
    """
    model = ConversationSettings
    can_delete = False
    extra = 0
    fk_name = "conversation"


class ConversationMemberInline(admin.TabularInline):
    """
    Members of a conversation, shown inline in Conversation admin.
    """
    model = ConversationMember
    extra = 0
    raw_id_fields = ("user",)
    autocomplete_fields = ("user",)
    show_change_link = True


# ---------------------------------------------------------------------------
# Conversation Admin
# ---------------------------------------------------------------------------

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "type",
        "title",
        "created_by",
        "is_archived",
        "is_locked",
        "last_message_at",
        "created_at",
    )
    list_filter = (
        "type",
        "is_archived",
        "is_locked",
        ("created_at", admin.DateFieldListFilter),
        ("last_message_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "id",
        "title",
        "description",
        "created_by__username",
        "memberships__user__username",
        "memberships__user__phone_number",  # adjust if your User has phone field
    )
    readonly_fields = ("created_at", "updated_at", "last_message_at")
    date_hierarchy = "created_at"
    inlines = [ConversationSettingsInline, ConversationMemberInline]
    list_select_related = ("created_by",)

    ordering = ("-last_message_at", "-created_at")


# ---------------------------------------------------------------------------
# Conversation Member Admin
# ---------------------------------------------------------------------------

@admin.register(ConversationMember)
class ConversationMemberAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "user",
        "base_role",
        "notification_level",
        "is_muted",
        "is_blocked",
        "joined_at",
        "left_at",
        "is_active",
    )
    list_filter = (
        "base_role",
        "notification_level",
        "is_muted",
        "is_blocked",
        ("joined_at", admin.DateFieldListFilter),
        ("left_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "conversation__id",
        "conversation__title",
        "user__username",
        "user__email",
        "user__phone_number",  # adjust/remove depending on your User model
    )
    raw_id_fields = ("conversation", "user")
    readonly_fields = ("joined_at", "left_at")

    def is_active(self, obj):
        return obj.is_active
    is_active.boolean = True
    is_active.short_description = "Active?"


# ---------------------------------------------------------------------------
# Conversation Settings Admin
# ---------------------------------------------------------------------------

@admin.register(ConversationSettings)
class ConversationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "conversation",
        "send_policy",
        "join_policy",
        "info_edit_policy",
        "subroom_policy",
        "max_subroom_depth",
        "message_retention_days",
        "allow_reactions",
        "allow_stickers",
        "allow_attachments",
        "created_at",
    )
    list_filter = (
        "send_policy",
        "join_policy",
        "info_edit_policy",
        "subroom_policy",
        "allow_reactions",
        "allow_stickers",
        "allow_attachments",
    )
    search_fields = ("conversation__id", "conversation__title")
    raw_id_fields = ("conversation",)
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# Message Thread Link Admin
# ---------------------------------------------------------------------------

@admin.register(MessageThreadLink)
class MessageThreadLinkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "parent_conversation",
        "parent_message_key",
        "child_conversation",
        "parent_thread",
        "depth",
        "created_by",
        "created_at",
    )
    list_filter = ("depth", ("created_at", admin.DateFieldListFilter))
    search_fields = (
        "parent_message_key",
        "parent_conversation__id",
        "parent_conversation__title",
        "child_conversation__id",
        "child_conversation__title",
        "created_by__username",
    )
    raw_id_fields = ("parent_conversation", "child_conversation", "parent_thread", "created_by")


# ---------------------------------------------------------------------------
# RBAC Admins
# ---------------------------------------------------------------------------

@admin.register(PermissionDefinition)
class PermissionDefinitionAdmin(admin.ModelAdmin):
    list_display = ("code", "category")
    search_fields = ("code", "description", "category")
    list_filter = ("category",)


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0
    raw_id_fields = ("permission",)


@admin.register(RoleDefinition)
class RoleDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "slug",
        "scope_type",
        "scope_id",
        "is_system",
        "is_default_for_scope",
        "rank",
        "created_by",
        "created_at",
    )
    list_filter = (
        "scope_type",
        "is_system",
        "is_default_for_scope",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = ("name", "slug", "scope_id", "created_by__username")
    inlines = [RolePermissionInline]
    raw_id_fields = ("created_by",)
    ordering = ("scope_type", "rank", "slug")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
  list_display = ("id", "role", "permission", "allowed")
  list_filter = ("allowed", "role__scope_type", "permission__category")
  search_fields = (
      "role__name",
      "role__slug",
      "permission__code",
      "permission__description",
  )
  raw_id_fields = ("role", "permission")


@admin.register(PrincipalRole)
class PrincipalRoleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "role",
        "scope_type",
        "scope_id",
        "assigned_at",
    )
    list_filter = (
        "scope_type",
        ("assigned_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "user__username",
        "user__email",
        "role__name",
        "role__slug",
        "scope_id",
    )
    raw_id_fields = ("user", "role")
    date_hierarchy = "assigned_at"
