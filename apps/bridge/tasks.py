from celery import shared_task
from .models import BridgeMessage, BridgeThread, BridgeAccount, BridgeAnalytics
from django.utils import timezone
import time

@shared_task
def enqueue_outbound_message(message_id):
    msg = BridgeMessage.objects.get(id=message_id)
    # find account & adapter
    # adapter = get_adapter_for_app(msg.bridge_thread.external_app)
    # adapter.send(msg)
    msg.status = 'SENT'
    msg.sent_at = timezone.now()
    msg.save()

@shared_task
def process_inbound_message(payload):
    # payload: dict from webhook
    # create thread/message, enrich, route
    data = payload
    # create or update thread and message records
    return True

@shared_task
def sync_bridge_account(account_id):
    account = BridgeAccount.objects.get(id=account_id)
    # call external APIs to sync conversation history
    account.last_sync_at = timezone.now()
    account.save()

@shared_task
def compute_bridge_analytics(account_id):
    account = BridgeAccount.objects.get(id=account_id)
    total = BridgeMessage.objects.filter(bridge_thread__bridgeaccount=account).count()
    analytics, _ = BridgeAnalytics.objects.get_or_create(bridge_account=account)
    analytics.total_messages = total
    analytics.save()