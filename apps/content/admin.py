# content/admin.py
from django.contrib import admin
from . import models

@admin.register(models.Content)
class ContentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "author", "is_published", "published_at")
    search_fields = ("title", "body", "author__username")
    list_filter = ("is_published", "language")
    readonly_fields = ("created_at", "updated_at")

@admin.register(models.Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "content", "author", "is_pinned", "moderation_state", "created_at")
    search_fields = ("text", "author__username", "content__title")
    list_filter = ("is_pinned", "moderation_state")

@admin.register(models.Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "content", "reaction_type", "weight", "created_at")
    search_fields = ("user__username", "content__title")

@admin.register(models.ContentMetrics)
class ContentMetricsAdmin(admin.ModelAdmin):
    list_display = ("content", "views_count", "shares_count", "comments_count", "reactions_count", "trending_score")

# Register remaining models quickly
admin.site.register([models.Tag, models.ContentTag, models.ContentView, models.ContentVariant,
                     models.AIAnalysis, models.Provenance, models.Promotion, models.Tip,
                     models.ModerationAction, models.ReactionBadge, models.Share])
