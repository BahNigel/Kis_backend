
from celery import shared_task
from . import models


@shared_task
def compute_event_ai_analysis(event_id):
    # Placeholder: compute trends, sentiment, predicted no-shows.
    event = models.Event.objects.get(id=event_id)
    # Gather data
    attendances = event.attendances.count()
    analysis = {
        "attendance_trend_json": {"total": attendances},
        "sentiment_by_session": {},
        "predicted_no_show_rate": 0.1,
        "recommended_capacity_adjustments": {},
    }
    models.EventAIAnalysis.objects.update_or_create(event=event, defaults=analysis)