from django.db import models
import uuid
from django.utils import timezone
from django.db.models import JSONField

class BaseEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True

class User(BaseEntity):
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    username = models.CharField(max_length=150, unique=True)
    display_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    tier = models.CharField(max_length=64, blank=True)  # denormalized current tier
    status = models.CharField(max_length=32, default='active')
    locale = models.CharField(max_length=32, default='en')
    timezone = models.CharField(max_length=64, default='UTC')
    org_id = models.UUIDField(null=True, blank=True)
    preferences = JSONField(default=dict)

    class Meta:
        indexes = [models.Index(fields=['email']), models.Index(fields=['username'])]

class Organization(BaseEntity):
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255, null=True, blank=True)
    ORG_TYPES = [('church','church'),('nonprofit','nonprofit'),('business','business')]
    org_type = models.CharField(max_length=32, choices=ORG_TYPES, default='business')
    default_theme = models.CharField(max_length=64, default='default')
    billing_account_id = models.UUIDField(null=True, blank=True)

class BillingPlan(BaseEntity):
    slug = models.SlugField(max_length=64, unique=True)
    display_name = models.CharField(max_length=255)
    price_per_month = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default='USD')
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Subscription(BaseEntity):
    OWNER_TYPES = [('user','user'),('organization','organization')]
    owner_type = models.CharField(max_length=32, choices=OWNER_TYPES)
    owner_id = models.UUIDField()
    plan = models.ForeignKey(BillingPlan, related_name='subscriptions', on_delete=models.CASCADE)
    status = models.CharField(max_length=32, default='trialing')
    started_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    seat_count = models.IntegerField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['owner_type','owner_id'])]

class Entitlement(BaseEntity):
    plan = models.ForeignKey(BillingPlan, related_name='entitlements', on_delete=models.CASCADE)
    feature_key = models.CharField(max_length=255)
    value = models.TextField()  # numeric or boolean or JSON as string
    unit = models.CharField(max_length=32, default='count')

    class Meta:
        unique_together = [('plan','feature_key')]

class UsageQuota(BaseEntity):
    OWNER_TYPES = [('user','user'),('organization','organization')]
    owner_type = models.CharField(max_length=32, choices=OWNER_TYPES)
    owner_id = models.UUIDField()
    feature_key = models.CharField(max_length=255)
    period_start = models.DateField()
    period_end = models.DateField()
    used = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    limit = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['owner_type','owner_id','feature_key','period_start'])]

class BillingInvoice(BaseEntity):
    subscription = models.ForeignKey(Subscription, related_name='invoices', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='USD')
    issued_at = models.DateTimeField(default=timezone.now)
    paid_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, default='unpaid')

class FeatureFlag(BaseEntity):
    key = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    enabled_by_default = models.BooleanField(default=False)

class PlanFeature(BaseEntity):
    plan = models.ForeignKey(BillingPlan, related_name='plan_features', on_delete=models.CASCADE)
    feature_flag = models.ForeignKey(FeatureFlag, related_name='plan_features', on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False)
    config = JSONField(default=dict)

    class Meta:
        unique_together = [('plan','feature_flag')]

class PartnerSettings(BaseEntity):
    org = models.OneToOneField(Organization, related_name='partner_settings', on_delete=models.CASCADE)
    custom_domain = models.CharField(max_length=255, null=True, blank=True)
    branding_config = JSONField(default=dict)
    low_fee_donation_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    priority_support = models.BooleanField(default=False)
    api_access = models.BooleanField(default=False)

class ImpactAnalyticsSettings(BaseEntity):
    org = models.OneToOneField(Organization, related_name='impact_settings', on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False)
    import_offline_data_allowed = models.BooleanField(default=False)
    export_formats = JSONField(default=list)

class DonationCampaign(BaseEntity):
    org = models.ForeignKey(Organization, related_name='donation_campaigns', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    goal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    raised_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default='USD')
    starts_at = models.DateField()
    ends_at = models.DateField(null=True, blank=True)
    public = models.BooleanField(default=True)

class EventTicketing(BaseEntity):
    org = models.ForeignKey(Organization, related_name='tickets', on_delete=models.CASCADE)
    event_id = models.UUIDField()
    ticket_type = models.CharField(max_length=128)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='USD')
    capacity = models.IntegerField(null=True, blank=True)

class HolographicRoom(BaseEntity):
    org = models.ForeignKey(Organization, related_name='holographic_rooms', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255)
    enabled = models.BooleanField(default=False)
    ar_required_assets = JSONField(default=list)

class QuantumEncryptionSetting(BaseEntity):
    OWNER_TYPES = [('user','user'),('organization','organization')]
    owner_type = models.CharField(max_length=32, choices=OWNER_TYPES)
    owner_id = models.UUIDField()
    enabled = models.BooleanField(default=False)
    algorithm = models.CharField(max_length=255, blank=True)

class CustomAIModel(BaseEntity):
    org = models.ForeignKey(Organization, related_name='custom_ai_models', on_delete=models.CASCADE)
    model_name = models.CharField(max_length=255)
    training_data_fingerprint = models.CharField(max_length=255, blank=True)
    deployed = models.BooleanField(default=False)
    last_trained_at = models.DateTimeField(null=True, blank=True)
