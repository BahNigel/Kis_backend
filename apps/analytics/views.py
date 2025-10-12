from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Metric, EventStream, Dashboard, AppSetting, FeatureFlag, Alert, EngagementScore
from .serializers import (
    MetricSerializer, EventStreamSerializer, DashboardSerializer, AppSettingSerializer,
    FeatureFlagSerializer, AlertSerializer, EngagementScoreSerializer,
)
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter, OpenApiTypes, OpenApiExample
from .tasks import compute_predictive_metrics, process_event_stream

@extend_schema_view(
    list=extend_schema(summary="List Metrics", responses={200: MetricSerializer(many=True)}, tags=["Metrics"]),
    retrieve=extend_schema(summary="Retrieve Metric", responses={200: MetricSerializer}, tags=["Metrics"]),
    create=extend_schema(summary="Create Metric", request=MetricSerializer, responses={201: MetricSerializer}, tags=["Metrics"]),
    update=extend_schema(summary="Update Metric", request=MetricSerializer, responses={200: MetricSerializer}, tags=["Metrics"]),
    destroy=extend_schema(summary="Delete Metric", responses={204: OpenApiResponse(description="deleted")}, tags=["Metrics"]),
)
class MetricViewSet(viewsets.ModelViewSet):
    queryset = Metric.objects.all()
    serializer_class = MetricSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['name','kind','source']
    search_fields = ['name']
    ordering_fields = ['captured_at','value']

    @extend_schema(summary="Trigger predictive computation for a metric", request=None, responses={200: OpenApiResponse(description="prediction queued")}, tags=["Metrics"])
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def predict(self, request, pk=None):
        metric = self.get_object()
        compute_predictive_metrics.delay(str(metric.id))
        return Response({'detail': 'prediction queued'})

@extend_schema_view(
    list=extend_schema(summary="List Event Stream", responses={200: EventStreamSerializer(many=True)}, tags=["EventStream"]),
    create=extend_schema(summary="Ingest Event", request=EventStreamSerializer, responses={201: EventStreamSerializer}, tags=["EventStream"]),
)
class EventStreamViewSet(viewsets.ModelViewSet):
    queryset = EventStream.objects.all()
    serializer_class = EventStreamSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ev = serializer.save()
        # enqueue processing
        process_event_stream.delay(str(ev.id))
        return Response(serializer.data, status=status.HTTP_201_CREATED)

@extend_schema_view(
    list=extend_schema(summary="List Dashboards", responses={200: DashboardSerializer(many=True)}, tags=["Dashboards"]),
    retrieve=extend_schema(summary="Retrieve Dashboard", responses={200: DashboardSerializer}, tags=["Dashboards"]),
    create=extend_schema(summary="Create Dashboard", request=DashboardSerializer, responses={201: DashboardSerializer}, tags=["Dashboards"]),
)
class DashboardViewSet(viewsets.ModelViewSet):
    queryset = Dashboard.objects.all()
    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated]

@extend_schema_view(
    list=extend_schema(summary="List App Settings", responses={200: AppSettingSerializer(many=True)}, tags=["Settings"]),
    retrieve=extend_schema(summary="Retrieve App Setting", responses={200: AppSettingSerializer}, tags=["Settings"]),
    create=extend_schema(summary="Create App Setting", request=AppSettingSerializer, responses={201: AppSettingSerializer}, tags=["Settings"]),
)
class AppSettingViewSet(viewsets.ModelViewSet):
    queryset = AppSetting.objects.all()
    serializer_class = AppSettingSerializer
    permission_classes = [IsAuthenticated]

@extend_schema_view(
    list=extend_schema(summary="List Feature Flags", responses={200: FeatureFlagSerializer(many=True)}, tags=["FeatureFlags"]),
    retrieve=extend_schema(summary="Retrieve Feature Flag", responses={200: FeatureFlagSerializer}, tags=["FeatureFlags"]),
    create=extend_schema(summary="Create Feature Flag", request=FeatureFlagSerializer, responses={201: FeatureFlagSerializer}, tags=["FeatureFlags"]),
)
class FeatureFlagViewSet(viewsets.ModelViewSet):
    queryset = FeatureFlag.objects.all()
    serializer_class = FeatureFlagSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Evaluate a feature flag for a target", request=None, responses={200: OpenApiResponse(description="flag evaluation result")}, tags=["FeatureFlags"])
    @action(detail=True, methods=['post'], url_path='evaluate', permission_classes=[IsAuthenticated])
    def evaluate(self, request, pk=None):
        flag = self.get_object()
        # naive evaluation stub
        target = request.data.get('target')
        enabled = flag.enabled
        # more complex audience checks would go here
        return Response({'key': flag.key, 'enabled': enabled, 'target': target})

@extend_schema_view(
    list=extend_schema(summary="List Alerts", responses={200: AlertSerializer(many=True)}, tags=["Alerts"]),
    retrieve=extend_schema(summary="Retrieve Alert", responses={200: AlertSerializer}, tags=["Alerts"]),
    create=extend_schema(summary="Create Alert", request=AlertSerializer, responses={201: AlertSerializer}, tags=["Alerts"]),
)
class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Acknowledge an alert", request=None, responses={200: OpenApiResponse(description="acknowledged")}, tags=["Alerts"])
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.acknowledged_by = request.user.id
        alert.triggered_at = alert.triggered_at or timezone.now()
        alert.save()
        return Response({'detail': 'acknowledged'})

@extend_schema_view(
    list=extend_schema(summary="List Engagement Scores", responses={200: EngagementScoreSerializer(many=True)}, tags=["Engagement"]),
    retrieve=extend_schema(summary="Retrieve Engagement Score", responses={200: EngagementScoreSerializer}, tags=["Engagement"]),
)
class EngagementScoreViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EngagementScore.objects.all()
    serializer_class = EngagementScoreSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]