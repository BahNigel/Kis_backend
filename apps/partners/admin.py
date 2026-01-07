# apps/partners/admin.py
from django.contrib import admin

from apps.partners.models import Partner, PartnerPost


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "owner",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "owner__username", "owner__email")
    raw_id_fields = ("owner", "main_conversation")


@admin.register(PartnerPost)
class PartnerPostAdmin(admin.ModelAdmin):
    list_display = ("partner", "author", "created_at", "is_deleted")
    list_filter = ("partner", "is_deleted")
    search_fields = ("partner__name", "author__display_name", "text")
    raw_id_fields = ("partner", "author")
