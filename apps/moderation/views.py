# moderation/views.py
from datetime import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from . import models, serializers

# -------------------------
# Moderation Flag Management
# -------------------------
class FlagViewSet(viewsets.ModelViewSet):
    queryset = models.Flag.objects.all()
    serializer_class = serializers.FlagSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Mark a flag as reviewed by moderator.",
        responses={200: serializers.FlagSerializer}
    )
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        flag = self.get_object()
        flag.status = "REVIEWED"
        flag.reviewed_at = timezone.now()
        flag.save()
        return Response(serializers.FlagSerializer(flag).data)

    @swagger_auto_schema(
        operation_description="Resolve a flag and optionally schedule an automatic moderation action.",
        responses={200: serializers.FlagSerializer}
    )
    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        flag = self.get_object()
        flag.status = "ACTIONED"
        flag.resolved_at = timezone.now()
        flag.save()
        return Response(serializers.FlagSerializer(flag).data)


# -------------------------
# Moderation Actions
# -------------------------
class ModerationActionViewSet(viewsets.ModelViewSet):
    queryset = models.ModerationAction.objects.all()
    serializer_class = serializers.ModerationActionSerializer
    permission_classes = [IsAuthenticated]


# -------------------------
# Audit Logs
# -------------------------
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.AuditLog.objects.all()
    serializer_class = serializers.AuditLogSerializer
    permission_classes = [IsAuthenticated]


# -------------------------
# Reputation
# -------------------------
class UserReputationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.UserReputation.objects.all()
    serializer_class = serializers.UserReputationSerializer
    permission_classes = [IsAuthenticated]


# -------------------------
# Moderation Rules
# -------------------------
class ModerationRuleViewSet(viewsets.ModelViewSet):
    queryset = models.ModerationRule.objects.all()
    serializer_class = serializers.ModerationRuleSerializer
    permission_classes = [IsAuthenticated]


# -------------------------
# Safety Alerts
# -------------------------
class SafetyAlertViewSet(viewsets.ModelViewSet):
    queryset = models.SafetyAlert.objects.all()
    serializer_class = serializers.SafetyAlertSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Acknowledge a safety alert.",
        responses={200: serializers.SafetyAlertSerializer}
    )
    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.acknowledged_at = timezone.now()
        alert.save()
        return Response(serializers.SafetyAlertSerializer(alert).data)
