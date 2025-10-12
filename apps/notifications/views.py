# notifications/views.py
from django.utils import timezone
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

# Swagger / OpenAPI helpers (drf-yasg)
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from . import models, serializers as srl, services
from .permissions import IsOwnerOrReadOnly

# -------------------------
# Small request/response serializers for docs
# -------------------------
class BulkMarkReadRequestSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), help_text="List of notification UUIDs to mark read")


class CreateNotificationRequestSerializer(serializers.Serializer):
    user_id = serializers.UUIDField(required=False, help_text="Target user ID (if omitted, default to caller when allowed)")
    type = serializers.CharField(max_length=128)
    template_key = serializers.CharField(max_length=200, required=False, allow_blank=True)
    context = serializers.DictField(child=serializers.CharField(), required=False)
    channel = serializers.CharField(max_length=32, required=False)
    priority = serializers.CharField(max_length=16, required=False, default="MEDIUM")
    dedup_key = serializers.CharField(max_length=255, required=False, allow_null=True)
    title = serializers.CharField(required=False, allow_blank=True)
    body = serializers.CharField(required=False, allow_blank=True)


class MarkReadResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    is_read = serializers.BooleanField()
    read_at = serializers.DateTimeField(allow_null=True)


# -------------------------
# Notification CRUD & Actions
# -------------------------
class NotificationViewSet(viewsets.ModelViewSet):
    """
    Notification endpoints.

    Features:
      - List & fetch notifications (users only see their own)
      - Mark single notification read
      - Bulk mark-as-read
      - Create notification (internal services may call this endpoint)
    """
    queryset = models.Notification.objects.all()
    serializer_class = srl.NotificationSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    lookup_field = "id"

    def get_queryset(self):
        """
        Limit notifications to the current user (exclude deleted).
        """
        user = self.request.user
        return models.Notification.objects.filter(user_id=user.id, is_deleted=False)

    # ------------------------------------------
    # Single mark-read action
    # ------------------------------------------
    @swagger_auto_schema(
        operation_id="notifications_mark_read",
        operation_description="Mark a notification as read. Returns basic read-state fields.",
        responses={200: MarkReadResponseSerializer()}
    )
    @action(detail=True, methods=["post"])
    def mark_read(self, request, id=None):
        """
        Mark the specified notification as read.
        """
        notif = self.get_object()
        notif.mark_read()
        resp = {"id": notif.id, "is_read": notif.is_read, "read_at": notif.read_at}
        return Response(MarkReadResponseSerializer(resp).data)

    # ------------------------------------------
    # Bulk mark-read
    # ------------------------------------------
    @swagger_auto_schema(
        operation_id="notifications_bulk_mark_read",
        operation_description="Bulk mark notifications as read for the authenticated user.",
        request_body=BulkMarkReadRequestSerializer,
        responses={200: openapi.Response("Updated count", schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={"updated": openapi.Schema(type=openapi.TYPE_INTEGER)}
        ))}
    )
    @action(detail=False, methods=["post"])  # bulk mark read
    def bulk_mark_read(self, request):
        """
        Bulk mark notifications as read. Accepts JSON: {\"ids\": ["uuid1","uuid2", ...]}
        """
        serializer = BulkMarkReadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data.get("ids", [])
        updated = models.Notification.objects.filter(user_id=request.user.id, id__in=ids).update(is_read=True, read_at=timezone.now())
        return Response({"updated": updated})

    # ------------------------------------------
    # Create notification (internal service entrypoint)
    # ------------------------------------------
    @swagger_auto_schema(
        operation_id="notifications_create",
        operation_description=(
            "Create a notification and schedule deliveries. This endpoint is intended for internal services. "
            "If `user_id` is omitted the implementation may default to request.user where appropriate."
        ),
        request_body=CreateNotificationRequestSerializer,
        responses={201: srl.NotificationSerializer()}
    )
    @action(detail=False, methods=["post"])  # create via API (internal services call this)
    def create_notification(self, request):
        """
        Create a notification record and enqueue delivery processing.
        """
        serializer = CreateNotificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        # Respect provided user_id; in many cases internal systems will provide it.
        notif = services.create_notification(
            user_id=payload.get("user_id"),
            type=payload.get("type"),
            template_key=payload.get("template_key"),
            context=payload.get("context"),
            channel=payload.get("channel"),
            priority=payload.get("priority", "MEDIUM"),
            dedup_key=payload.get("dedup_key"),
            title=payload.get("title"),
            body=payload.get("body"),
        )

        # Use the NotificationSerializer for full output
        return Response(srl.NotificationSerializer(notif).data, status=status.HTTP_201_CREATED)


# -------------------------
# Notification Template management
# -------------------------
class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    CRUD for notification templates used to render titles & bodies.
    """
    queryset = models.NotificationTemplate.objects.all()
    serializer_class = srl.NotificationTemplateSerializer
    permission_classes = [IsAuthenticated]


# -------------------------
# Notification Rules (per-user preferences & suppression)
# -------------------------
class NotificationRuleViewSet(viewsets.ModelViewSet):
    """
    Manage notification rules (quiet hours, channel preferences, condition-driven rules).
    """
    queryset = models.NotificationRule.objects.all()
    serializer_class = srl.NotificationRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Users only see their own rules (admins could extend this).
        """
        user = self.request.user
        return models.NotificationRule.objects.filter(user_id=user.id)
