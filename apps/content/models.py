# content/models.py
import uuid
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.accounts.models import User


class BaseEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True

class Content(BaseEntity):
    """
    Core content model — minimal fields here; extend with concrete types in other apps
    """
    author = models.ForeignKey(User, related_name="contents", on_delete=models.CASCADE)
    title = models.CharField(max_length=400)
    body = models.TextField(blank=True)
    summary = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=16, default="en")
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["is_published", "published_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.id})"

    def publish(self):
        self.is_published = True
        self.published_at = timezone.now()
        self.save(update_fields=["is_published", "published_at", "updated_at"])

    def recalc_metrics(self):
        from django.db.models import Count, Sum
        metrics, created = ContentMetrics.objects.get_or_create(content=self)
        metrics.views_count = ContentView.objects.filter(content=self, is_unique=True).count()
        metrics.shares_count = Share.objects.filter(content=self).count()
        metrics.comments_count = Comment.objects.filter(content=self, is_deleted=False).count()
        metrics.reactions_count = Reaction.objects.filter(content=self).count()
        metrics.trending_score = ContentMetrics.compute_trending_score(
            views=metrics.views_count,
            shares=metrics.shares_count,
            comments=metrics.comments_count,
            reactions=metrics.reactions_count,
            content=self
        )
        metrics.save()
        return metrics

class Comment(BaseEntity):
    content = models.ForeignKey(Content, related_name="comments", on_delete=models.CASCADE)
    author = models.ForeignKey(User, related_name="comments", on_delete=models.SET_NULL, null=True)
    text = models.TextField()
    parent_comment = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    language = models.CharField(max_length=16, default="en")
    edited_at = models.DateTimeField(null=True, blank=True)
    is_pinned = models.BooleanField(default=False, db_index=True)
    moderation_state = models.CharField(max_length=32, default="pending", db_index=True)

    class Meta:
        ordering = ["-created_at"]

class Share(BaseEntity):
    SHARE_TYPES = [
        ("link", "Link"),
        ("embed", "Embed"),
        ("external", "External"),
    ]
    VISIBILITY = [
        ("public", "Public"),
        ("followers", "Followers"),
        ("private", "Private"),
    ]
    user = models.ForeignKey(User, related_name="shares", on_delete=models.SET_NULL, null=True)
    content = models.ForeignKey(Content, related_name="shares", on_delete=models.CASCADE)
    share_type = models.CharField(max_length=32, choices=SHARE_TYPES, default="link")
    comment = models.TextField(blank=True, null=True)
    visibility = models.CharField(max_length=32, choices=VISIBILITY, default="public")
    created_at = models.DateTimeField(default=timezone.now)

class Reaction(BaseEntity):
    REACTION_TYPES = [
        ("like", "Like"),
        ("love", "Love"),
        ("haha", "Haha"),
        ("sad", "Sad"),
        ("angry", "Angry"),
        ("custom", "Custom"),
    ]
    user = models.ForeignKey(User, related_name="reactions", on_delete=models.CASCADE)
    content = models.ForeignKey(Content, related_name="reactions", on_delete=models.CASCADE)
    reaction_type = models.CharField(max_length=32, choices=REACTION_TYPES)
    emoji_code = models.CharField(max_length=64, blank=True, null=True)
    weight = models.FloatField(default=1.0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "content", "reaction_type")

class Tag(BaseEntity):
    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(max_length=128, unique=True)
    type = models.CharField(max_length=64, default="topic")

    def __str__(self):
        return self.name

class ContentTag(BaseEntity):
    content = models.ForeignKey(Content, related_name="content_tags", on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, related_name="content_tags", on_delete=models.CASCADE)

    class Meta:
        unique_together = ("content", "tag")

class ContentView(BaseEntity):
    user = models.ForeignKey(User, related_name="views", on_delete=models.SET_NULL, null=True, blank=True)
    content = models.ForeignKey(Content, related_name="views", on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(default=timezone.now)
    duration_sec = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    device_type = models.CharField(max_length=64, null=True, blank=True)
    ip_address_hash = models.CharField(max_length=128, null=True, blank=True)
    is_unique = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["content", "viewed_at"]),
        ]

class ContentMetrics(BaseEntity):
    content = models.OneToOneField(Content, related_name="metrics", on_delete=models.CASCADE)
    views_count = models.BigIntegerField(default=0)
    shares_count = models.BigIntegerField(default=0)
    comments_count = models.BigIntegerField(default=0)
    reactions_count = models.BigIntegerField(default=0)
    media_asset = models.ForeignKey(
        "media.MediaAsset",
        related_name="contents",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Optional: associated MediaAsset if this content *is* a media item."
    )
    trending_score = models.FloatField(default=0.0)
    engagement_rate = models.FloatField(default=0.0, null=True, blank=True)

    @staticmethod
    def compute_trending_score(views=0, shares=0, comments=0, reactions=0, content: Content = None):
        """
        Example composite trending calculation:
          trending = log(views + 1) * 0.4 + shares*0.3 + log(comments+1)*0.15 + log(reactions+1)*0.15
        Could be replaced with a time-decayed score or machine-learned model.
        """
        import math
        score = 0.0
        score += math.log(views + 1) * 0.4
        score += shares * 0.3
        score += math.log(comments + 1) * 0.15
        score += math.log(reactions + 1) * 0.15
        # optionally scale by recency
        if content and content.published_at:
            age_days = max((timezone.now() - content.published_at).days, 1)
            decay = 1.0 / (1 + (age_days / 7))  # weekly decay
            score *= decay
        return float(score)

class ContentVariant(BaseEntity):
    content = models.ForeignKey(Content, related_name="variants", on_delete=models.CASCADE)
    variant_type = models.CharField(max_length=64)  # e.g., "headline_test", "language_translation"
    ai_summary = models.TextField(null=True, blank=True)
    language = models.CharField(max_length=16, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

class AIAnalysis(BaseEntity):
    content = models.ForeignKey(Content, related_name="ai_analyses", on_delete=models.CASCADE)
    safety_score = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)], default=1.0)
    topic_tags = models.JSONField(default=list, blank=True)
    toxicity_score = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    readability_score = models.FloatField(default=0.0)
    generated_summary = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

class Provenance(BaseEntity):
    content = models.OneToOneField(Content, related_name="provenance", on_delete=models.CASCADE)
    origin_hash = models.CharField(max_length=128)
    edit_history = models.JSONField(default=list, blank=True)
    anchored_at = models.DateTimeField(null=True, blank=True)

class Promotion(BaseEntity):
    content = models.ForeignKey(Content, related_name="promotions", on_delete=models.CASCADE)
    owner = models.ForeignKey(User, related_name="promotions", on_delete=models.SET_NULL, null=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    budget_cents = models.BigIntegerField(default=0)
    status = models.CharField(max_length=32, default="scheduled")

class Tip(BaseEntity):
    content = models.ForeignKey(Content, related_name="tips", on_delete=models.CASCADE)
    from_user = models.ForeignKey(User, related_name="tips_sent", on_delete=models.SET_NULL, null=True)
    to_user = models.ForeignKey(User, related_name="tips_received", on_delete=models.SET_NULL, null=True)
    amount_cents = models.BigIntegerField()
    currency = models.CharField(max_length=8, default="USD")
    created_at = models.DateTimeField(default=timezone.now)

class ModerationAction(BaseEntity):
    ACTION_TYPES = [
        ("remove", "Remove Content"),
        ("warning", "Warning"),
        ("suspend", "Suspend User"),
        ("restore", "Restore"),
        ("note", "Note"),
    ]
    content = models.ForeignKey(Content, related_name="moderation_actions", on_delete=models.CASCADE)
    moderator = models.ForeignKey(User, related_name="moderation_actions", on_delete=models.SET_NULL, null=True)
    action_type = models.CharField(max_length=32, choices=ACTION_TYPES)
    reason = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

class ReactionBadge(BaseEntity):
    user = models.ForeignKey(User, related_name="reaction_badges", on_delete=models.CASCADE)
    content = models.ForeignKey(Content, related_name="reaction_badges", on_delete=models.CASCADE)
    badge_type = models.CharField(max_length=64)
    awarded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "content", "badge_type")
