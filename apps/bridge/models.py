from django.db import models
import uuid
from django.db.models import JSONField
from django.utils import timezone

class BaseEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True

class BridgeAccount(BaseEntity):
    user_id = models.UUIDField()  # link to local user
    external_app = models.CharField(max_length=64)
    external_user_id = models.CharField(max_length=256)
    access_token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    metadata = JSONField(default=dict)

    class Meta:
        indexes = [models.Index(fields=['user_id','external_app'])]

class BridgeThread(BaseEntity):
    external_app = models.CharField(max_length=64)
    external_thread_id = models.CharField(max_length=256)
    linked_thread_id = models.UUIDField(null=True, blank=True)
    topic = models.CharField(max_length=512, blank=True)
    metadata = JSONField(default=dict)
    is_archived = models.BooleanField(default=False)
    last_activity_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=['external_app','external_thread_id'])]

class BridgeMessage(BaseEntity):
    bridge_thread = models.ForeignKey(BridgeThread, related_name='messages', on_delete=models.CASCADE)
    direction = models.CharField(max_length=8, choices=[('INBOUND','INBOUND'),('OUTBOUND','OUTBOUND')])
    message_type = models.CharField(max_length=16, choices=[('TEXT','TEXT'),('IMAGE','IMAGE'),('VIDEO','VIDEO'),('FILE','FILE'),('LINK','LINK'),('REACTION','REACTION')])
    payload = JSONField(default=dict)
    external_message_id = models.CharField(max_length=256, null=True, blank=True)
    status = models.CharField(max_length=16, default='RECEIVED')
    sent_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    ai_category = models.CharField(max_length=128, null=True, blank=True)
    sentiment_score = models.FloatField(null=True, blank=True)
    is_flagged = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['bridge_thread','external_message_id','status'])]

class BridgeAutomation(BaseEntity):
    bridge_thread = models.ForeignKey(BridgeThread, related_name='automations', on_delete=models.CASCADE)
    rule_name = models.CharField(max_length=128)
    trigger_type = models.CharField(max_length=16, choices=[('KEYWORD','KEYWORD'),('TIME','TIME'),('EVENT','EVENT')])
    action_type = models.CharField(max_length=16, choices=[('REPLY','REPLY'),('FORWARD','FORWARD'),('ALERT','ALERT'),('ANALYTICS','ANALYTICS')])
    action_payload = JSONField(default=dict)
    last_triggered_at = models.DateTimeField(null=True, blank=True)

class BridgeAnalytics(BaseEntity):
    bridge_account = models.OneToOneField(BridgeAccount, related_name='analytics', on_delete=models.CASCADE)
    total_messages = models.IntegerField(default=0)
    inbound_count = models.IntegerField(default=0)
    outbound_count = models.IntegerField(default=0)
    avg_response_time = models.FloatField(default=0.0)
    top_external_apps = JSONField(default=dict)
    engagement_score = models.FloatField(default=0.0)