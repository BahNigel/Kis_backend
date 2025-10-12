from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import (
    User, Organization, BillingPlan, Subscription, Entitlement, UsageQuota, BillingInvoice,
    FeatureFlag, PlanFeature, PartnerSettings, ImpactAnalyticsSettings, DonationCampaign,
    EventTicketing, HolographicRoom, QuantumEncryptionSetting, CustomAIModel,
)
from .serializers import (
    UserSerializer, OrganizationSerializer, BillingPlanSerializer, SubscriptionSerializer, EntitlementSerializer,
    UsageQuotaSerializer, BillingInvoiceSerializer, FeatureFlagSerializer, PlanFeatureSerializer, PartnerSettingsSerializer,
    ImpactAnalyticsSettingsSerializer, DonationCampaignSerializer, EventTicketingSerializer, HolographicRoomSerializer,
    QuantumEncryptionSettingSerializer, CustomAIModelSerializer,
)
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter, OpenApiTypes, OpenApiExample
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .tasks import reconcile_subscription, generate_invoice

# Common query params
OWNER_FILTER_PARAMS = [
    OpenApiParameter(name='owner_type', required=False, location=OpenApiParameter.QUERY, type=OpenApiTypes.STR),
    OpenApiParameter(name='owner_id', required=False, location=OpenApiParameter.QUERY, type=OpenApiTypes.UUID),
]

@extend_schema_view(
    list=extend_schema(summary='List Users', responses={200: UserSerializer(many=True)}, tags=['Users']),
    retrieve=extend_schema(summary='Retrieve User', responses={200: UserSerializer}, tags=['Users']),
    create=extend_schema(summary='Create User', request=UserSerializer, responses={201: UserSerializer}, tags=['Users']),
)
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['email','username','display_name']

@extend_schema_view(
    list=extend_schema(summary='List Organizations', responses={200: OrganizationSerializer(many=True)}, tags=['Organizations']),
    retrieve=extend_schema(summary='Retrieve Organization', responses={200: OrganizationSerializer}, tags=['Organizations']),
    create=extend_schema(summary='Create Organization', request=OrganizationSerializer, responses={201: OrganizationSerializer}, tags=['Organizations']),
)
class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [SearchFilter]
    search_fields = ['name','domain']

@extend_schema_view(
    list=extend_schema(summary='List Billing Plans', responses={200: BillingPlanSerializer(many=True)}, tags=['Billing']),
    retrieve=extend_schema(summary='Retrieve Billing Plan', responses={200: BillingPlanSerializer}, tags=['Billing']),
    create=extend_schema(summary='Create Billing Plan', request=BillingPlanSerializer, responses={201: BillingPlanSerializer}, tags=['Billing']),
)
class BillingPlanViewSet(viewsets.ModelViewSet):
    queryset = BillingPlan.objects.all()
    serializer_class = BillingPlanSerializer
    permission_classes = [IsAuthenticated]

@extend_schema_view(
    list=extend_schema(summary='List Subscriptions', responses={200: SubscriptionSerializer(many=True)}, tags=['Subscriptions']),
    retrieve=extend_schema(summary='Retrieve Subscription', responses={200: SubscriptionSerializer}, tags=['Subscriptions']),
    create=extend_schema(summary='Create Subscription', request=SubscriptionSerializer, responses={201: SubscriptionSerializer}, tags=['Subscriptions']),
)
class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['owner_type','owner_id','plan']

    @extend_schema(summary='Reconcile subscription (webhook/refresh)', responses={200: OpenApiResponse(description='reconciled')}, tags=['Subscriptions'])
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reconcile(self, request, pk=None):
        sub = self.get_object()
        reconcile_subscription.delay(str(sub.id))
        return Response({'detail':'reconciliation started'})

@extend_schema_view(
    list=extend_schema(summary='List Entitlements', responses={200: EntitlementSerializer(many=True)}, tags=['Entitlements']),
    create=extend_schema(summary='Create Entitlement', request=EntitlementSerializer, responses={201: EntitlementSerializer}, tags=['Entitlements']),
)
class EntitlementViewSet(viewsets.ModelViewSet):
    queryset = Entitlement.objects.all()
    serializer_class = EntitlementSerializer
    permission_classes = [IsAuthenticated]

@extend_schema_view(
    list=extend_schema(summary='List Usage Quotas', responses={200: UsageQuotaSerializer(many=True)}, tags=['Usage']),
    create=extend_schema(summary='Create Usage Quota', request=UsageQuotaSerializer, responses={201: UsageQuotaSerializer}, tags=['Usage']),
)
class UsageQuotaViewSet(viewsets.ModelViewSet):
    queryset = UsageQuota.objects.all()
    serializer_class = UsageQuotaSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['owner_type','owner_id','feature_key','period_start']

@extend_schema_view(
    list=extend_schema(summary='List Invoices', responses={200: BillingInvoiceSerializer(many=True)}, tags=['Billing']),
    create=extend_schema(summary='Generate Invoice', request=BillingInvoiceSerializer, responses={201: BillingInvoiceSerializer}, tags=['Billing']),
)
class BillingInvoiceViewSet(viewsets.ModelViewSet):
    queryset = BillingInvoice.objects.all()
    serializer_class = BillingInvoiceSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Generate invoice (async)', responses={200: OpenApiResponse(description='invoice queued')}, tags=['Billing'])
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def generate(self, request):
        # request should contain subscription ids or owner filters
        generate_invoice.delay(request.data)
        return Response({'detail':'invoice generation queued'})

@extend_schema_view(
    list=extend_schema(summary='List Feature Flags', responses={200: FeatureFlagSerializer(many=True)}, tags=['Flags']),
    create=extend_schema(summary='Create Feature Flag', request=FeatureFlagSerializer, responses={201: FeatureFlagSerializer}, tags=['Flags']),
)
class FeatureFlagViewSet(viewsets.ModelViewSet):
    queryset = FeatureFlag.objects.all()
    serializer_class = FeatureFlagSerializer
    permission_classes = [IsAuthenticated]

@extend_schema_view(
    list=extend_schema(summary='List Plan Features', responses={200: PlanFeatureSerializer(many=True)}, tags=['Flags']),
    create=extend_schema(summary='Create Plan Feature', request=PlanFeatureSerializer, responses={201: PlanFeatureSerializer}, tags=['Flags']),
)
class PlanFeatureViewSet(viewsets.ModelViewSet):
    queryset = PlanFeature.objects.all()
    serializer_class = PlanFeatureSerializer
    permission_classes = [IsAuthenticated]

@extend_schema_view(
    retrieve=extend_schema(summary='Retrieve Partner Settings', responses={200: PartnerSettingsSerializer}, tags=['Partner']),
    update=extend_schema(summary='Update Partner Settings', request=PartnerSettingsSerializer, responses={200: PartnerSettingsSerializer}, tags=['Partner']),
)
class PartnerSettingsViewSet(viewsets.ModelViewSet):
    queryset = PartnerSettings.objects.all()
    serializer_class = PartnerSettingsSerializer
    permission_classes = [IsAuthenticated]

@extend_schema_view(
    retrieve=extend_schema(summary='Retrieve Impact Analytics Settings', responses={200: ImpactAnalyticsSettingsSerializer}, tags=['Partner']),
    update=extend_schema(summary='Update Impact Analytics Settings', request=ImpactAnalyticsSettingsSerializer, responses={200: ImpactAnalyticsSettingsSerializer}, tags=['Partner']),
)
class ImpactAnalyticsSettingsViewSet(viewsets.ModelViewSet):
    queryset = ImpactAnalyticsSettings.objects.all()
    serializer_class = ImpactAnalyticsSettingsSerializer
    permission_classes = [IsAuthenticated]

@extend_schema_view(
    list=extend_schema(summary='List Donation Campaigns', responses={200: DonationCampaignSerializer(many=True)}, tags=['Partner']),
    create=extend_schema(summary='Create Donation Campaign', request=DonationCampaignSerializer, responses={201: DonationCampaignSerializer}, tags=['Partner']),
)
class DonationCampaignViewSet(viewsets.ModelViewSet):
    queryset = DonationCampaign.objects.all()
    serializer_class = DonationCampaignSerializer
    permission_classes = [IsAuthenticated]

@extend_schema_view(
    list=extend_schema(summary='List Event Tickets', responses={200: EventTicketingSerializer(many=True)}, tags=['Partner']),
    create=extend_schema(summary='Create Event Ticket Type', request=EventTicketingSerializer, responses={201: EventTicketingSerializer}, tags=['Partner']),
)
class EventTicketingViewSet(viewsets.ModelViewSet):
    queryset = EventTicketing.objects.all()
    serializer_class = EventTicketingSerializer
    permission_classes = [IsAuthenticated]

@extend_schema_view(
    list=extend_schema(summary='List Holographic Rooms', responses={200: HolographicRoomSerializer(many=True)}, tags=['Premium']),
    create=extend_schema(summary='Create Holographic Room', request=HolographicRoomSerializer, responses={201: HolographicRoomSerializer}, tags=['Premium']),
)
class HolographicRoomViewSet(viewsets.ModelViewSet):
    queryset = HolographicRoom.objects.all()
    serializer_class = HolographicRoomSerializer
    permission_classes = [IsAuthenticated]

@extend_schema_view(
    list=extend_schema(summary='List Quantum Encryption Settings', responses={200: QuantumEncryptionSettingSerializer(many=True)}, tags=['Premium']),
    create=extend_schema(summary='Create Quantum Encryption Setting', request=QuantumEncryptionSettingSerializer, responses={201: QuantumEncryptionSettingSerializer}, tags=['Premium']),
)
class QuantumEncryptionSettingViewSet(viewsets.ModelViewSet):
    queryset = QuantumEncryptionSetting.objects.all()
    serializer_class = QuantumEncryptionSettingSerializer
    permission_classes = [IsAuthenticated]

@extend_schema_view(
    list=extend_schema(summary='List Custom AI Models', responses={200: CustomAIModelSerializer(many=True)}, tags=['Premium']),
    create=extend_schema(summary='Create Custom AI Model', request=CustomAIModelSerializer, responses={201: CustomAIModelSerializer}, tags=['Premium']),
)
class CustomAIModelViewSet(viewsets.ModelViewSet):
    queryset = CustomAIModel.objects.all()
    serializer_class = CustomAIModelSerializer
    permission_classes = [IsAuthenticated]