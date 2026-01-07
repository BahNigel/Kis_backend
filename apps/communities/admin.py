# apps/communities/admin.py
from django.contrib import admin

from apps.communities.models import (
    Community,
    CommunityMembership,
    CommunityJoinRequest,
    CommunityBan,
    CommunityPost,
    CommunityPostComment,
    CommunityPostReaction,
    CommunityCommentReaction,
)


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "partner",
        "owner",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "partner")
    search_fields = ("name", "slug", "owner__username", "owner__email")
    raw_id_fields = ("partner", "owner", "main_conversation")


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ("community", "user", "role", "joined_at", "left_at", "is_banned")
    list_filter = ("role", "is_banned")
    search_fields = ("community__name", "user__phone", "user__display_name")
    raw_id_fields = ("community", "user")


@admin.register(CommunityJoinRequest)
class CommunityJoinRequestAdmin(admin.ModelAdmin):
    list_display = ("community", "user", "status", "created_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("community__name", "user__phone", "user__display_name")
    raw_id_fields = ("community", "user", "reviewed_by")


@admin.register(CommunityBan)
class CommunityBanAdmin(admin.ModelAdmin):
    list_display = ("community", "user", "banned_by", "banned_at", "expires_at")
    search_fields = ("community__name", "user__phone", "user__display_name")
    raw_id_fields = ("community", "user", "banned_by")


@admin.register(CommunityPost)
class CommunityPostAdmin(admin.ModelAdmin):
    list_display = ("community", "author", "status", "is_pinned", "created_at")
    list_filter = ("status", "is_pinned")
    search_fields = ("community__name", "author__phone", "text")
    raw_id_fields = ("community", "author", "pinned_by")


@admin.register(CommunityPostComment)
class CommunityPostCommentAdmin(admin.ModelAdmin):
    list_display = ("post", "author", "is_deleted", "created_at")
    search_fields = ("author__phone", "text")
    raw_id_fields = ("post", "author")


@admin.register(CommunityPostReaction)
class CommunityPostReactionAdmin(admin.ModelAdmin):
    list_display = ("post", "user", "emoji", "created_at")
    search_fields = ("user__phone", "emoji")
    raw_id_fields = ("post", "user")


@admin.register(CommunityCommentReaction)
class CommunityCommentReactionAdmin(admin.ModelAdmin):
    list_display = ("comment", "user", "emoji", "created_at")
    search_fields = ("user__phone", "emoji")
    raw_id_fields = ("comment", "user")
