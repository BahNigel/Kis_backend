from django.db import models
from django.utils import timezone
import uuid


def uuid4():
    return uuid.uuid4()


class BaseEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True


class NotificationTemplate(BaseEntity):
    """Reusable templates for notifications. Templates support mustache-like placeholders.
    Example context: {"actor_name": "Nigel", "event_title": "Launch"}
    """
    key = models.CharField(max_length=200, unique=True)
    title_template = models.CharField(max_length=400)
    body_template = models.TextField()
    default_channel = models.CharField(max_length=32, default="IN_APP")
    metadata = models.JSONField(default=dict, blank=True)

    def render(self, context: dict):
        # Very small rendering: replace {{key}} tokens. In prod use jinja2 or similar.
        title = self.title_template
        body = self.body_template
        for k, v in (context or {}).items():
            token = "{{%s}}" % k
            title = title.replace(token, str(v))
            body = body.replace(token, str(v))
        return title, body


class Notification(BaseEntity):
    CHANNEL_CHOICES = [
        ("IN_APP", "In-App"),
        ("EMAIL", "Email"),
        ("SMS", "SMS"),
        ("WEBHOOK", "Webhook"),
    ]
    PRIORITY = [
        ("URGENT", "Urgent"),
        ("HIGH", "High"),
        ("MEDIUM", "Medium"),
        ("LOW", "Low"),
    ]
    SENTIMENT = [
        ("POSITIVE", "Positive"),
        ("NEUTRAL", "Neutral"),
        ("NEGATIVE", "Negative"),
    ]

    user_id = models.UUIDField(db_index=True)  # recipient user id from account app
    template = models.ForeignKey(NotificationTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    type = models.CharField(max_length=128, db_index=True)  # e.g. FRIEND_REQUEST, EVENT_ALERT
    title = models.CharField(max_length=400)
    body = models.TextField()

    target_type = models.CharField(max_length=64, blank=True, null=True)
    target_id = models.UUIDField(null=True, blank=True)

    channel = models.CharField(max_length=32, choices=CHANNEL_CHOICES, default="IN_APP")
    priority = models.CharField(max_length=16, choices=PRIORITY, default="MEDIUM")

    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    actions_json = models.JSONField(default=list, blank=True)  # list of action dicts {name, label, url}
    personalization_score = models.FloatField(default=0.0)
    sentiment = models.CharField(max_length=16, choices=SENTIMENT, default="NEUTRAL")
    reward_points = models.IntegerField(null=True, blank=True)

    is_snoozed = models.BooleanField(default=False)
    snoozed_until = models.DateTimeField(null=True, blank=True)

    context_data = models.JSONField(default=dict, blank=True)
    dedup_key = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    is_read = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["user_id", "is_read", "created_at"]),
        ]

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    def mark_delivered(self):
        self.delivered_at = timezone.now()
        self.save(update_fields=["delivered_at"]) 


class NotificationRule(BaseEntity):
    """Defines per-user or global rules for notification routing, suppression and scheduling."""
    user_id = models.UUIDField(null=True, blank=True, db_index=True)
    target_type = models.CharField(max_length=64, null=True, blank=True)
    target_id = models.UUIDField(null=True, blank=True)
    type = models.CharField(max_length=128, null=True, blank=True)

    priority = models.CharField(max_length=16, null=True, blank=True)
    condition_json = models.JSONField(default=dict, blank=True)
    schedule_json = models.JSONField(default=dict, blank=True)  # e.g. "quiet_hours": {start: '22:00', end: '07:00'}
    channels_json = models.JSONField(default=list, blank=True)  # preferred channels order
    enabled = models.BooleanField(default=True)


class NotificationDelivery(BaseEntity):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SENT", "Sent"),
        ("FAILED", "Failed"),
        ("BOUNCED", "Bounced"),
    ]

    notification = models.ForeignKey(Notification, related_name="deliveries", on_delete=models.CASCADE)
    channel = models.CharField(max_length=32)
    delivered_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="PENDING")
    retry_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["status", "channel"])]


class NotificationDigest(BaseEntity):
    """Aggregated digest record for email/in-app weekly/daily digests."""
    user_id = models.UUIDField(db_index=True)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    notifications = models.JSONField(default=list)
    sent_at = models.DateTimeField(null=True, blank=True)