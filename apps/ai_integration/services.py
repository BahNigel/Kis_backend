# Central place with model orchestration, adapter pattern for providers, and helpers
from typing import Dict, Any
from .models import AIJob, TranslationRequest, AIModel


def dispatch_job_to_model(job: AIJob) -> Dict[str, Any]:
    """
    Decide which model / adapter to call based on job metadata and local availability.
    For a free tier, this uses a local lightweight model adapter (stub) or external free APIs.
    Returns dict with keys: result_ref, payload.
    """
    # Basic router by job_type
    if job.job_type == 'TRANSLATION':
        return handle_translation(job)
    if job.job_type == 'CUSTOM' and job.input_ref_type == 'QNA':
        return handle_qna(job)
    # other handlers...
    return {'result_ref': '', 'payload': {}}


def handle_translation(job: AIJob) -> Dict[str, Any]:
    # Fetch translation request
    tr = getattr(job, 'translation_request', None)
    if not tr:
        return {'result_ref': '', 'payload': {}}
    # Here you would call a real translation provider. For free tier implement a simple rule-based stub.
    # Example stub: reverse text as "translation" (replace with real model in paid tier)
    translated = tr.result_text or '<<translated_text_placeholder>>'
    # Save back
    tr.result_text = translated
    tr.quality_score = 0.0
    tr.save()
    return {'result_ref': f'translation:{tr.id}', 'payload': {'translated': translated}}


def handle_qna(job: AIJob) -> Dict[str, Any]:
    # Simple QnA stub: echo + context
    message = job.metadata.get('message', '')
    response = f"Echo (free stub): {message}"
    # Ideally append to session conversation
    # Save result_ref
    job.result_ref = 'qna:stub'
    job.save()
    return {'result_ref': job.result_ref, 'payload': {'answer': response}}


def run_pipeline_steps(pipeline: AIModel):
    # Interpret pipeline.job_order which contains definitions like [{job_type: 'TRANSLATION', ...}, ...]
    for step in pipeline.job_order:
        # Create job per step
        job = AIJob.objects.create(job_type=step.get('job_type', 'CUSTOM'), input_ref_type=step.get('input_ref_type', 'RAW'), metadata=step.get('metadata', {}), triggered_by='PIPELINE')
        dispatch_job_to_model(job)