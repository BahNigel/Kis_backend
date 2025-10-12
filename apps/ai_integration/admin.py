from django.contrib import admin
from .models import AIJob, TranslationRequest, QnASession, AIModel, AIJobFeedback, AIPipeline, AISchedule


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'is_active', 'trained_at')
    search_fields = ('name', 'version')


@admin.register(AIJob)
class AIJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'job_type', 'status', 'started_at', 'completed_at', 'retries')
    list_filter = ('job_type', 'status')
    search_fields = ('id', 'result_ref')


@admin.register(TranslationRequest)
class TranslationRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'source_lang', 'target_lang', 'quality_score')


@admin.register(QnASession)
class QnASessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_id', 'session_status', 'last_interaction_at')


@admin.register(AIJobFeedback)
class AIJobFeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'feedback_type', 'processed')


@admin.register(AIPipeline)
class AIPipelineAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'status')


@admin.register(AISchedule)
class AIScheduleAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'cron_expression', 'enabled')