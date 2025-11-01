from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Metric, Alert
from .tasks import compute_predictive_metrics

@receiver(post_save, sender=Metric)
def on_metric_created(sender, instance, created, **kwargs):
    if created:
        # queue prediction for new metric values
        compute_predictive_metrics.delay(str(instance.id))
        # check alerts
        for alert in instance.alerts.all():
            # simplistic threshold check
            cond = alert.condition or {}
            if cond.get('threshold') and instance.value > cond['threshold']:
                alert.triggered_at = instance.captured_at
                alert.save()