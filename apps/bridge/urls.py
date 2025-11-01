from rest_framework.routers import DefaultRouter
from .views import BridgeAccountViewSet, BridgeThreadViewSet, BridgeMessageViewSet, BridgeAutomationViewSet, BridgeAnalyticsViewSet

router = DefaultRouter()
router.register('accounts', BridgeAccountViewSet, basename='bridgeaccount')
router.register('threads', BridgeThreadViewSet, basename='bridgethread')
router.register('messages', BridgeMessageViewSet, basename='bridgemessage')
router.register('automations', BridgeAutomationViewSet, basename='bridgeautomation')
router.register('analytics', BridgeAnalyticsViewSet, basename='bridgeanalytics')

urlpatterns = router.urls