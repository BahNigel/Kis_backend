from celery import shared_task
from .models import Metric, EventStream, EngagementScore
from django.utils import timezone
import numpy as np

@shared_task
def compute_predictive_metrics(metric_id):
    # placeholder: load historical values and run a simple sklearn model
    metric = Metric.objects.get(id=metric_id)
    # fake prediction
    metric.predicted_value = metric.value * 1.05
    metric.confidence = 0.85
    metric.save()

@shared_task
def process_event_stream(event_id):
    ev = EventStream.objects.get(id=event_id)
    # parse event and create metrics
    # example: message_sent -> increment counters
    ev.processed = True
    ev.save()

@shared_task
def compute_engagement_for_target(target_id):
    # aggregate metrics and compute engagement score
    score = EngagementScore.objects.create(target_id=target_id, score_type='activity', value=42.0, calculated_at=timezone.now(), metadata={})
    return str(score.id)