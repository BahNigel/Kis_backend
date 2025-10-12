from rest_framework import serializers
from .models import AIJob, TranslationRequest, QnASession, AIModel, AIJobFeedback, AIPipeline, AISchedule


class AIModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIModel
        fields = '__all__'


class AIJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIJob
        fields = '__all__'
        read_only_fields = ('status', 'started_at', 'completed_at', 'retries')


class TranslationRequestSerializer(serializers.ModelSerializer):
    job = AIJobSerializer(read_only=True)

    class Meta:
        model = TranslationRequest
        fields = '__all__'


class QnASessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QnASession
        fields = '__all__'


class AIJobFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIJobFeedback
        fields = '__all__'


class AIPipelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIPipeline
        fields = '__all__'


class AIScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AISchedule
        fields = '__all__'