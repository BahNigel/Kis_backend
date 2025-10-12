from celery import shared_task
from .models import Survey, SurveyAnalytics, Response

@shared_task
def compute_survey_analytics(survey_id):
    survey = Survey.objects.get(id=survey_id)
    total = survey.responses.count()
    analytics, _ = SurveyAnalytics.objects.get_or_create(survey=survey)
    analytics.total_responses = total
    # compute more advanced stats: completion rate, avg time, top choices
    analytics.completion_rate = total / max(1, survey.questions.count())
    # placeholder for ML/AI scoring - integrate external model here
    analytics.trend_score = float(total) * 1.0
    analytics.save()

@shared_task
def ai_enrich_response(response_id):
    # placeholder: call external ML model to classify sentiment, spam, etc.
    r = Response.objects.get(id=response_id)
    # e.g. call model -> r.sentiment_score = ...
    r.is_valid = True
    r.save()