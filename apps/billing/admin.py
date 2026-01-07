from django.contrib import admin

from .models import WalletAccount, CreditAccount, WalletLedgerEntry, WalletTransaction, PromoCode, PromoRedemption


@admin.register(WalletAccount)
class WalletAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "balance_cents", "currency", "status", "updated_at")
    search_fields = ("user__email", "user__phone", "user__display_name")
    list_filter = ("currency", "status")


@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "credits", "locked_credits", "updated_at")
    search_fields = ("user__email", "user__phone", "user__display_name")


@admin.register(WalletLedgerEntry)
class WalletLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "amount_cents", "credits_delta", "created_at")
    search_fields = ("user__email", "user__phone", "reference")
    list_filter = ("kind", "status")


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "amount_cents", "currency", "status", "created_at")
    search_fields = ("user__email", "tx_ref", "provider_ref")
    list_filter = ("provider", "status")


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "cash_bonus_cents", "credit_bonus", "is_active", "used_count")
    search_fields = ("code",)
    list_filter = ("is_active",)


@admin.register(PromoRedemption)
class PromoRedemptionAdmin(admin.ModelAdmin):
    list_display = ("promo", "user", "redeemed_at")
    search_fields = ("promo__code", "user__email")
