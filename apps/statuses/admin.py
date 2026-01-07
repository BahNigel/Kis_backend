from django.contrib import admin

from apps.statuses.models import StatusItem


@admin.register(StatusItem)
class StatusItemAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "type", "expires_at", "is_deleted", "created_at")
    list_filter = ("type", "is_deleted")
    search_fields = ("user__phone", "user__display_name", "text")
