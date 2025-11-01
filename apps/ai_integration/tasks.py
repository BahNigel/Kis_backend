# Assumes Celery is configured in the project
from celery import shared_task
from django.utils import timezone
from .models import AIJob, TranslationRequest, AIJobFeedback, AIPipeline
from .services import dispatch_job_to_model, run_pipeline_steps


@shared_task(bind=True, max_retries=3)
def enqueue_ai_job(self, job_id):
    try:
        job = AIJob.objects.get(id=job_id)
        job.status = 'RUNNING'
        job.started_at = timezone.now()
        job.save()

        # Dispatch to appropriate local handler / remote model
        result = dispatch_job_to_model(job)

        job.result_ref = result.get('result_ref', '')
        job.status = 'COMPLETED'
        job.completed_at = timezone.now()
        job.save()
        return result
    except Exception as exc:
        job = AIJob.objects.filter(id=job_id).first()
        if job:
            job.status = 'FAILED'
            job.error = str(exc)
            job.retries = job.retries + 1
            job.save()
        raise self.retry(exc=exc, countdown=5)


@shared_task
def execute_pipeline(pipeline_id, triggered_by='SYSTEM'):
    pipeline = AIPipeline.objects.get(id=pipeline_id)
    pipeline.started_at = timezone.now()
    pipeline.status = 'ACTIVE'
    pipeline.save()
    try:
        run_pipeline_steps(pipeline)
        pipeline.status = 'DRAFT'
        pipeline.completed_at = timezone.now()
        pipeline.save()
    except Exception as e:
        pipeline.status = 'DISABLED'
        pipeline.save()
        raise
