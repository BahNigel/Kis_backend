# apps/accounts/authentication.py
from rest_framework import authentication
from django.utils.translation import gettext_lazy as _
from .models import ApiToken

class ApiTokenDRFAuthentication(authentication.BaseAuthentication):
    """
    Authenticate requests using Authorization: Bearer <token>.
    Returns (user, api_token_instance) on success.
    """
    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).decode("utf-8")
        if not auth_header:
            return None
        parts = auth_header.split()
        if len(parts) != 2:
            return None
        kw, token = parts
        if kw != self.keyword:
            return None

        ip_addr = request.META.get("REMOTE_ADDR")
        api_token = ApiToken.verify_plain_token(token, ip_address=ip_addr)
        if not api_token:
            return None

        user = getattr(api_token, "user", None)
        if not user or not user.is_active or getattr(user, "is_deleted", False):
            return None

        # attach token to request for convenience
        request._api_token = api_token
        return (user, api_token)

    def authenticate_header(self, request):
        return f'{self.keyword} realm="api"'
