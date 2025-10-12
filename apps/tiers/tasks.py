from celery import shared_task
from .models import Subscription, BillingInvoice
from django.utils import timezone

@shared_task
def reconcile_subscription(subscription_id):
    # Integrate with Stripe/Billing provider to refresh subscription state
    # For demo: mark as active
    sub = Subscription.objects.get(id=subscription_id)
    sub.status = 'active'
    sub.save()

@shared_task
def generate_invoice(payload):
    # payload could be dict containing subscription ids
    # For demo: create a fake invoice per subscription id list
    subs = payload.get('subscription_ids', []) if isinstance(payload, dict) else []
    for sid in subs:
        try:
            sub = Subscription.objects.get(id=sid)
            inv = BillingInvoice.objects.create(subscription=sub, amount=0, currency='USD', issued_at=timezone.now(), status='unpaid')
        except Exception:
            continue
    return True