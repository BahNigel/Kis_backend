# apps/channels/admin.py
from django.contrib import admin

from apps.channels.models import Channel


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
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
    search_fields = ("name", "slug", "owner__username", "owner__email")
    raw_id_fields = ("owner", "conversation", "partner", "community")
