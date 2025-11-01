

"""
Commerce Django App (commerce)

Purpose:
- Full-featured marketplace & shop platform focusing on security, authenticity, and advanced commerce features.
- Built to integrate with the AI & Automation app for verification, recommendations and fraud detection.

Key capabilities implemented:
- Shop creation + KYC-style verification workflow (ShopVerificationRequest)
- Product catalog with authenticity checks (ProductAuthenticityCheck)
- Orders, Payments (provider hooks), Promotions, Subscriptions, Loyalty
- FraudSignal model and async fraud evaluation
- Audit logs for compliance and traceability
- Background tasks (Celery) for verification & fraud computation
- Admin panels for manual review & audit
- Stubs/adapters in services.py to connect to third-party verifiers, OCR, blockchain verification, or image-forensics providers

Free-tier behavior / safety notes:
- Verification & authenticity adapters are stubbed for free-tier testing. Replace adapters with paid providers when ready (examples: Jumio, Onfido, Trulioo for KYC; Chainpoint or OpenTimestamps for blockchain anchoring; Virustotal/ImageForensics APIs for image checks).
- Use django-storages + S3/Backblaze for secure document storage.
- Enable server-side scanning and virus checks for user uploads.

Quick install:
1. Add "commerce" to INSTALLED_APPS.
2. Ensure DRF and Celery are installed and configured.
3. Run migrations: python manage.py makemigrations commerce && python manage.py migrate
4. Start Celery worker: celery -A your_project worker -l info
5. Configure object storage and set secure upload buckets.

Security & authenticity recommended next steps:
- Integrate a KYC provider for automated identity verification.
- Connect image-forensics models and brand catalogs for counterfeit detection.
- Use blockchain anchoring for high-value goods (store certificate hash on-chain).
- Add manual review queues with role-based access controls for reviewers.
- Add rate-limits, merchant onboarding checks, scoring thresholds and escalation rules.

"""

import uuid
from django.db import models
from django.db.models import JSONField
from django.conf import settings


class BaseEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True


class Shop(BaseEntity):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shops')
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    branding = JSONField(default=dict, blank=True)
    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(max_length=20, default='UNVERIFIED')  # PENDING | VERIFIED | REJECTED
    rating_avg = models.FloatField(default=0.0)
    rating_count = models.IntegerField(default=0)
    followers_count = models.IntegerField(default=0)
    social_links = JSONField(default=dict, blank=True)
    analytics = JSONField(default=dict, blank=True)
    trust_badges = JSONField(default=list, blank=True)  # e.g., ['kyc','authenticity','secure-pay']

    class Meta:
        indexes = [models.Index(fields=['slug'])]

    def __str__(self):
        return f"{self.name} ({self.owner})"


class ShopVerificationRequest(BaseEntity):
    SHOP_DOC_TYPES = [('ID', 'ID Document'), ('BUSINESS_REG', 'Business Registration'), ('INVOICE', 'Proof of Sales')]
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='verification_requests')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, default='PENDING')  # PENDING | IN_REVIEW | APPROVED | REJECTED
    documents = JSONField(default=list, blank=True)  # list of {type, url, meta}
    reviewer_notes = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    risk_score = models.FloatField(null=True, blank=True)


class Product(BaseEntity):
    INVENTORY_TYPES = [('PHYSICAL', 'Physical'), ('DIGITAL', 'Digital'), ('SERVICE', 'Service')]
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='products')
    sku = models.CharField(max_length=128, unique=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='XAF')
    inventory_type = models.CharField(max_length=20, choices=INVENTORY_TYPES, default='PHYSICAL')
    stock_qty = models.IntegerField(default=0)
    variants = JSONField(default=list, blank=True)
    categories = JSONField(default=list, blank=True)
    attributes = JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    rating_avg = models.FloatField(default=0.0)
    rating_count = models.IntegerField(default=0)
    ai_score = models.FloatField(default=0.0)
    ar_preview_url = models.URLField(blank=True)
    authenticity_status = models.CharField(max_length=20, default='UNKNOWN')  # UNKNOWN | VERIFIED | FLAGGED
    authenticity_proof = JSONField(default=dict, blank=True)  # e.g., blockchain anchor, certificate

    class Meta:
        indexes = [models.Index(fields=['sku']), models.Index(fields=['slug'])]

    def __str__(self):
        return f"{self.name} [{self.sku}]"


class ProductAuthenticityCheck(BaseEntity):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='auth_checks')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    provider = models.CharField(max_length=100, default='local_ai')
    status = models.CharField(max_length=20, default='PENDING')  # PENDING | PROCESSING | VERIFIED | FLAGGED | ERROR
    result = JSONField(default=dict, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)


class Order(BaseEntity):
    ORDER_STATUS = [('PENDING','Pending'),('PAID','Paid'),('SHIPPED','Shipped'),('DELIVERED','Delivered'),('CANCELLED','Cancelled'),('REFUNDED','Refunded')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='PENDING')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='XAF')
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_code = models.CharField(max_length=64, blank=True)
    referral_code = models.CharField(max_length=64, blank=True)


class OrderItem(BaseEntity):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='XAF')
    variant = JSONField(default=dict, blank=True)
    applied_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)


class Payment(BaseEntity):
    PAYMENT_STATUS = [('PENDING','Pending'),('SUCCESS','Success'),('FAILED','Failed'),('REFUNDED','Refunded')]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    provider = models.CharField(max_length=100)
    method = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='XAF')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='PENDING')
    provider_ref = models.CharField(max_length=255, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    fraud_score = models.FloatField(null=True, blank=True)


class Promotion(BaseEntity):
    DISCOUNT_TYPES = [('PERCENT','Percent'),('FIXED','Fixed')]
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='promotions')
    code = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=8, decimal_places=2)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    usage_limit = models.IntegerField(null=True, blank=True)
    used_count = models.IntegerField(default=0)
    applicable_products = JSONField(default=list, blank=True)
    social_boost = models.BooleanField(default=False)


class Subscription(BaseEntity):
    STATUS = [('ACTIVE','Active'),('PAUSED','Paused'),('CANCELLED','Cancelled')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shop_subscriptions')
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, null=True, blank=True, related_name='shop_subscriptions')
    plan_name = models.CharField(max_length=128)
    status = models.CharField(max_length=20, choices=STATUS, default='ACTIVE')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='XAF')
    perks = JSONField(default=dict, blank=True)


class LoyaltyPoint(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loyalty_points')
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, null=True, blank=True)
    points = models.IntegerField()
    earned_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)


class ShopFollow(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='follows')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='followers')
    followed_at = models.DateTimeField(auto_now_add=True)


class ProductShare(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    shared_at = models.DateTimeField(auto_now_add=True)
    platform = models.CharField(max_length=64)


class AIRecommendation(BaseEntity):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    target_type = models.CharField(max_length=50)  # Product | Shop
    target_id = models.UUIDField()
    score = models.FloatField()
    reason = models.TextField(blank=True)


class AuditLog(BaseEntity):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    target_type = models.CharField(max_length=255)
    target_id = models.UUIDField(null=True, blank=True)
    metadata = JSONField(default=dict, blank=True)


class FraudSignal(BaseEntity):
    source = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)  # order, payment, shop, product
    entity_id = models.UUIDField()
    score = models.FloatField()
    details = JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False)


