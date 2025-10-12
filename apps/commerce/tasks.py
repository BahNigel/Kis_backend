
from celery import shared_task
from django.utils import timezone
from .models import ShopVerificationRequest, ProductAuthenticityCheck, Order, FraudSignal, AIRecommendation, Product, Shop
from .services import (run_shop_verification_checks, run_product_auth_check, compute_fraud_for_order, build_recommendations)


@shared_task(bind=True, max_retries=2)
def enqueue_shop_verification(self, request_id):
    req = ShopVerificationRequest.objects.get(id=request_id)
    req.status = 'IN_REVIEW'
    req.save()
    try:
        result = run_shop_verification_checks(req)
        req.status = result.get('status','APPROVED')
        req.risk_score = result.get('risk_score', 0.0)
        req.processed_at = timezone.now()
        req.save()
        if req.status == 'APPROVED':
            shop = req.shop
            shop.is_verified = True
            tb = list(set(shop.trust_badges + result.get('badges',[])))
            shop.trust_badges = tb
            shop.save()
        return result
    except Exception as exc:
        req.status = 'ERROR'
        req.save()
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=2)
def enqueue_product_auth_check(self, check_id):
    pac = ProductAuthenticityCheck.objects.get(id=check_id)
    pac.status = 'PROCESSING'
    pac.save()
    try:
        result = run_product_auth_check(pac)
        pac.status = result.get('status','VERIFIED')
        pac.result = result.get('result', {})
        pac.confidence = result.get('confidence', 0.0)
        pac.checked_at = timezone.now()
        pac.save()
        # update product
        prod = pac.product
        prod.authenticity_status = pac.status
        prod.authenticity_proof = pac.result.get('proof', {})
        prod.save()
        return result
    except Exception as exc:
        pac.status = 'ERROR'
        pac.save()
        raise self.retry(exc=exc, countdown=10)


@shared_task
def evaluate_fraud_score(order_id):
    order = Order.objects.get(id=order_id)
    score, details = compute_fraud_for_order(order)
    fs = FraudSignal.objects.create(source='fraud_engine', entity_type='order', entity_id=order.id, score=score, details=details)
    # take action thresholds
    if score > 0.8:
        order.status = 'PENDING'
        order.save()
    return {'score': score}


@shared_task
def compute_recommendations(user_id):
    recs = build_recommendations(user_id)
    created = []
    for r in recs:
        ai = AIRecommendation.objects.create(user_id=user_id, target_type=r['type'], target_id=r['id'], score=r['score'], reason=r.get('reason',''))
        created.append(str(ai.id))
    return created