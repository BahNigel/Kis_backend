
from rest_framework import serializers
from . import models


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Seat
        fields = "__all__"


class SeatMapSerializer(serializers.ModelSerializer):
    seats = SeatSerializer(many=True, read_only=True)

    class Meta:
        model = models.SeatMap
        fields = "__all__"


class VenueSerializer(serializers.ModelSerializer):
    seat_maps = SeatMapSerializer(many=True, read_only=True)

    class Meta:
        model = models.Venue
        fields = "__all__"


class EventSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EventSession
        fields = "__all__"


class EventSerializer(serializers.ModelSerializer):
    sessions = EventSessionSerializer(many=True, read_only=True)

    class Meta:
        model = models.Event
        fields = "__all__"


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Ticket
        fields = "__all__"


class TicketSaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TicketSale
        fields = "__all__"


class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Attendance
        fields = "__all__"
