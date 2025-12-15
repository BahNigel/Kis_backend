# apps/background_removal/tasks.py
import logging
import requests
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile

from .models import BackgroundRemovalJob

logger = logging.getLogger(__name__)

@shared_task
def process_background_removal_job(job_id: str):
    try:
        job = BackgroundRemovalJob.objects.get(id=job_id)
    except BackgroundRemovalJob.DoesNotExist:
        logger.error("BackgroundRemovalJob %s does not exist", job_id)
        return

    if not job.original_image:
        job.status = BackgroundRemovalJob.Status.FAILED
        job.error_message = "Original image is missing."
        job.save(update_fields=["status", "error_message"])
        return

    job.status = BackgroundRemovalJob.Status.PROCESSING
    job.error_message = None
    job.save(update_fields=["status", "error_message"])

    media_service_url = settings.MEDIA_SERVICE_URL

    try:
        # Send original image to media-service
        with job.original_image.open("rb") as f:
            files = {
                "image": (job.original_image.name, f, "image/png")
            }
            response = requests.post(media_service_url, files=files, timeout=120)

        if response.status_code != 200:
            logger.error(
                "Media service error (%s): %s",
                response.status_code,
                response.text[:500],
            )
            job.status = BackgroundRemovalJob.Status.FAILED
            job.error_message = (
                f"Media service error ({response.status_code}): "
                f"{response.text[:200]}"
            )
            job.save(update_fields=["status", "error_message"])
            return

        processed_bytes = response.content
        if not processed_bytes:
            job.status = BackgroundRemovalJob.Status.FAILED
            job.error_message = "Media service returned empty content."
            job.save(update_fields=["status", "error_message"])
            return

        filename = f"bgremoved_{job.id}.png"
        job.processed_image.save(
            filename,
            ContentFile(processed_bytes),
            save=False,
        )
        job.status = BackgroundRemovalJob.Status.DONE
        job.error_message = None
        job.save()

    except Exception as e:
        logger.exception("Error processing background removal job %s", job_id)
        job.status = BackgroundRemovalJob.Status.FAILED
        job.error_message = str(e)
        job.save(update_fields=["status", "error_message"])
