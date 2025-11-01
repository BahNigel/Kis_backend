"""
Middleware: Request logging and Quota enforcement.
Quota enforcement is simplified: checks UsageQuota in DB and optionally cache.
This is an example pattern; in production you'd offload heavy checks to a permission/service layer.
"""
import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from apps.accounts.models import UsageQuota, AuditLog

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._start_time = time.time()
        logger.debug(f"REQ START {request.method} {request.get_full_path()}")

    def process_response(self, request, response):
        duration = (time.time() - getattr(request, "_start_time", time.time())) * 1000.0
        logger.debug(f"REQ END {request.method} {request.get_full_path()} {response.status_code} {duration:.2f}ms")
        return response

class QuotaEnforcementMiddleware(MiddlewareMixin):
    """
    Example middleware that enforces per-day ai_queries_per_day quota on POST /api/v1/ai/*
    Real implementation: use decorator or permission class for clearer scope.
    """
    def process_view(self, request, view_func, view_args, view_kwargs):
        # only run for authenticated users and for endpoints that are considered quota-checked
        if not request.user or not getattr(request, "user", None) or not request.user.is_authenticated:
            return None

        path = request.path
        # crude path matching
        if request.method in ("POST", "PUT") and "/api/v1/ai/" in path:
            try:
                quota = UsageQuota.objects.filter(user=request.user).order_by("-created_at").first()
                if not quota:
                    # no quota record - create default and allow
                    UsageQuota.objects.create(user=request.user, quotas_json={"ai_queries_per_day": 10})
                    return None
                # reset daily quotas if last_reset_at is older than midnight
                # (keep it simple)
                if quota.quotas_json.get("ai_queries_per_day", 0) <= 0:
                    AuditLog.log(actor=request.user, action="quota.exhausted", meta={"path": path})
                    from django.http import JsonResponse
                    return JsonResponse({"detail": "AI daily quota exceeded", "status_code": 429}, status=429)
            except Exception as exc:
                logger.exception("Quota enforcement failure - allowing through by default.")
                return None
        return None
