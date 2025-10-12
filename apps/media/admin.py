# media/admin.py
from django.contrib import admin
from . import models

@admin.register(models.MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "owner", "status", "bytes")
    search_fields = ("bucket_key", "canonical_url", "checksum")
    list_filter = ("type", "status")
    readonly_fields = ("created_at", "updated_at")

@admin.register(models.ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = ("id", "asset", "pipeline", "status", "priority", "started_at", "finished_at")
    list_filter = ("pipeline", "status")

@admin.register(models.MediaVariant)
class MediaVariantAdmin(admin.ModelAdmin):
    list_display = ("id", "asset", "purpose", "codec", "url")
    search_fields = ("url",)

admin.site.register([models.Provenance, models.Watermark, models.AccessPolicy, models.MediaMetrics])
