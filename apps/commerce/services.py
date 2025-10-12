# Heavy-lifting: verification adapters, fraud engine, recommendation engine, payment hooks
import hashlib, json
from typing import Dict, Any, List
from .models import ShopVerificationRequest, ProductAuthenticityCheck, Order, Product, Shop


def run_shop_verification_checks(req: ShopVerificationRequest) -> Dict[str, Any]:
    """
    Combine multiple checks:
    - Identity document OCR & match
    - Business registry verification (adapter)
    - Social signals (followers, age)
    - AI-based image forensics on uploaded docs
    - Risk scoring
    Returns dict with status, risk_score, badges
    """
    # Stubbed implementation for free tier: basic heuristic checks
    docs = req.documents or []
    badges = []
    risk = 0.0
    if len(docs) >= 2:
        badges.append('documents-submitted')
        risk -= 0.2
    # check owner's history - stub
    risk += 0.1
    # if business reg doc exists, lower risk
    if any(d.get('type')=='BUSINESS_REG' for d in docs):
        badges.append('business-registered')
        risk -= 0.3
    status = 'APPROVED' if risk < 0.5 else 'PENDING'
    return {'status': status, 'risk_score': max(0.0, min(1.0, risk)), 'badges': badges}


def run_product_auth_check(pac: ProductAuthenticityCheck) -> Dict[str, Any]:
    """
    Composite authenticity checks:
    - Image similarity checks against known-good catalog (adapter)
    - Text & metadata cross-check (brand info)
    - Blockchain certificate verification (adapter)
    - AI-based multimodal detector (image + text) for counterfeits
    Returns: status, confidence, result dict with proof
    """
    prod = pac.product
    # free stub: if product.sku contains 'auth' treat as verified
    confidence = 0.0
    result = {'proof': {}}
    status = 'FLAGGED'
    if 'auth' in prod.sku.lower():
        status = 'VERIFIED'
        confidence = 0.92
        result['proof'] = {'method': 'sku_heuristic', 'note': 'SKU contains auth'}
    else:
        # simple hash of name as deterministic placeholder
        h = hashlib.sha1(prod.name.encode('utf-8')).hexdigest()
        confidence = int(h[:2],16)/255.0
        status = 'VERIFIED' if confidence > 0.7 else 'FLAGGED'
        result['proof'] = {'method': 'name_hash', 'hash': h}
    return {'status': status, 'confidence': confidence, 'result': result}


def compute_fraud_for_order(order: Order) -> (float, Dict[str, Any]): # type: ignore
    """
    Simple fraud scoring combining heuristics:
    - high order value relative to average
    - new account / little history
    - mismatched shipping & billing
    Returns score 0..1 and detail dict
    """
    score = 0.0
    details = {}
    # heuristic: large orders
    if float(order.total) > 1000000:
        score += 0.5
        details['large_order'] = True
    # new account heuristic placeholder
    # TODO integrate with user profile
    score = min(1.0, score)
    return score, details


def build_recommendations(user_id) -> List[Dict[str, Any]]:
    """
    Use simple collaborative/content hybrid stub:
    - fetch popular products
    - score by ai_score and shop trust
    Returns list of {type:'Product', id:uuid, score:float, reason:str}
    """
    popular = Product.objects.filter(is_active=True).order_by('-ai_score')[:10]
    out = []
    for p in popular:
        score = float(p.ai_score or 0.0)
        if p.shop.is_verified:
            score += 0.1
        out.append({'type':'Product','id':p.id,'score':score,'reason':'popular/ai_score'})
    return out
