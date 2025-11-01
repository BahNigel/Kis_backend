import hashlib
import hmac
from django.conf import settings


def sign_payload(payload: str) -> str:
    secret = getattr(settings, "EVENTS_WEBHOOK_SECRET", "please-set-this")
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()