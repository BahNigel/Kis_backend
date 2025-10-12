# media/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import MediaAsset, MediaVariant, ProcessingJob, MediaMetrics
from .serializers import (
    MediaAssetSerializer, MediaVariantSerializer, ProcessingJobSerializer, MediaMetricsSerializer
)
from .permissions import IsOwnerOrReadOnly

# --- Swagger / OpenAPI compatibility shim (drf-yasg first, then drf-spectacular) ---
try:
    # drf-yasg
    from drf_yasg.utils import swagger_auto_schema
    from drf_yasg import openapi

    def schema_decorator(**kwargs):
        return swagger_auto_schema(**kwargs)

    def _PARAM(name, typ, required=False, desc=""):
        # drf-yasg Parameter helper for query params
        location = openapi.IN_QUERY if typ == "query" else openapi.IN_BODY
        return openapi.Parameter(name=name, in_=location, description=desc, type=openapi.TYPE_STRING, required=required)

    USING_SCHEMA_LIB = "drf_yasg"

except Exception:
    try:
        # drf-spectacular
        from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

        def schema_decorator(**kwargs):
            """
            Map a limited subset of kwargs to drf-spectacular's extend_schema.
            Supported keys mapped: operation_description, request_body, responses, manual_parameters
            """
            operation_description = kwargs.get("operation_description")
            request_body = kwargs.get("request_body")
            responses = kwargs.get("responses")
            manual_parameters = kwargs.get("manual_parameters") or kwargs.get("parameters") or []

            spect_params = []
            for p in manual_parameters:
                try:
                    name = getattr(p, "name", None) or getattr(p, "param_name", None)
                    location = getattr(p, "in_", None)
                    required = getattr(p, "required", False)
                    desc = getattr(p, "description", "") or ""
                    # Map common locations; default to QUERY
                    loc = OpenApiParameter.QUERY
                    spect_params.append(OpenApiParameter(name=name, description=desc, required=required, type=str, location=loc))
                except Exception:
                    continue

            # Map responses: drf-spectacular expects dict mapping status->serializer/response
            return extend_schema(
                description=operation_description,
                request=request_body,
                responses=responses,
                parameters=spect_params if spect_params else None
            )

        def _PARAM(name, typ, required=False, desc=""):
            # simple factory for spectaculr mapping (location defaulted to query)
            loc = OpenApiParameter.QUERY
            return OpenApiParameter(name=name, description=desc, required=required, type=str, location=loc)

        USING_SCHEMA_LIB = "drf_spectacular"

    except Exception:
        # no schema lib installed, no-op decorator
        def schema_decorator(**kwargs):
            def _noop(func):
                return func
            return _noop

        def _PARAM(name, typ, required=False, desc=""):
            return None

        USING_SCHEMA_LIB = None
# ------------------------------------------------------------------------------

class MediaAssetViewSet(viewsets.ModelViewSet):
    queryset = MediaAsset.objects.select_related("owner").all()
    serializer_class = MediaAssetSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @schema_decorator(
        operation_description=(
            "Mark an upload as complete. Client should supply 'canonical_url' (optional). "
            "This endpoint marks the asset ready and schedules common processing jobs (analyze, phash)."
        ),
        manual_parameters=[
            _PARAM("canonical_url", "query", required=False, desc="Canonical public URL for the uploaded asset")
        ],
        responses={
            200: (openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "ok": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="True when scheduling succeeded")
            }) if USING_SCHEMA_LIB == "drf_yasg" else {"ok": "boolean"})
        }
    )
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def upload_complete(self, request, pk=None):
        """
        Called when client finishes upload; can mark asset ready and schedule processing jobs.
        """
        asset = self.get_object()
        url = request.data.get("canonical_url")
        asset.mark_ready(url=url)
        # schedule processing jobs - simple stub: create jobs for analyze & phash
        ProcessingJob.objects.create(asset=asset, pipeline="analyze", priority=50)
        ProcessingJob.objects.create(asset=asset, pipeline="phash", priority=40)
        return Response({"ok": True})

    @schema_decorator(
        operation_description="Record a media view. Optionally pass 'minutes' viewed (int).",
        manual_parameters=[
            _PARAM("minutes", "query", required=False, desc="Minutes streamed/viewed (integer)")
        ],
        responses={
            200: (openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "views": openapi.Schema(type=openapi.TYPE_INTEGER),
                "stream_minutes": openapi.Schema(type=openapi.TYPE_INTEGER),
                "downloads": openapi.Schema(type=openapi.TYPE_INTEGER),
                "carbon_grams": openapi.Schema(type=openapi.TYPE_NUMBER),
                "cost_cents": openapi.Schema(type=openapi.TYPE_INTEGER),
            }) if USING_SCHEMA_LIB == "drf_yasg" else MediaMetricsSerializer)
        }
    )
    @action(detail=True, methods=["post"], permission_classes=[permissions.AllowAny])
    def record_view(self, request, pk=None):
        """
        Record a view for the media asset (increments counters). Returns current metrics.
        """
        asset = self.get_object()
        minutes = request.data.get("minutes", 0)
        metrics, _ = MediaMetrics.objects.get_or_create(asset=asset)
        metrics.add_view(minutes=minutes)
        return Response(MediaMetricsSerializer(metrics).data)

class ProcessingJobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProcessingJob.objects.select_related("asset").all()
    serializer_class = ProcessingJobSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
