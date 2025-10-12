from rest_framework import serializers
from .models import BridgeAccount, BridgeThread, BridgeMessage, BridgeAutomation, BridgeAnalytics

class BridgeAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BridgeAccount
        fields = '__all__'
        read_only_fields = ['id','last_sync_at']

class BridgeThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = BridgeThread
        fields = '__all__'

class BridgeMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BridgeMessage
        fields = '__all__'
        read_only_fields = ['id','status','received_at','sent_at','ai_category','sentiment_score','is_flagged']

class BridgeAutomationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BridgeAutomation
        fields = '__all__'
        read_only_fields = ['id','last_triggered_at']

class BridgeAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BridgeAnalytics
        fields = '__all__'
        read_only_fields = ['id','top_external_apps','engagement_score']