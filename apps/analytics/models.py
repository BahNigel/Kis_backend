from django.db import models
import uuid
from django.utils import timezone
from django.db.models import JSONField

class BaseEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True

class Metric(BaseEntity):
    KIND_CHOICES = [
        ('system','system'),('engagement','engagement'),('partner','partner'),('predictive','predictive')
    ]
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    name = models.CharField(max_length=255)
    value = models.FloatField()
    unit = models.CharField(max_length=32, blank=True)
    captured_at = models.DateTimeField(default=timezone.now)
    tags = JSONField(default=dict)
    source = models.CharField(max_length=64, default='internal')
    predicted_value = models.FloatField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['name','captured_at']), models.Index(fields=['kind'])]

class EventStream(BaseEntity):
    event_type = models.CharField(max_length=128)
    payload = JSONField(default=dict)
    timestamp = models.DateTimeField(default=timezone.now)
    processed = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['event_type','timestamp'])]

class Dashboard(BaseEntity):
    org_id = models.UUIDField(null=True, blank=True)
    partner_id = models.UUIDField(null=True, blank=True)
    name = models.CharField(max_length=255)
    definition = JSONField(default=dict)  # widgets, layout, queries
    is_shared = models.BooleanField(default=False)
    auto_update = models.BooleanField(default=True)

class AppSetting(BaseEntity):
    SCOPE_CHOICES = [('global','global'),('org','org'),('user','user'),('partner','partner')]
    key = models.CharField(max_length=255)
    value = JSONField(default=dict)
    scope = models.CharField(max_length=32, choices=SCOPE_CHOICES, default='global')
    audience = JSONField(null=True, blank=True)
    adaptive_rules = JSONField(null=True, blank=True)

    class Meta:
        unique_together = [('key','scope')]

class FeatureFlag(BaseEntity):
    key = models.CharField(max_length=255, unique=True)
    enabled = models.BooleanField(default=False)
    audience = JSONField(default=dict)
    experiment_id = models.UUIDField(null=True, blank=True)
    partner_visible = models.BooleanField(default=False)

class Alert(BaseEntity):
    SEVERITY_CHOICES = [('low','low'),('medium','medium'),('high','high'),('critical','critical')]
    metric = models.ForeignKey(Metric, related_name='alerts', on_delete=models.CASCADE)
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES)
    condition = JSONField(default=dict)
    triggered_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.UUIDField(null=True, blank=True)
    audience = JSONField(null=True, blank=True)

class EngagementScore(BaseEntity):
    target_id = models.UUIDField()
    score_type = models.CharField(max_length=64)
    value = models.FloatField()
    calculated_at = models.DateTimeField(default=timezone.now)
    metadata = JSONField(default=dict)

    class Meta:
        indexes = [models.Index(fields=['target_id','score_type','calculated_at'])]
