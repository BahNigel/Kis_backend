import json
import logging
import urllib.request

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _post_to_nest(path: str, payload: dict) -> None:
    base = getattr(settings, "NEST_INTERNAL_URL", "").rstrip("/")
    token = getattr(settings, "NEST_INTERNAL_TOKEN", "")
    if not base or not token:
        logger.warning("[chat.tasks] Missing NEST_INTERNAL_URL or NEST_INTERNAL_TOKEN; skipping notify")
        return

    url = f"{base}/{path.lstrip('/')}"
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Auth": token,
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=3) as resp:
        resp.read()


def notify_nest_conversation_created(conversation_id: str, user_ids: list[str]) -> None:
    payload = {
        "conversationId": str(conversation_id),
        "userIds": [str(uid) for uid in user_ids],
    }
    _post_to_nest("conversations/created", payload)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def notify_nest_conversation_created_task(self, conversation_id: str, user_ids: list[str]) -> None:
    try:
        notify_nest_conversation_created(conversation_id, user_ids)
    except Exception as exc:
        raise self.retry(exc=exc)
