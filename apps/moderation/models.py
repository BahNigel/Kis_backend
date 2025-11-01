# moderation/models.py
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


class Flag(BaseEntity):
    SOURCE_CHOICES = [("USER", "User"), ("SYSTEM", "System"), ("AI", "AI")]
    TARGET_TYPES = [("POST", "Post"), ("COMMENT", "Comment"), ("GROUP", "Group"), ("CHANNEL", "Channel"), ("USER", "User")]
    SEVERITY = [("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"), ("CRITICAL", "Critical")]
    STATUS = [("PENDING", "Pending"), ("REVIEWED", "Reviewed"), ("ACTIONED", "Actioned"), ("DISMISSED", "Dismissed")]
    ESCALATION = [("AUTO", "Auto"), ("MODERATOR", "Moderator"), ("ADMIN", "Admin")]

    source = models.CharField(max_length=16, choices=SOURCE_CHOICES)
    target_type = models.CharField(max_length=32, choices=TARGET_TYPES)
    target_id = models.UUIDField()
    reporter_id = models.UUIDField(null=True, blank=True)
    reason = models.TextField()
    severity = models.CharField(max_length=16, choices=SEVERITY)
    status = models.CharField(max_length=16, choices=STATUS, default="PENDING")
    ai_score = models.FloatField(null=True, blank=True)
    escalation_level = models.CharField(max_length=16, choices=ESCALATION, default="AUTO")
    tags = models.JSONField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)


class ModerationAction(BaseEntity):
    ACTIONS = [("WARN", "Warn"), ("SUSPEND", "Suspend"), ("DELETE", "Delete"), 
               ("BAN", "Ban"), ("TEMP_RESTRICT", "Temporary Restrict"), ("ESCALATE", "Escalate")]

    flag = models.ForeignKey(Flag, related_name="actions", on_delete=models.CASCADE)
    action = models.CharField(max_length=32, choices=ACTIONS)
    notes = models.TextField(blank=True)
    performed_by_id = models.UUIDField()
    scheduled_action_at = models.DateTimeField(null=True, blank=True)
    auto_generated = models.BooleanField(default=False)


class AuditLog(BaseEntity):
    actor_id = models.UUIDField()
    action = models.CharField(max_length=128)
    target_type = models.CharField(max_length=32)
    target_id = models.UUIDField()
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.CharField(max_length=45, null=True, blank=True)
    device_info = models.TextField(null=True, blank=True)


class UserReputation(BaseEntity):
    user_id = models.UUIDField(unique=True)
    score = models.FloatField(default=100.0)
    flags_received = models.IntegerField(default=0)
    actions_taken = models.IntegerField(default=0)
    last_updated = models.DateTimeField(default=timezone.now)


class ModerationRule(BaseEntity):
    target_type = models.CharField(max_length=32)
    condition_json = models.JSONField(default=dict, blank=True)
    action_json = models.JSONField(default=dict, blank=True)
    escalation_json = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)


class SafetyAlert(BaseEntity):
    ALERT_TYPES = [("HIGH_SEVERITY", "High Severity"), ("LEGAL", "Legal"), ("COMMUNITY_RISK", "Community Risk")]
    flag = models.ForeignKey(Flag, null=True, blank=True, on_delete=models.SET_NULL)
    alert_type = models.CharField(max_length=32, choices=ALERT_TYPES)
    message = models.TextField()
    sent_to_ids = models.JSONField(default=list, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
