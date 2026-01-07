# apps/groups/admin.py
from django.contrib import admin

from apps.groups.models import Group, GroupMembership, GroupJoinRequest, GroupBan


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "owner",
        "partner",
        "community",
        "is_archived",
        "created_at",
    )
    list_filter = ("is_archived", "partner", "community")
    search_fields = ("name", "slug", "owner__username")
    raw_id_fields = ("owner", "conversation", "partner", "community")


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("group", "user", "role", "joined_at", "left_at", "is_banned")
    list_filter = ("role", "is_banned")
    search_fields = ("group__name", "user__phone", "user__display_name")
    raw_id_fields = ("group", "user")


@admin.register(GroupJoinRequest)
class GroupJoinRequestAdmin(admin.ModelAdmin):
    list_display = ("group", "user", "status", "created_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("group__name", "user__phone", "user__display_name")
    raw_id_fields = ("group", "user", "reviewed_by")


@admin.register(GroupBan)
class GroupBanAdmin(admin.ModelAdmin):
    list_display = ("group", "user", "banned_by", "banned_at", "expires_at")
    search_fields = ("group__name", "user__phone", "user__display_name")
    raw_id_fields = ("group", "user", "banned_by")
