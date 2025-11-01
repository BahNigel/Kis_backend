from django.db import models
import uuid
from django.db.models import JSONField
from django.utils import timezone
from enum import Enum
from django_enumfield import enum

class BaseEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True

class SurveyType(enum.Enum):
    POLL = 0
    QUIZ = 1
    FEEDBACK = 2

class Visibility(enum.Enum):
    PUBLIC = 0
    PRIVATE = 1
    GROUP_ONLY = 2

class VoteType(enum.Enum):
    SINGLE_CHOICE = 0
    MULTIPLE_CHOICE = 1
    RATING = 2
    OPEN = 3

class Survey(BaseEntity):
    owner_id = models.UUIDField(null=True, blank=True)
    org_id = models.UUIDField(null=True, blank=True)
    group_id = models.UUIDField(null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    type = enum.EnumField(SurveyType)
    is_anonymous = models.BooleanField(default=False)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    reward_points = models.IntegerField(null=True, blank=True)
    is_recurring = models.BooleanField(default=False)
    visibility = enum.EnumField(Visibility, default=Visibility.PUBLIC)
    ai_score = models.FloatField(default=0.0)
    popularity_rank = models.IntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['owner_id']),
            models.Index(fields=['org_id']),
            models.Index(fields=['-created_at']),
        ]

    def is_active(self):
        now = timezone.now()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True

class Question(BaseEntity):
    survey = models.ForeignKey(Survey, related_name='questions', on_delete=models.CASCADE)
    text = models.TextField()
    vote_type = enum.EnumField(VoteType)
    # options stored as JSON: list of {id, text, metadata}
    options = JSONField(default=list)
    required = models.BooleanField(default=True)
    ai_score = models.FloatField(default=0.0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        indexes = [models.Index(fields=['survey', 'order'])]

class Response(BaseEntity):
    survey = models.ForeignKey(Survey, related_name='responses', on_delete=models.CASCADE)
    question = models.ForeignKey(Question, related_name='responses', on_delete=models.CASCADE)
    user_id = models.UUIDField(null=True, blank=True)
    answer = JSONField()  # supports complex answers
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_valid = models.BooleanField(default=True)
    sentiment_score = models.FloatField(null=True, blank=True)
    social_impact_score = models.FloatField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['survey','question']), models.Index(fields=['user_id'])]

class SurveyShare(BaseEntity):
    survey = models.ForeignKey(Survey, related_name='shares', on_delete=models.CASCADE)
    shared_by_id = models.UUIDField()
    platform = models.CharField(max_length=64)
    shared_at = models.DateTimeField(auto_now_add=True)

class SurveyAnalytics(BaseEntity):
    survey = models.OneToOneField(Survey, related_name='analytics', on_delete=models.CASCADE)
    total_responses = models.IntegerField(default=0)
    completion_rate = models.FloatField(default=0.0)
    average_time = models.FloatField(default=0.0)
    top_choices = JSONField(default=dict)
    demographic_breakdown = JSONField(default=dict)
    trend_score = models.FloatField(default=0.0)
