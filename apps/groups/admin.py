# apps/groups/admin.py
from django.contrib import admin

from apps.groups.models import Group


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
