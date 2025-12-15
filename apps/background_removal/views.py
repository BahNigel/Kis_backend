# apps/background_removal/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import BackgroundRemovalJob
from .serializers import (
    BackgroundRemovalJobCreateSerializer,
    BackgroundRemovalJobStatusSerializer,
)
from .tasks import process_background_removal_job


class StartBackgroundRemovalView(APIView):
    """
    POST /api/v1/remove-background/
    Expects multipart/form-data with field `image`.
    """

    def post(self, request, *args, **kwargs):
        if "image" not in request.FILES:
            return Response(
                {"detail": "No 'image' file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BackgroundRemovalJobCreateSerializer(
            data={"image": request.FILES["image"]}
        )
        serializer.is_valid(raise_exception=True)
        job = serializer.save()

        # Kick off asynchronous processing via Celery + Redis
        process_background_removal_job.delay(str(job.id))

        return Response(
            {
                "job_id": str(job.id),
                "status": job.status,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class BackgroundRemovalJobStatusView(APIView):
    """
    GET /api/v1/gbJobs/<job_id>/
    Used by the React Native client to poll job status.
    """

    def get(self, request, job_id, *args, **kwargs):
        job = get_object_or_404(BackgroundRemovalJob, id=job_id)
        serializer = BackgroundRemovalJobStatusSerializer(
            job,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
