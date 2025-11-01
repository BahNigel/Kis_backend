
from django.contrib import admin
from . import models


@admin.register(models.Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "start_at", "end_at", "status", "visibility")
    list_filter = ("status", "type", "visibility")
    search_fields = ("title", "description", "slug")
    readonly_fields = ("created_at", "updated_at")


@admin.register(models.EventSession)
class EventSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "event", "start_at", "end_at", "session_type")
    search_fields = ("title",)


@admin.register(models.Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("tier_name", "event", "type", "price_cents", "quantity_remaining")
    search_fields = ("tier_name", "sku")


# Register other models quickly
for m in [models.Venue, models.SeatMap, models.Seat, models.TicketSale, models.Attendance, models.HybridStream]:
    try:
        admin.site.register(m)
    except admin.sites.AlreadyRegistered:
        pass