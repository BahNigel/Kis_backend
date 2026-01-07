import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import AuthenticationFailed
from apps.accounts.jwt_auth import DeviceBoundJWTAuthentication

from .internal_auth import require_internal_auth


class IntrospectView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        require_internal_auth(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header:
            raise AuthenticationFailed("Missing token")

        scheme = os.environ.get("DJANGO_AUTH_SCHEME", "Bearer").strip()
        prefix = f"{scheme} "
        if not auth_header.startswith(prefix):
            raise AuthenticationFailed("Invalid auth scheme")

        token = auth_header[len(prefix):].strip()
        if not token:
            raise AuthenticationFailed("Missing token")

        jwt_auth = DeviceBoundJWTAuthentication()
        validated = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated)
        if not user or not user.is_active:
            raise AuthenticationFailed("Invalid token")
        if not validated.get("device_id"):
            raise AuthenticationFailed("Device-bound token required")

        username = getattr(user, "username", "") or ""
        email = getattr(user, "email", "") or ""
        display_name = ""
        if hasattr(user, "get_full_name"):
            display_name = user.get_full_name() or ""
        if not display_name:
            display_name = username or (email.split("@")[0] if email else "")

        tier = ""
        if hasattr(user, "tier"):
            tier = getattr(user, "tier") or ""
        elif hasattr(user, "profile") and getattr(user, "profile", None):
            tier = getattr(user.profile, "tier", "") or ""

        is_premium = bool(tier and tier.lower() != "basic")

        return Response({
            "id": str(user.id),
            "username": username,
            "email": email,
            "display_name": display_name,
            "tier": tier,
            "isPremium": is_premium,
            "device_id": validated.get("device_id"),
            "entitlements": {},
            "scopes": [],
        })
