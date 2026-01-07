from django.contrib import admin

from .models import LoyaltyPoint


@admin.register(LoyaltyPoint)
class LoyaltyPointAdmin(admin.ModelAdmin):
    list_display = ("user", "points", "earned_at", "expires_at", "reason")
    search_fields = ("user__email", "user__phone", "reason")
