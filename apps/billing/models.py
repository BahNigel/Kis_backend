from __future__ import annotations

from django.db import models
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import BaseEntity


class WalletAccount(BaseEntity):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet_account",
    )
    balance_cents = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=8, default="USD")
    status = models.CharField(max_length=30, default="active")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "status"]) ]

    def __str__(self) -> str:
        return f"Wallet({self.user_id}) {self.balance_cents} {self.currency}"


class CreditAccount(BaseEntity):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="credit_account",
    )
    credits = models.IntegerField(default=0)
    locked_credits = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user"]) ]

    def __str__(self) -> str:
        return f"Credits({self.user_id}) {self.credits}"


class WalletLedgerEntry(BaseEntity):
    KIND_CHOICES = [
        ("deposit", "Deposit"),
        ("conversion_cash_to_credits", "Convert cash to credits"),
        ("conversion_credits_to_cash", "Convert credits to cash"),
        ("transfer_in", "Transfer in"),
        ("transfer_out", "Transfer out"),
        ("tier_upgrade", "Tier upgrade"),
        ("promo", "Promo"),
        ("admin_adjust", "Admin adjustment"),
        ("purchase", "Purchase"),
        ("refund", "Refund"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet_ledger",
    )
    kind = models.CharField(max_length=64, choices=KIND_CHOICES)
    amount_cents = models.BigIntegerField(default=0)
    credits_delta = models.IntegerField(default=0)
    balance_after_cents = models.BigIntegerField(default=0)
    credits_after = models.IntegerField(default=0)
    status = models.CharField(max_length=32, default="posted")
    reference = models.CharField(max_length=255, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "kind"]),
            models.Index(fields=["created_at"]),
        ]


class WalletTransaction(BaseEntity):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet_transactions",
    )
    provider = models.CharField(max_length=100, default="flutterwave")
    method = models.CharField(max_length=100, blank=True)
    amount_cents = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=8, default="USD")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")
    tx_ref = models.CharField(max_length=255, unique=True)
    provider_ref = models.CharField(max_length=255, blank=True)
    payment_url = models.URLField(blank=True)
    meta = models.JSONField(default=dict, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["tx_ref"]),
        ]


class PromoCode(BaseEntity):
    code = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True)
    cash_bonus_cents = models.BigIntegerField(default=0)
    credit_bonus = models.IntegerField(default=0)
    usage_limit = models.IntegerField(null=True, blank=True)
    used_count = models.IntegerField(default=0)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["code"]) ]


class PromoRedemption(BaseEntity):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="promo_redemptions",
    )
    promo = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name="redemptions")
    redeemed_at = models.DateTimeField(default=timezone.now)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("user", "promo")
