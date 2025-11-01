
from celery import shared_task
from django.utils import timezone
from . import models, services
import time
import random
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def process_notification_delivery(self, notification_id):
    """Process pending deliveries for a notification. Implements retry/backoff and status updates."""
    try:
        notif = models.Notification.objects.get(id=notification_id)
    except models.Notification.DoesNotExist:
        return

    # suppression
    if services.should_suppress(notif.user_id, notif.type, context=notif.context_data):
        # mark as snoozed or postpone
        notif.is_snoozed = True
        notif.snoozed_until = timezone.now() + timezone.timedelta(hours=1)
        notif.save()
        return

    for delivery in notif.deliveries.filter(status="PENDING"):
        # simulate delivery for in-app: mark delivered
        try:
            if delivery.channel == "IN_APP":
                delivery.status = "SENT"
                delivery.delivered_at = timezone.now()
                delivery.save()
                notif.mark_delivered()
            elif delivery.channel == "WEBHOOK":
                # call webhook endpoint (placeholder)
                # In production, sign payload, handle retries, and verify responses
                # simulate random failure
                if random.random() < 0.85:
                    delivery.status = "SENT"
                    delivery.delivered_at = timezone.now()
                    delivery.save()
                    notif.mark_delivered()
                else:
                    raise Exception("webhook error")
            else:
                # EMAIL/SMS channels are placeholders — we create delivery and mark pending
                # Hand off to external provider integrations (not included)
                delivery.status = "PENDING"
                delivery.save()

        except Exception as exc:
            delivery.retry_count += 1
            delivery.last_error = str(exc)
            delivery.status = "FAILED"
            delivery.save()
            try:
                raise self.retry(exc=exc, countdown=min(60 * 2 ** delivery.retry_count, 3600))
            except Exception:
                # reached max retries or other issue
                logger.exception("Delivery failed for %s", delivery.id)
                continue


@shared_task
def compile_and_send_digests(period_start_iso: str, period_end_iso: str):
    """Aggregate notifications into digests and mark them for delivery."""
    from django.utils.dateparse import parse_datetime
    start = parse_datetime(period_start_iso)
    end = parse_datetime(period_end_iso)
    # For each user, aggregate notifications
    uids = models.Notification.objects.filter(created_at__gte=start, created_at__lt=end).values_list("user_id", flat=True).distinct()
    for uid in uids:
        notes = models.Notification.objects.filter(user_id=uid, created_at__gte=start, created_at__lt=end)
        payload = [{"id": str(n.id), "title": n.title, "summary": n.body[:200]} for n in notes]
        digest = models.NotificationDigest.objects.create(user_id=uid, period_start=start, period_end=end, notifications=payload)
        # create a delivery record for the digest (email or in-app)
        # In production: create aggregated email or in-app batched message
        # Here we simply mark digest as ready; external worker will send emails
    return True
