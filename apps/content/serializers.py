# content/serializers.py
from rest_framework import serializers
from .models import (
    Content, Comment, Reaction, ContentMetrics, Tag, ContentTag,
    ContentView, ContentVariant, AIAnalysis, Provenance, Share, Tip
)

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name", "slug", "type")

class ContentSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField()
    tags = serializers.SerializerMethodField()
    metrics = serializers.SerializerMethodField()

    class Meta:
        model = Content
        fields = ("id", "title", "body", "summary", "language", "author", "is_published", "published_at", "tags", "metrics")

    def get_tags(self, obj):
        return TagSerializer([ct.tag for ct in obj.content_tags.all()], many=True).data

    def get_metrics(self, obj):
        if hasattr(obj, "metrics"):
            return {
                "views": obj.metrics.views_count,
                "shares": obj.metrics.shares_count,
                "comments": obj.metrics.comments_count,
                "reactions": obj.metrics.reactions_count,
                "trending_score": obj.metrics.trending_score
            }
        return None

class CommentSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)
    replies_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ("id", "content", "author", "text", "parent_comment", "language", "edited_at", "is_pinned", "moderation_state", "replies_count", "created_at")

    def get_replies_count(self, obj):
        return obj.replies.count()

class ReactionSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    class Meta:
        model = Reaction
        fields = ("id", "user", "content", "reaction_type", "emoji_code", "weight", "metadata", "created_at")

class ContentMetricsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentMetrics
        fields = ("views_count", "shares_count", "comments_count", "reactions_count", "trending_score", "engagement_rate")

# Minimal serializers for administrative objects
class ContentVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentVariant
        fields = "__all__"

class AIAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIAnalysis
        fields = "__all__"

class ProvenanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provenance
        fields = "__all__"

class ShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = Share
        fields = "__all__"

class TipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tip
        fields = "__all__"
