from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'shops', views.ShopViewSet)
router.register(r'shop-verifications', views.ShopVerificationRequestViewSet)
router.register(r'products', views.ProductViewSet)
router.register(r'product-auth-checks', views.ProductAuthenticityCheckViewSet)
router.register(r'orders', views.OrderViewSet)
router.register(r'payments', views.PaymentViewSet)
router.register(r'promotions', views.PromotionViewSet)
router.register(r'subscriptions', views.SubscriptionViewSet)
router.register(r'loyalty', views.LoyaltyPointViewSet)
router.register(r'follows', views.ShopFollowViewSet)
router.register(r'shares', views.ProductShareViewSet)
router.register(r'recommendations', views.AIRecommendationViewSet)
router.register(r'audit-logs', views.AuditLogViewSet)
router.register(r'fraud-signals', views.FraudSignalViewSet)

urlpatterns = router.urls
