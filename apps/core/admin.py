from django.contrib import admin
from django.utils.html import format_html
from . import models

# ---------------------------
# Permissions & Roles
# ---------------------------
@admin.register(models.Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("codename", "description", "created_at")
    search_fields = ("codename", "description")
    ordering = ("codename",)


@admin.register(models.Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "scope", "get_parent_role", "is_default", "created_at")
    list_filter = ("scope", "is_default")
    search_fields = ("name", "description")
    filter_horizontal = ("permissions",)

    def get_parent_role(self, obj):
        return obj.parent_role
    get_parent_role.short_description = "Parent Role"


@admin.register(models.RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("role", "get_principal_type", "get_principal_id", "get_target_type", "get_target_id", "created_at")
    list_filter = ()
    search_fields = ("role__name",)

    def get_principal_type(self, obj):
        return obj.principal_type
    get_principal_type.short_description = "Principal Type"

    def get_principal_id(self, obj):
        return obj.principal_id
    get_principal_id.short_description = "Principal ID"

    def get_target_type(self, obj):
        return obj.target_type
    get_target_type.short_description = "Target Type"

    def get_target_id(self, obj):
        return obj.target_id
    get_target_id.short_description = "Target ID"


@admin.register(models.AccessControlEntry)
class AccessControlEntryAdmin(admin.ModelAdmin):
    list_display = ("get_principal_type", "get_principal_id", "get_target_type", "get_target_id", "effect", "expires_at")
    list_filter = ("effect",)
    search_fields = ("permissions",)

    def get_principal_type(self, obj):
        return obj.principal_type
    get_principal_type.short_description = "Principal Type"

    def get_principal_id(self, obj):
        return obj.principal_id
    get_principal_id.short_description = "Principal ID"

    def get_target_type(self, obj):
        return obj.target_type
    get_target_type.short_description = "Target Type"

    def get_target_id(self, obj):
        return obj.target_id
    get_target_id.short_description = "Target ID"


# ---------------------------
# Communities
# ---------------------------
class GroupInline(admin.TabularInline):
    model = models.Group
    extra = 0
    fields = ("name", "get_is_active", "member_count")
    readonly_fields = ("member_count", "get_is_active")

    def get_is_active(self, obj):
        return getattr(obj, "is_active", True)
    get_is_active.boolean = True
    get_is_active.short_description = "Active"


@admin.register(models.Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("name", "get_owner", "created_at", "get_is_active")
    search_fields = ("name", "description", "owner__username")
    inlines = [GroupInline]

    def get_owner(self, obj):
        return getattr(obj, "owner", None)
    get_owner.short_description = "Owner"

    def get_is_active(self, obj):
        return getattr(obj, "is_active", True)
    get_is_active.boolean = True
    get_is_active.short_description = "Active"


# ---------------------------
# Groups
# ---------------------------
class MembershipInline(admin.TabularInline):
    model = models.Membership
    extra = 0
    fields = ("get_user", "status", "joined_at", "is_moderator")
    readonly_fields = ("joined_at",)

    def get_user(self, obj):
        try:
            return obj.user_object
        except AttributeError:
            return f"{obj.user_content_type} ({obj.user_object_id})"
    get_user.short_description = "User"


class MembershipInviteInline(admin.TabularInline):
    model = models.MembershipInvite
    extra = 0
    readonly_fields = ("token", "created_by", "expires_at", "max_uses", "get_used_count")

    def get_used_count(self, obj):
        return getattr(obj, "used_count", 0)
    get_used_count.short_description = "Used Count"


@admin.register(models.Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "community", "get_is_active", "member_count", "created_at")
    list_filter = ("community",)
    search_fields = ("name", "description")
    inlines = [MembershipInline, MembershipInviteInline]

    def get_is_active(self, obj):
        return getattr(obj, "is_active", True)
    get_is_active.boolean = True
    get_is_active.short_description = "Active"


# ---------------------------
# Channels
# ---------------------------
@admin.register(models.Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("name", "is_public", "created_at")
    list_filter = ("is_public",)
    search_fields = ("name", "description")
    filter_horizontal = ("groups", "communities")


# ---------------------------
# Membership & Invites
# ---------------------------
@admin.register(models.Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("group", "get_user", "status", "joined_at", "is_moderator")

    def get_user(self, obj):
        try:
            return obj.user_object
        except AttributeError:
            return f"{obj.user_content_type} ({obj.user_object_id})"
    get_user.short_description = "User"


@admin.register(models.MembershipInvite)
class MembershipInviteAdmin(admin.ModelAdmin):
    list_display = ("group", "token", "created_by", "expires_at", "max_uses", "get_used_count")

    def get_used_count(self, obj):
        return getattr(obj, "used_count", 0)
    get_used_count.short_description = "Used Count"


# ---------------------------
# Moderation Actions
# ---------------------------
@admin.register(models.ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    list_display = ("get_action_type", "get_target_type", "get_target_id", "get_performed_by", "created_at")
    list_filter = ()
    search_fields = ()

    def get_action_type(self, obj):
        return getattr(obj, "action_type", "")
    get_action_type.short_description = "Action Type"

    def get_target_type(self, obj):
        return getattr(obj, "target_type", "")
    get_target_type.short_description = "Target Type"

    def get_target_id(self, obj):
        return getattr(obj, "target_id", "")
    get_target_id.short_description = "Target ID"

    def get_performed_by(self, obj):
        return getattr(obj, "performed_by", None)
    get_performed_by.short_description = "Performed By"


# ---------------------------
# Settings
# ---------------------------
@admin.register(models.GroupSettings)
class GroupSettingsAdmin(admin.ModelAdmin):
    list_display = ("group", "get_join_policy", "get_message_restriction", "updated_at")
    list_filter = ()
    search_fields = ("group__name",)

    def get_join_policy(self, obj):
        return getattr(obj, "join_policy", "")
    get_join_policy.short_description = "Join Policy"

    def get_message_restriction(self, obj):
        return getattr(obj, "message_restriction", "")
    get_message_restriction.short_description = "Message Restriction"


@admin.register(models.ChannelSettings)
class ChannelSettingsAdmin(admin.ModelAdmin):
    list_display = ("channel", "get_topic_restriction", "updated_at")
    search_fields = ("channel__name",)

    def get_topic_restriction(self, obj):
        return getattr(obj, "topic_restriction", "")
    get_topic_restriction.short_description = "Topic Restriction"
