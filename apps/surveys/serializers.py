from rest_framework import serializers
from .models import Survey, Question, Response, SurveyShare, SurveyAnalytics

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id','survey','text','vote_type','options','required','ai_score','order']
        read_only_fields = ['id','ai_score']

class ResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Response
        fields = ['id','survey','question','user_id','answer','submitted_at','is_valid','sentiment_score','social_impact_score']
        read_only_fields = ['id','submitted_at','is_valid','sentiment_score','social_impact_score']

class SurveyShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyShare
        fields = ['id','survey','shared_by_id','platform','shared_at']
        read_only_fields = ['id','shared_at']

class SurveyAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyAnalytics
        fields = '__all__'
        read_only_fields = ['id','survey','total_responses','completion_rate','average_time','top_choices','demographic_breakdown','trend_score']

class SurveySerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    analytics = SurveyAnalyticsSerializer(read_only=True)

    class Meta:
        model = Survey
        fields = ['id','owner_id','org_id','group_id','title','description','type','is_anonymous','starts_at','ends_at','reward_points','is_recurring','visibility','ai_score','popularity_rank','questions','analytics','created_at','updated_at']
        read_only_fields = ['id','ai_score','popularity_rank','created_at','updated_at']

class SurveyCreateSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, required=False)

    class Meta:
        model = Survey
        fields = ['id','owner_id','org_id','group_id','title','description','type','is_anonymous','starts_at','ends_at','reward_points','is_recurring','visibility','questions']
        read_only_fields = ['id']

    def create(self, validated_data):
        questions = validated_data.pop('questions', [])
        survey = Survey.objects.create(**validated_data)
        for idx, q in enumerate(questions):
            Question.objects.create(survey=survey, order=idx, **q)
        return survey