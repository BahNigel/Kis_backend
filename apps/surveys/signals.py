from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Response, SurveyAnalytics

@receiver(post_save, sender=Response)
def update_survey_analytics(sender, instance, created, **kwargs):
    if not created:
        return
    survey = instance.survey
    analytics, _ = SurveyAnalytics.objects.get_or_create(survey=survey)
    analytics.total_responses += 1
    # naive completion rate & trend update example
    analytics.completion_rate = round(analytics.total_responses / max(1, survey.questions.count()), 3)
    analytics.trend_score = analytics.total_responses / max(1, (survey.popularity_rank or 1))
    analytics.top_choices = {}  # advanced aggregation would go here
    analytics.save()