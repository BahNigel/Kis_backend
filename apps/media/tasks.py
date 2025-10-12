# media/tasks.py
from celery import shared_task
from .models import ProcessingJob, MediaAsset

@shared_task(bind=True)
def process_job_worker(self, job_id):
    """
    Worker stub: pick a ProcessingJob, perform pipeline, write results.
    Replace with integration to FFMPEG, image pipelines, ML models, etc.
    """
    job = ProcessingJob.objects.get(id=job_id)
    job.mark_running(worker_meta={"worker": "local-stub"})
    # Fake processing depending on pipeline
    if job.pipeline == "phash":
        # compute a faux perceptual hash
        result_meta = {"phash": "0000abcd1234", "derived_variant": None}
    elif job.pipeline == "analyze":
        result_meta = {"labels": {"nsfw": 0.01}, "derived_variant": None}
    else:
        result_meta = {"notes": "processed by stub"}

    job.mark_done(result_meta=result_meta)
    return {"job": str(job_id), "status": "done"}

@shared_task
def schedule_asset_processing(asset_id):
    asset = MediaAsset.objects.get(id=asset_id)
    # Create jobs for common pipelines
    ProcessingJob.objects.create(asset=asset, pipeline="phash", priority=40)
    ProcessingJob.objects.create(asset=asset, pipeline="analyze", priority=50)
    ProcessingJob.objects.create(asset=asset, pipeline="transcode", priority=60)
    return {"asset": str(asset_id)}
