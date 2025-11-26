# apps/communities/admin.py
from django.contrib import admin

from apps.communities.models import Community


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
