"""
Authentication backends for the project.
TokenAuthBackend authenticates by plain API token (Authorization: Bearer <token>)
by delegating to ApiToken.verify_plain_token().
"""

from django.contrib.auth.backends import BaseBackend
from typing import Optional
from .models import ApiToken, User

class TokenAuthBackend(BaseBackend):
    """
    Allows authenticate(request, token=PLAIN_TOKEN) -> User.
    Register in settings.AUTHENTICATION_BACKENDS when you want Django-level auth support.
    """
    def authenticate(self, request, token: Optional[str] = None, **kwargs) -> Optional[User]:
        if not token:
            return None
        ip = None
        if request is not None:
            ip = request.META.get("REMOTE_ADDR")
        api_token = ApiToken.verify_plain_token(token, ip_address=ip)
        if not api_token:
            return None
        user = getattr(api_token, "user", None)
        if user and user.is_active and not user.is_deleted:
            return user
        return None

    def get_user(self, user_id: str) -> Optional[User]:
        try:
            return User.objects.get(pk=user_id, is_deleted=False)
        except User.DoesNotExist:
            return None
