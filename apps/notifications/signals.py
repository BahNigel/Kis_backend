
from django.db.models.signals import post_save
from django.dispatch import receiver
from . import models


@receiver(post_save, sender=models.NotificationDelivery)
def on_delivery_status_change(sender, instance, created, **kwargs):
    if not created and instance.status == "SENT":
        # If any delivery is sent, mark parent notification delivered
        instance.notification.mark_delivered()