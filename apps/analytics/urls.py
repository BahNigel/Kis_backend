from rest_framework.routers import DefaultRouter
from .views import (
    MetricViewSet, EventStreamViewSet, DashboardViewSet, AppSettingViewSet,
    FeatureFlagViewSet, AlertViewSet, EngagementScoreViewSet,
)

router = DefaultRouter()
router.register('metrics', MetricViewSet, basename='metric')
router.register('events', EventStreamViewSet, basename='eventstream')
router.register('dashboards', DashboardViewSet, basename='dashboard')
router.register('settings', AppSettingViewSet, basename='appsetting')
router.register('flags', FeatureFlagViewSet, basename='featureflag')
router.register('alerts', AlertViewSet, basename='alert')
router.register('engagement', EngagementScoreViewSet, basename='engagement')

urlpatterns = router.urls