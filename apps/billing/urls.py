from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import WalletViewSet, WalletAdminViewSet, PromoCodeViewSet, FlutterwaveWebhookView

router = DefaultRouter()
router.register(r"wallet", WalletViewSet, basename="wallet")
router.register(r"wallet-admin", WalletAdminViewSet, basename="wallet-admin")
router.register(r"promo-codes", PromoCodeViewSet, basename="promo-codes")

urlpatterns = [
    path("", include(router.urls)),
    path("wallet/webhook/flutterwave/", FlutterwaveWebhookView.as_view(), name="wallet-flw-webhook"),
]
