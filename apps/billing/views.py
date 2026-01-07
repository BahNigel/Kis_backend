from __future__ import annotations

import uuid
import json
from datetime import timedelta
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User, AccountTier
from .models import WalletAccount, CreditAccount, WalletLedgerEntry, WalletTransaction, PromoCode, PromoRedemption
from .serializers import (
    WalletAccountSerializer,
    CreditAccountSerializer,
    WalletLedgerEntrySerializer,
    WalletTransactionSerializer,
    PromoCodeSerializer,
)
from .services import (
    get_wallet_account,
    get_credit_account,
    record_ledger,
    convert_cash_to_credits,
    convert_credits_to_cash,
    transfer_balance,
    upgrade_with_credits,
    cents_to_credits,
    credits_to_cents,
    adjust_points,
)

FLW_BASE_URL = "https://api.flutterwave.com/v3"


def _flutterwave_headers() -> dict:
    secret = settings.FLW_SECRET_KEY
    return {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
    }


def _flutterwave_payment_link(payload: dict) -> dict:
    url = f"{FLW_BASE_URL}/payments"
    response = requests.post(url, json=payload, headers=_flutterwave_headers(), timeout=30)
    data = response.json() if response.content else {}
    if response.status_code >= 300:
        raise ValueError(data.get("message") or "Failed to create payment")
    return data


def _ensure_payments_ready() -> None:
    if not getattr(settings, "FLW_SECRET_KEY", None):
        raise ValueError("FLW_SECRET_KEY is not configured")


class WalletViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        wallet = get_wallet_account(request.user)
        credits = get_credit_account(request.user)
        features = [
            "instant_topup",
            "credits_conversion",
            "cash_conversion",
            "gifts_transfer",
            "promo_redemption",
            "auto_convert_rules",
            "spend_limits",
            "safety_lock",
            "tier_discounts",
            "receipt_history",
            "referral_rewards",
            "scheduled_topups",
        ]
        payload = {
            "wallet": WalletAccountSerializer(wallet).data,
            "credits": CreditAccountSerializer(credits).data,
            "credits_value_cents": credits_to_cents(credits.credits),
            "features": features,
        }
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="ledger")
    def ledger(self, request):
        entries = WalletLedgerEntry.objects.filter(user=request.user).order_by("-created_at")[:200]
        return Response({"results": WalletLedgerEntrySerializer(entries, many=True).data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="transactions")
    def transactions(self, request):
        entries = WalletTransaction.objects.filter(user=request.user).order_by("-created_at")[:100]
        return Response({"results": WalletTransactionSerializer(entries, many=True).data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="deposit")
    def deposit(self, request):
        amount = int(request.data.get("amount_cents", 0))
        amount_usd = request.data.get("amount_usd")
        provider = request.data.get("provider", "flutterwave")
        method = request.data.get("method")
        payment_meta: dict[str, Any] = {}
        mock = bool(request.data.get("mock")) or getattr(settings, "PAYMENTS_MOCK", False)

        if amount_usd is not None:
            try:
                amount = int(float(amount_usd) * 100)
            except (ValueError, TypeError):
                return Response({"detail": "Invalid amount_usd"}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({"detail": "Amount must be greater than 0"}, status=status.HTTP_400_BAD_REQUEST)

        tx_ref = f"kis_{uuid.uuid4().hex}"
        if not method:
            if provider == "mobilemoney_mtn":
                method = "mobilemoney"
                payment_meta["network"] = "MTN"
            elif provider == "mobilemoney_orange":
                method = "mobilemoney"
                payment_meta["network"] = "ORANGE"
            else:
                method = "card"

        transaction_obj = WalletTransaction.objects.create(
            user=request.user,
            provider=provider,
            method=method,
            amount_cents=amount,
            currency="USD",
            status="pending",
            tx_ref=tx_ref,
            meta={"intent": "wallet_topup", **payment_meta},
        )

        if mock:
            record_ledger(
                user=request.user,
                kind="deposit",
                amount_cents=amount,
                reference=tx_ref,
                meta={"provider": "mock"},
            )
            transaction_obj.status = "success"
            transaction_obj.processed_at = timezone.now()
            transaction_obj.save(update_fields=["status", "processed_at", "updated_at"])
            return Response(
                {
                    "tx_ref": tx_ref,
                    "status": "success",
                    "payment_url": None,
                },
                status=status.HTTP_200_OK,
            )

        try:
            _ensure_payments_ready()
            payload = {
                "tx_ref": tx_ref,
                "amount": amount / 100,
                "currency": "USD",
                "redirect_url": getattr(settings, "FLW_REDIRECT_URL", "https://kis.app/payments/complete"),
                "customer": {
                    "email": request.user.email or "user@kis.app",
                    "phonenumber": request.user.phone or "",
                    "name": request.user.display_name or "KIS User",
                },
                "customizations": {
                    "title": "KIS Wallet Top Up",
                    "description": "Add funds to your KIS wallet",
                },
            }
            if method:
                payload["payment_options"] = method
            if payment_meta:
                payload["meta"] = payment_meta

            response = _flutterwave_payment_link(payload)
            payment_url = response.get("data", {}).get("link")
            transaction_obj.payment_url = payment_url or ""
            transaction_obj.raw_payload = response
            transaction_obj.save(update_fields=["payment_url", "raw_payload", "updated_at"])
            return Response(
                {
                    "tx_ref": tx_ref,
                    "status": "pending",
                    "payment_url": payment_url,
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as exc:
            transaction_obj.status = "failed"
            transaction_obj.raw_payload = {"error": str(exc)}
            transaction_obj.save(update_fields=["status", "raw_payload", "updated_at"])
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="convert")
    def convert(self, request):
        direction = request.data.get("direction")
        try:
            if direction == "cash_to_credits":
                amount_cents = int(request.data.get("amount_cents", 0))
                if amount_cents == 0 and request.data.get("amount_usd"):
                    amount_cents = int(float(request.data.get("amount_usd")) * 100)
                result = convert_cash_to_credits(request.user, amount_cents)
                return Response(
                    {
                        "direction": direction,
                        "amount_cents": result.amount_cents,
                        "credits": result.credits,
                    },
                    status=status.HTTP_200_OK,
                )
            if direction == "credits_to_cash":
                credits = int(request.data.get("credits", 0))
                result = convert_credits_to_cash(request.user, credits)
                return Response(
                    {
                        "direction": direction,
                        "amount_cents": result.amount_cents,
                        "credits": result.credits,
                    },
                    status=status.HTTP_200_OK,
                )
            return Response({"detail": "Invalid direction"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="transfer")
    def transfer(self, request):
        recipient_id = request.data.get("recipient_id")
        amount_cents = int(request.data.get("amount_cents", 0))
        amount_usd = request.data.get("amount_usd")
        credits = int(request.data.get("credits", 0))

        if not recipient_id:
            return Response({"detail": "recipient_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        if amount_usd is not None and amount_cents == 0:
            try:
                amount_cents = int(float(amount_usd) * 100)
            except (ValueError, TypeError):
                return Response({"detail": "Invalid amount_usd"}, status=status.HTTP_400_BAD_REQUEST)

        recipient = get_object_or_404(User, id=recipient_id)
        try:
            outbound, inbound = transfer_balance(
                sender=request.user,
                recipient=recipient,
                amount_cents=amount_cents,
                credits=credits,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "outbound": WalletLedgerEntrySerializer(outbound).data,
                "inbound": WalletLedgerEntrySerializer(inbound).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="upgrade")
    def upgrade(self, request):
        tier_id = request.data.get("tier")
        tier = get_object_or_404(AccountTier, id=tier_id)
        try:
            result = upgrade_with_credits(request.user, tier)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="redeem")
    def redeem(self, request):
        code = (request.data.get("code") or "").strip().upper()
        if not code:
            return Response({"detail": "Promo code required"}, status=status.HTTP_400_BAD_REQUEST)
        promo = get_object_or_404(PromoCode, code=code, is_active=True)
        if promo.ends_at and promo.ends_at < timezone.now():
            return Response({"detail": "Promo expired"}, status=status.HTTP_400_BAD_REQUEST)
        if promo.usage_limit and promo.used_count >= promo.usage_limit:
            return Response({"detail": "Promo fully redeemed"}, status=status.HTTP_400_BAD_REQUEST)

        if PromoRedemption.objects.filter(user=request.user, promo=promo).exists():
            return Response({"detail": "Promo already redeemed"}, status=status.HTTP_400_BAD_REQUEST)

        record_ledger(
            user=request.user,
            kind="promo",
            amount_cents=promo.cash_bonus_cents,
            credits_delta=promo.credit_bonus,
            reference=f"promo:{promo.code}",
            meta={"promo": promo.code},
        )
        promo.used_count += 1
        promo.save(update_fields=["used_count", "updated_at"])
        PromoRedemption.objects.create(user=request.user, promo=promo)
        return Response({"code": promo.code, "cash_bonus_cents": promo.cash_bonus_cents, "credit_bonus": promo.credit_bonus})


@method_decorator(csrf_exempt, name="dispatch")
class FlutterwaveWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        secret = getattr(settings, "FLW_WEBHOOK_SECRET", "")
        signature = request.headers.get("verif-hash")
        if secret and signature != secret:
            return Response({"detail": "invalid signature"}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data if isinstance(request.data, dict) else {}
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        tx_ref = data.get("tx_ref")
        status_flag = (data.get("status") or "").lower()

        if not tx_ref:
            return Response({"detail": "tx_ref missing"}, status=status.HTTP_400_BAD_REQUEST)

        transaction_obj = WalletTransaction.objects.filter(tx_ref=tx_ref).first()
        if not transaction_obj:
            return Response({"detail": "unknown transaction"}, status=status.HTTP_404_NOT_FOUND)

        transaction_obj.raw_payload = payload
        if status_flag == "successful" and transaction_obj.status != "success":
            transaction_obj.status = "success"
            transaction_obj.provider_ref = data.get("id", "")
            transaction_obj.processed_at = timezone.now()
            transaction_obj.save(update_fields=["status", "provider_ref", "processed_at", "raw_payload", "updated_at"])
            record_ledger(
                user=transaction_obj.user,
                kind="deposit",
                amount_cents=transaction_obj.amount_cents,
                reference=transaction_obj.tx_ref,
                meta={"provider": "flutterwave"},
            )
        elif status_flag in ("failed", "cancelled"):
            transaction_obj.status = "failed" if status_flag == "failed" else "cancelled"
            transaction_obj.save(update_fields=["status", "raw_payload", "updated_at"])
        return Response({"status": "ok"})


class WalletAdminViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=["post"], url_path="adjust")
    def adjust(self, request):
        user_id = request.data.get("user_id")
        cash_cents = int(request.data.get("cash_cents", 0))
        credits = int(request.data.get("credits", 0))
        points = int(request.data.get("points", 0))
        reason = request.data.get("reason", "admin_adjust")

        if not user_id:
            return Response({"detail": "user_id required"}, status=status.HTTP_400_BAD_REQUEST)
        user = get_object_or_404(User, id=user_id)

        if cash_cents or credits:
            record_ledger(
                user=user,
                kind="admin_adjust",
                amount_cents=cash_cents,
                credits_delta=credits,
                reference=f"admin:{request.user.id}",
                meta={"reason": reason},
            )
        if points:
            adjust_points(user, points, reason)
        return Response({"detail": "adjusted"}, status=status.HTTP_200_OK)


class PromoCodeViewSet(viewsets.ModelViewSet):
    queryset = PromoCode.objects.all()
    serializer_class = PromoCodeSerializer
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=["get"], url_path="public")
    def public(self, request):
        active = PromoCode.objects.filter(is_active=True).order_by("-created_at")[:50]
        return Response({"results": PromoCodeSerializer(active, many=True).data}, status=status.HTTP_200_OK)
