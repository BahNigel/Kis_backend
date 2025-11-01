# events/views.py
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.db import transaction
from django.utils import timezone

# Swagger / OpenAPI helpers (drf-yasg)
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from . import models, serializers as srl, permissions as perms

# ---------------------------------------------------------------------
# small request serializers for documented endpoints
# ---------------------------------------------------------------------
class PurchaseRequestSerializer(serializers.Serializer):
    qty = serializers.IntegerField(min_value=1, default=1, help_text="Quantity of tickets to purchase")

class PurchaseResponseSerializer(serializers.Serializer):
    id = serializers.CharField()
    ticket = serializers.CharField()
    buyer_id = serializers.CharField()
    qty = serializers.IntegerField()
    total_cents = serializers.IntegerField()
    status = serializers.CharField()
    purchased_at = serializers.DateTimeField()

class CheckInQRSerializer(serializers.Serializer):
    payload = serializers.CharField(help_text="QR payload containing attendance id or ticket sale id")

class AttendanceResponseSerializer(serializers.Serializer):
    id = serializers.CharField()
    event = serializers.CharField()
    session = serializers.CharField(allow_null=True)
    user_id = serializers.CharField()
    status = serializers.CharField()
    checked_in_at = serializers.DateTimeField(allow_null=True)
    check_in_method = serializers.CharField(allow_null=True)


# ---------------------------------------------------------------------
# Event management (CRUD + lifecycle actions)
# ---------------------------------------------------------------------
class EventViewSet(viewsets.ModelViewSet):
    """
    Event management endpoints.

    Features:
    - CRUD for Event objects
    - Lifecycle actions: publish, cancel
    - Events include sessions, capacity, visibility, etc.
    """
    queryset = models.Event.objects.all()
    serializer_class = srl.EventSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, perms.IsEventOwnerOrReadOnly]
    lookup_field = "id"

    @swagger_auto_schema(
        operation_id="publishEvent",
        operation_description="Mark the event as published (owner-only).",
        responses={200: srl.EventSerializer()},
    )
    @action(detail=True, methods=["post"], permission_classes=[perms.IsEventOwnerOrReadOnly])
    def publish(self, request, id=None):
        """
        Publish event
        """
        event = self.get_object()
        event.status = "published"
        event.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(event).data)

    @swagger_auto_schema(
        operation_id="cancelEvent",
        operation_description="Cancel the event (owner-only).",
        responses={200: srl.EventSerializer()},
    )
    @action(detail=True, methods=["post"], permission_classes=[perms.IsEventOwnerOrReadOnly])
    def cancel(self, request, id=None):
        """
        Cancel event
        """
        event = self.get_object()
        event.status = "cancelled"
        event.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(event).data)


# ---------------------------------------------------------------------
# Ticketing features (ticket CRUD + purchase)
# ---------------------------------------------------------------------
class TicketViewSet(viewsets.ModelViewSet):
    """
    Ticketing endpoints.

    Features:
    - CRUD on tickets (tiers, sku, price, quantity)
    - Quick purchase endpoint (transactionally reserves stock and creates TicketSale)
    """
    queryset = models.Ticket.objects.select_related("event").all()
    serializer_class = srl.TicketSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        method="post",
        operation_id="purchaseTicket",
        operation_description=(
            "Purchase a ticket. This is a simplified transactional endpoint that reserves "
            "quantity and creates a TicketSale. Real payment integration must be added "
            "in services/payment layer."
        ),
        request_body=PurchaseRequestSerializer,
        responses={
            201: PurchaseResponseSerializer,
            400: openapi.Response("Bad Request", schema=openapi.Schema(type=openapi.TYPE_OBJECT))
        },
    )
    @action(detail=True, methods=["post"])  # quick purchase endpoint
    @transaction.atomic
    def purchase(self, request, pk=None):
        """
        Purchase the ticket identified by `pk`.

        Expected body: {"qty": 2}
        """
        ticket = self.get_object()
        qty = int(request.data.get("qty", 1))
        buyer_id = request.user.id

        if ticket.quantity_remaining < qty:
            return Response({"error": "not enough tickets"}, status=status.HTTP_400_BAD_REQUEST)

        # reserve (atomic)
        ticket.quantity_remaining = ticket.quantity_remaining - qty
        ticket.save(update_fields=["quantity_remaining", "updated_at"])

        sale = models.TicketSale.objects.create(
            ticket=ticket,
            buyer_id=buyer_id,
            qty=qty,
            total_cents=ticket.price_cents * qty,
            status="completed",
        )

        # Use serializer to craft response if available, otherwise return subset
        resp_data = {
            "id": str(sale.id),
            "ticket": str(ticket.id),
            "buyer_id": str(sale.buyer_id),
            "qty": sale.qty,
            "total_cents": sale.total_cents,
            "status": sale.status,
            "purchased_at": sale.purchased_at,
        }
        return Response(resp_data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------
# Attendance & Check-in (RSVP, check-in via QR)
# ---------------------------------------------------------------------
class AttendanceViewSet(viewsets.ModelViewSet):
    """
    Attendance endpoints.

    Features:
    - CRUD on attendance records
    - Check-in by QR (simplified; in production validate signed QR payloads)
    """
    queryset = models.Attendance.objects.all()
    serializer_class = srl.AttendanceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        method="post",
        operation_id="checkinByQR",
        operation_description=(
            "Check in by scanning a QR code. For production this should validate "
            "signed payloads, timestamps and optionally require device authentication."
        ),
        request_body=CheckInQRSerializer,
        responses={
            200: AttendanceResponseSerializer,
            404: openapi.Response("Not Found"),
            400: openapi.Response("Bad Request"),
        },
    )
    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticatedOrReadOnly])
    def checkin_qr(self, request):
        """
        Accept a QR payload that contains an attendance id or ticket sale id.
        NOTE: This is simplified — real implementation validates signatures & timestamps.
        """
        payload = request.data.get("payload")
        if not payload:
            return Response({"error": "missing payload"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            att = models.Attendance.objects.get(id=payload)
        except models.Attendance.DoesNotExist:
            return Response({"error": "attendance not found"}, status=status.HTTP_404_NOT_FOUND)

        att.status = "checked_in"
        att.checked_in_at = timezone.now()
        att.check_in_method = "qr"
        att.save(update_fields=["status", "checked_in_at", "check_in_method", "updated_at"])

        return Response(AttendanceResponseSerializer(att).data)
