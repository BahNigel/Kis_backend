
from rest_framework import serializers
from . import models


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.NotificationTemplate
        fields = "__all__"


class NotificationDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.NotificationDelivery
        fields = "__all__"


class NotificationSerializer(serializers.ModelSerializer):
    deliveries = NotificationDeliverySerializer(many=True, read_only=True)

    class Meta:
        model = models.Notification
        fields = "__all__"
        read_only_fields = ("delivered_at", "read_at", "is_read")


class NotificationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.NotificationRule
        fields = "__all__"


class NotificationDigestSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.NotificationDigest
        fields = "__all__"
