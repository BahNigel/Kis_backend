from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Subscription
from .tasks import reconcile_subscription

@receiver(post_save, sender=Subscription)
def on_subscription_changed(sender, instance, created, **kwargs):
    # queue reconciliation when subscription is created/updated
    reconcile_subscription.delay(str(instance.id))