from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, OrganizationViewSet, BillingPlanViewSet, SubscriptionViewSet, EntitlementViewSet,
    UsageQuotaViewSet, BillingInvoiceViewSet, FeatureFlagViewSet, PlanFeatureViewSet, PartnerSettingsViewSet,
    ImpactAnalyticsSettingsViewSet, DonationCampaignViewSet, EventTicketingViewSet, HolographicRoomViewSet,
    QuantumEncryptionSettingViewSet, CustomAIModelViewSet,
)

router = DefaultRouter()
router.register('users', UserViewSet)
router.register('organizations', OrganizationViewSet)
router.register('plans', BillingPlanViewSet)
router.register('subscriptions', SubscriptionViewSet)
router.register('entitlements', EntitlementViewSet)
router.register('usage', UsageQuotaViewSet)
router.register('invoices', BillingInvoiceViewSet)
router.register('flags', FeatureFlagViewSet)
router.register('plan-features', PlanFeatureViewSet)
router.register('partner-settings', PartnerSettingsViewSet)
router.register('impact-settings', ImpactAnalyticsSettingsViewSet)
router.register('campaigns', DonationCampaignViewSet)
router.register('tickets', EventTicketingViewSet)
router.register('holograms', HolographicRoomViewSet)
router.register('quantum', QuantumEncryptionSettingViewSet)
router.register('ai-models', CustomAIModelViewSet)

urlpatterns = router.urls