# commerce/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from .models import (Shop, ShopVerificationRequest, Product, ProductAuthenticityCheck, Order, Payment, Promotion,
                     Subscription, LoyaltyPoint, ShopFollow, ProductShare, AIRecommendation, AuditLog, FraudSignal)
from .serializers import (ShopSerializer, ShopVerificationRequestSerializer, ProductSerializer, ProductAuthenticityCheckSerializer,
                          OrderSerializer, PaymentSerializer, PromotionSerializer, SubscriptionSerializer, LoyaltyPointSerializer,
                          ShopFollowSerializer, ProductShareSerializer, AIRecommendationSerializer, AuditLogSerializer, FraudSignalSerializer)
from .tasks import (enqueue_shop_verification, enqueue_product_auth_check, evaluate_fraud_score, compute_recommendations)

# --- OpenAPI / Swagger compatibility layer (supports drf-spectacular and drf-yasg) ---
try:
    # drf-spectacular
    from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter
    SPECTACULAR = True
except Exception:
    SPECTACULAR = False

try:
    # drf-yasg
    from drf_yasg.utils import swagger_auto_schema
    from drf_yasg import openapi
    YASG = True
except Exception:
    YASG = False


def doc_decorator(summary=None, description=None, request=None, responses=None, parameters=None):
    """
    Return a decorator that wraps either drf-spectacular or drf-yasg schema decorators,
    or a no-op decorator if neither is installed.
    """
    if SPECTACULAR:
        return extend_schema(summary=summary, description=description, request=request, responses=responses, parameters=parameters)
    if YASG:
        def _map_params(params):
            if not params:
                return None
            return params
        return swagger_auto_schema(operation_summary=summary, operation_description=description,
                                  request_body=request, responses=responses, manual_parameters=_map_params(parameters))
    def _noop(func):
        return func
    return _noop


def class_doc_decorator(tag_name: str):
    """
    Class-level decorator for tagging viewsets (drf-spectacular). No-op for drf-yasg.
    """
    if SPECTACULAR:
        return extend_schema_view(
            list=extend_schema(tags=[tag_name]),
            retrieve=extend_schema(tags=[tag_name]),
            create=extend_schema(tags=[tag_name]),
            update=extend_schema(tags=[tag_name]),
            partial_update=extend_schema(tags=[tag_name]),
            destroy=extend_schema(tags=[tag_name])
        )
    def _noop(cls):
        return cls
    return _noop


# --- ViewSets with OpenAPI annotations ---
@class_doc_decorator('Shops')
class ShopViewSet(viewsets.ModelViewSet):
    queryset = Shop.objects.all().order_by('-created_at')
    serializer_class = ShopSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @doc_decorator(
        summary="Request shop verification",
        description="Submit a verification request (KYC/business documents) for a shop. Enqueues an async verification job.",
        request=ShopVerificationRequestSerializer,
        responses={200: OpenApiResponse(description="Verification requested") if SPECTACULAR else "Verification requested"}
    )
    @action(detail=True, methods=['post'])
    def request_verification(self, request, pk=None):
        shop = self.get_object()
        data = request.data
        svr = ShopVerificationRequest.objects.create(shop=shop, requested_by=request.user, documents=data.get('documents', []))
        enqueue_shop_verification.delay(str(svr.id))
        return Response({'status': 'verification_requested', 'id': svr.id})


@class_doc_decorator('Shop Verification Requests')
class ShopVerificationRequestViewSet(viewsets.ModelViewSet):
    queryset = ShopVerificationRequest.objects.all().order_by('-created_at')
    serializer_class = ShopVerificationRequestSerializer

    @doc_decorator(
        summary="Review shop verification request",
        description="Approve or reject a shop verification request. This endpoint is intended for manual reviewers.",
        request=None,
        responses={200: OpenApiResponse(description="Reviewed") if SPECTACULAR else "Reviewed"}
    )
    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        req = self.get_object()
        action_name = request.data.get('action')
        notes = request.data.get('notes', '')
        if action_name == 'approve':
            req.status = 'APPROVED'
            req.shop.is_verified = True
            req.shop.trust_badges = list(set(req.shop.trust_badges + ['kyc']))
            req.shop.save()
        elif action_name == 'reject':
            req.status = 'REJECTED'
        req.reviewer_notes = notes
        req.processed_at = timezone.now()
        req.save()
        return Response({'status': 'reviewed', 'new_status': req.status})


@class_doc_decorator('Products')
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer

    @doc_decorator(
        summary="Request product authenticity check",
        description="Submit a product for AI/heuristic authenticity checks. Enqueues an async job.",
        request=ProductAuthenticityCheckSerializer,
        responses={200: OpenApiResponse(description="Auth check requested") if SPECTACULAR else "Auth check requested"}
    )
    @action(detail=True, methods=['post'])
    def check_authenticity(self, request, pk=None):
        product = self.get_object()
        pac = ProductAuthenticityCheck.objects.create(product=product, requested_by=request.user, provider=request.data.get('provider', 'local_ai'))
        enqueue_product_auth_check.delay(str(pac.id))
        return Response({'status': 'auth_check_requested', 'id': pac.id})


@class_doc_decorator('Product Authenticity Checks')
class ProductAuthenticityCheckViewSet(viewsets.ModelViewSet):
    queryset = ProductAuthenticityCheck.objects.all().order_by('-created_at')
    serializer_class = ProductAuthenticityCheckSerializer


@class_doc_decorator('Orders')
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by('-created_at')
    serializer_class = OrderSerializer

    @doc_decorator(
        summary="Pay for order",
        description="Create a payment for an order and mark it paid (free-tier stub). Triggers async fraud evaluation.",
        request=PaymentSerializer,
        responses={200: OpenApiResponse(description="Paid") if SPECTACULAR else "Paid"}
    )
    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        order = self.get_object()
        payment = Payment.objects.create(order=order, provider=request.data.get('provider', 'local'), method=request.data.get('method', 'card'), amount=order.total, currency=order.currency)
        # For free tier: mark success instantly (stub)
        payment.status = 'SUCCESS'
        payment.captured_at = timezone.now()
        payment.save()
        order.status = 'PAID'
        order.paid_at = timezone.now()
        order.save()
        # run fraud evaluation async
        evaluate_fraud_score.delay(str(order.id))
        return Response({'status': 'paid', 'payment_id': payment.id})


@class_doc_decorator('Payments')
class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all().order_by('-created_at')
    serializer_class = PaymentSerializer


@class_doc_decorator('Promotions')
class PromotionViewSet(viewsets.ModelViewSet):
    queryset = Promotion.objects.all().order_by('-created_at')
    serializer_class = PromotionSerializer


@class_doc_decorator('Subscriptions')
class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all().order_by('-created_at')
    serializer_class = SubscriptionSerializer


@class_doc_decorator('Loyalty')
class LoyaltyPointViewSet(viewsets.ModelViewSet):
    queryset = LoyaltyPoint.objects.all().order_by('-created_at')
    serializer_class = LoyaltyPointSerializer


@class_doc_decorator('Follows')
class ShopFollowViewSet(viewsets.ModelViewSet):
    queryset = ShopFollow.objects.all()
    serializer_class = ShopFollowSerializer


@class_doc_decorator('Shares')
class ProductShareViewSet(viewsets.ModelViewSet):
    queryset = ProductShare.objects.all()
    serializer_class = ProductShareSerializer


@class_doc_decorator('Recommendations')
class AIRecommendationViewSet(viewsets.ModelViewSet):
    queryset = AIRecommendation.objects.all()
    serializer_class = AIRecommendationSerializer

    @doc_decorator(
        summary="Compute recommendations",
        description="Enqueue recommendation computation for a user (async).",
        request=AIRecommendationSerializer,
        responses={200: OpenApiResponse(description="Enqueued") if SPECTACULAR else "Enqueued"}
    )
    @action(detail=False, methods=['post'])
    def compute(self, request):
        user_id = request.data.get('user_id')
        compute_recommendations.delay(user_id)
        return Response({'status': 'enqueued'})


@class_doc_decorator('Audit Logs')
class AuditLogViewSet(viewsets.ModelViewSet):
    queryset = AuditLog.objects.all().order_by('-created_at')
    serializer_class = AuditLogSerializer


@class_doc_decorator('Fraud Signals')
class FraudSignalViewSet(viewsets.ModelViewSet):
    queryset = FraudSignal.objects.all().order_by('-created_at')
    serializer_class = FraudSignalSerializer
