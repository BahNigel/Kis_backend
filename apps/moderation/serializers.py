# moderation/serializers.py
from rest_framework import serializers
from . import models


class FlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Flag
        fields = "__all__"


class ModerationActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ModerationAction
        fields = "__all__"


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AuditLog
        fields = "__all__"


class UserReputationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserReputation
        fields = "__all__"


class ModerationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ModerationRule
        fields = "__all__"


class SafetyAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SafetyAlert
        fields = "__all__"
