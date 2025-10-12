# moderation/urls.py
from rest_framework.routers import DefaultRouter
from .views import (
    FlagViewSet,
    ModerationActionViewSet,
    AuditLogViewSet,
    UserReputationViewSet,
    ModerationRuleViewSet,
    SafetyAlertViewSet
)

router = DefaultRouter()
router.register(r"flags", FlagViewSet, basename="flags")
router.register(r"actions", ModerationActionViewSet, basename="moderation-actions")
router.register(r"audit-logs", AuditLogViewSet, basename="audit-logs")
router.register(r"user-reputation", UserReputationViewSet, basename="user-reputation")
router.register(r"moderation-rules", ModerationRuleViewSet, basename="moderation-rules")
router.register(r"safety-alerts", SafetyAlertViewSet, basename="safety-alerts")

urlpatterns = router.urls
