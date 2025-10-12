from rest_framework import serializers
from .models import (
    User, Organization, BillingPlan, Subscription, Entitlement, UsageQuota, BillingInvoice,
    FeatureFlag, PlanFeature, PartnerSettings, ImpactAnalyticsSettings, DonationCampaign,
    EventTicketing, HolographicRoom, QuantumEncryptionSetting, CustomAIModel,
)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'
        read_only_fields = ['id','created_at','updated_at']

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'

class BillingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPlan
        fields = '__all__'

class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = '__all__'

class EntitlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Entitlement
        fields = '__all__'

class UsageQuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageQuota
        fields = '__all__'

class BillingInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingInvoice
        fields = '__all__'

class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = '__all__'

class PlanFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanFeature
        fields = '__all__'

class PartnerSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerSettings
        fields = '__all__'

class ImpactAnalyticsSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImpactAnalyticsSettings
        fields = '__all__'

class DonationCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = DonationCampaign
        fields = '__all__'

class EventTicketingSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventTicketing
        fields = '__all__'

class HolographicRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = HolographicRoom
        fields = '__all__'

class QuantumEncryptionSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuantumEncryptionSetting
        fields = '__all__'

class CustomAIModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomAIModel
        fields = '__all__'