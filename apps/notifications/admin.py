
from django.contrib import admin
from . import models


@admin.register(models.Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("type", "user_id", "channel", "priority", "is_read", "created_at")
    list_filter = ("channel", "priority")
    search_fields = ("title", "body", "type", "dedup_key")


@admin.register(models.NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("key", "default_channel")
    search_fields = ("key", "title_template")


for m in [models.NotificationDelivery, models.NotificationRule, models.NotificationDigest]:
    try:
        admin.site.register(m)
    except admin.sites.AlreadyRegistered:
        pass
