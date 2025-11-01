from rest_framework import serializers
from .models import Metric, EventStream, Dashboard, AppSetting, FeatureFlag, Alert, EngagementScore

class MetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = Metric
        fields = '__all__'
        read_only_fields = ['id','predicted_value','confidence','captured_at']

class EventStreamSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventStream
        fields = '__all__'
        read_only_fields = ['id','processed','timestamp']

class DashboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dashboard
        fields = '__all__'

class AppSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppSetting
        fields = '__all__'

class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = '__all__'

class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = '__all__'
        read_only_fields = ['triggered_at']

class EngagementScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = EngagementScore
        fields = '__all__'
        read_only_fields = ['calculated_at']