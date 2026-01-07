from __future__ import annotations

from rest_framework import serializers

from .models import WalletAccount, CreditAccount, WalletLedgerEntry, WalletTransaction, PromoCode


class WalletAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletAccount
        fields = ["id", "balance_cents", "currency", "status", "metadata", "created_at"]


class CreditAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditAccount
        fields = ["id", "credits", "locked_credits", "metadata", "created_at"]


class WalletLedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletLedgerEntry
        fields = [
            "id",
            "kind",
            "amount_cents",
            "credits_delta",
            "balance_after_cents",
            "credits_after",
            "status",
            "reference",
            "meta",
            "created_at",
        ]


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = [
            "id",
            "provider",
            "method",
            "amount_cents",
            "currency",
            "status",
            "tx_ref",
            "provider_ref",
            "payment_url",
            "meta",
            "created_at",
        ]


class PromoCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCode
        fields = [
            "id",
            "code",
            "description",
            "cash_bonus_cents",
            "credit_bonus",
            "usage_limit",
            "used_count",
            "starts_at",
            "ends_at",
            "is_active",
            "metadata",
        ]
