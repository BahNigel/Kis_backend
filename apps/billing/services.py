from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, Subscription, AccountTier
from apps.commerce.models import LoyaltyPoint
from .models import WalletAccount, CreditAccount, WalletLedgerEntry, WalletTransaction

CREDITS_PER_USD = 20


@dataclass
class ConversionResult:
    amount_cents: int
    credits: int


def cents_to_credits(amount_cents: int) -> int:
    return max(0, (amount_cents * CREDITS_PER_USD) // 100)


def credits_to_cents(credits: int) -> int:
    return max(0, (credits * 100) // CREDITS_PER_USD)


def get_wallet_account(user: User) -> WalletAccount:
    wallet, _ = WalletAccount.objects.get_or_create(user=user, defaults={"balance_cents": 0, "currency": "USD"})
    return wallet


def get_credit_account(user: User) -> CreditAccount:
    credits, _ = CreditAccount.objects.get_or_create(user=user, defaults={"credits": 0})
    return credits


def record_ledger(
    *,
    user: User,
    kind: str,
    amount_cents: int = 0,
    credits_delta: int = 0,
    reference: str = "",
    meta: Optional[dict] = None,
) -> WalletLedgerEntry:
    meta = meta or {}
    wallet = get_wallet_account(user)
    credit = get_credit_account(user)
    wallet.balance_cents += amount_cents
    credit.credits += credits_delta
    wallet.save(update_fields=["balance_cents", "updated_at"])
    credit.save(update_fields=["credits", "updated_at"])
    return WalletLedgerEntry.objects.create(
        user=user,
        kind=kind,
        amount_cents=amount_cents,
        credits_delta=credits_delta,
        balance_after_cents=wallet.balance_cents,
        credits_after=credit.credits,
        reference=reference,
        meta=meta,
    )


def convert_cash_to_credits(user: User, amount_cents: int) -> ConversionResult:
    if amount_cents <= 0:
        raise ValueError("Amount must be greater than 0.")
    credits = cents_to_credits(amount_cents)
    if credits <= 0:
        raise ValueError("Amount too small to convert to credits.")

    with transaction.atomic():
        wallet = get_wallet_account(user)
        if wallet.balance_cents < amount_cents:
            raise ValueError("Insufficient wallet balance.")
        record_ledger(
            user=user,
            kind="conversion_cash_to_credits",
            amount_cents=-amount_cents,
            credits_delta=credits,
            reference="cash_to_credits",
        )
    return ConversionResult(amount_cents=amount_cents, credits=credits)


def convert_credits_to_cash(user: User, credits: int) -> ConversionResult:
    if credits <= 0:
        raise ValueError("Credits must be greater than 0.")
    amount_cents = credits_to_cents(credits)
    if amount_cents <= 0:
        raise ValueError("Credits too small to convert to cash.")

    with transaction.atomic():
        credit = get_credit_account(user)
        if credit.credits < credits:
            raise ValueError("Insufficient credits.")
        record_ledger(
            user=user,
            kind="conversion_credits_to_cash",
            amount_cents=amount_cents,
            credits_delta=-credits,
            reference="credits_to_cash",
        )
    return ConversionResult(amount_cents=amount_cents, credits=credits)


def transfer_balance(
    *,
    sender: User,
    recipient: User,
    amount_cents: int = 0,
    credits: int = 0,
) -> Tuple[WalletLedgerEntry, WalletLedgerEntry]:
    if amount_cents <= 0 and credits <= 0:
        raise ValueError("Amount or credits must be greater than 0.")

    with transaction.atomic():
        if amount_cents > 0:
            sender_wallet = get_wallet_account(sender)
            if sender_wallet.balance_cents < amount_cents:
                raise ValueError("Insufficient wallet balance.")
            record_ledger(
                user=sender,
                kind="transfer_out",
                amount_cents=-amount_cents,
                reference=f"transfer_to:{recipient.id}",
            )
            inbound = record_ledger(
                user=recipient,
                kind="transfer_in",
                amount_cents=amount_cents,
                reference=f"transfer_from:{sender.id}",
            )
            outbound = WalletLedgerEntry.objects.filter(user=sender).latest("created_at")
            return outbound, inbound

        sender_credit = get_credit_account(sender)
        if sender_credit.credits < credits:
            raise ValueError("Insufficient credits.")
        record_ledger(
            user=sender,
            kind="transfer_out",
            credits_delta=-credits,
            reference=f"credit_transfer_to:{recipient.id}",
        )
        inbound = record_ledger(
            user=recipient,
            kind="transfer_in",
            credits_delta=credits,
            reference=f"credit_transfer_from:{sender.id}",
        )
        outbound = WalletLedgerEntry.objects.filter(user=sender).latest("created_at")
        return outbound, inbound


def upgrade_with_credits(user: User, tier: AccountTier) -> dict:
    required_credits = cents_to_credits(tier.price_cents)
    if required_credits <= 0:
        required_credits = 0

    with transaction.atomic():
        credit = get_credit_account(user)
        if credit.credits < required_credits:
            raise ValueError("Insufficient credits for upgrade.")
        record_ledger(
            user=user,
            kind="tier_upgrade",
            credits_delta=-required_credits,
            reference=f"tier:{tier.id}",
            meta={"tier": tier.name},
        )
        Subscription.objects.filter(user=user, status="active").update(status="superseded", ends_at=timezone.now())
        Subscription.objects.create(
            user=user,
            tier=tier,
            status="active",
            started_at=timezone.now(),
            ends_at=timezone.now() + timedelta(days=30),
            billing_meta={"source": "credits"},
        )
        user.tier = tier.name
        user.save(update_fields=["tier", "updated_at"])

    return {
        "tier": tier.name,
        "required_credits": required_credits,
    }


def adjust_points(user: User, points: int, reason: str) -> LoyaltyPoint:
    return LoyaltyPoint.objects.create(
        user=user,
        shop=None,
        points=points,
        earned_at=timezone.now(),
        expires_at=None,
        reason=reason,
    )
