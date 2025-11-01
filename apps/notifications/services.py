
from django.utils import timezone
from django.db import transaction
from . import models
from django.conf import settings
import datetime
import logging

logger = logging.getLogger(__name__)


def should_suppress(user_id, notification_type, context=None):
    # Basic suppression logic: quiet hours, snoozes, and user rules.
    # In production, tie into user preferences from account app and ML suppression models.
    rules = models.NotificationRule.objects.filter(user_id=user_id, enabled=True)
    now = timezone.now()
    for r in rules:
        if r.type and r.type != notification_type:
            continue
        # check quiet hours
        q = r.schedule_json.get("quiet_hours")
        if q:
            start = q.get("start")
            end = q.get("end")
            if start and end:
                # naive local time check — production should normalize timezones
                now_time = now.time()
                start_t = datetime.time.fromisoformat(start)
                end_t = datetime.time.fromisoformat(end)
                if start_t <= now_time <= end_t:
                    return True
    return False


@transaction.atomic
def create_notification(user_id, type, template_key=None, context=None, channel=None, priority="MEDIUM", dedup_key=None, **kwargs):
    """Create a notification and schedule deliveries. Deduplication key avoids duplicates."""
    # dedupe
    if dedup_key:
        existing = models.Notification.objects.filter(user_id=user_id, dedup_key=dedup_key, is_read=False, is_deleted=False)
        if existing.exists():
            return existing.first()

    title = kwargs.get("title")
    body = kwargs.get("body")
    template = None
    if template_key:
        try:
            template = models.NotificationTemplate.objects.get(key=template_key)
            t, b = template.render(context or {})
            title = title or t
            body = body or b
        except models.NotificationTemplate.DoesNotExist:
            template = None

    notif = models.Notification.objects.create(
        user_id=user_id,
        template=template,
        type=type,
        title=title or "",
        body=body or "",
        target_type=kwargs.get("target_type"),
        target_id=kwargs.get("target_id"),
        channel=channel or (template.default_channel if template else "IN_APP"),
        priority=priority,
        actions_json=kwargs.get("actions_json", []),
        personalization_score=kwargs.get("personalization_score", 0.0),
        sentiment=kwargs.get("sentiment", "NEUTRAL"),
        reward_points=kwargs.get("reward_points"),
        is_snoozed=kwargs.get("is_snoozed", False),
        snoozed_until=kwargs.get("snoozed_until"),
        context_data=context or {},
        dedup_key=dedup_key,
    )

    # Create initial delivery record(s). Channel preferences might produce multiple.
    channels = [notif.channel]
    # apply user rules to override channels
    rules = models.NotificationRule.objects.filter(user_id=user_id, enabled=True)
    if rules.exists():
        preferred = rules.first().channels_json or []
        if preferred:
            channels = preferred

    for ch in channels:
        models.NotificationDelivery.objects.create(notification=notif, channel=ch)

    # Immediately schedule a worker to process deliveries (or enqueue Celery task in prod)
    from .tasks import process_notification_delivery

    process_notification_delivery.delay(str(notif.id))

    return notif