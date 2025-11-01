
import hashlib
import hmac
from django.conf import settings
from django.utils import timezone
import datetime


def sign_webhook(payload: str) -> str:
    secret = getattr(settings, "NOTIFICATIONS_WEBHOOK_SECRET", "please-set-this")
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def is_within_quiet_hours(schedule_json, now=None):
    now = now or timezone.now()
    q = schedule_json.get("quiet_hours") if schedule_json else None
    if not q:
        return False
    start = q.get("start")
    end = q.get("end")
    if not start or not end:
        return False
    start_t = datetime.time.fromisoformat(start)
    end_t = datetime.time.fromisoformat(end)
    now_t = now.time()
    if start_t <= end_t:
        return start_t <= now_t <= end_t
    else:
        # spans midnight
        return now_t >= start_t or now_t <= end_t


# rate limiting helpers
from django.core.cache import cache


def is_rate_limited(user_id, key="notification", limit=5, window_seconds=60):
    cache_key = f"rate:{key}:{user_id}"
    current = cache.get(cache_key) or 0
    if current >= limit:
        return True
    cache.incr(cache_key, 1)
    cache.expire(cache_key, window_seconds)
    return False
