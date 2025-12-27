import os
from rest_framework.exceptions import AuthenticationFailed


def require_internal_auth(request) -> None:
    expected = os.environ.get("DJANGO_INTERNAL_TOKEN", "")
    got = request.headers.get("X-Internal-Auth", "")

    if not expected or got != expected:
        raise AuthenticationFailed("Invalid internal auth")
