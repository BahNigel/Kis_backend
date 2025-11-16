# accounts/auth_backends.py
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from django.utils import timezone
from typing import Optional
from apps.core.phone_utils import to_e164, normalize_local_digits
from .models import User  # adjust import to your app

class PhoneOrEmailBackend(ModelBackend):
    """
    Auth with phone (E.164 or national with default region), email, or username.
    Prefers phone if provided; falls back to email/username.
    """

    def authenticate(self, request, username: Optional[str] = None, password: Optional[str] = None, **kwargs):
        ident = kwargs.get("phone") or username or kwargs.get("email")
        if not ident or not password:
            return None

        candidates = []

        # If request provided, let client send preferred region (JSON or header)
        default_region = "CM"
        if request is not None:
            default_region = (
                (getattr(getattr(request, "data", {}), "get", lambda *_: None)("country") or  # DRF Request
                 (request.data.get("country") if hasattr(request, "data") else None) or
                 request.headers.get("X-Country") or
                 default_region)
            )

        # Build candidate identifiers
        try:
            # Try E.164 for whatever came in
            e164 = to_e164(str(ident), default_region=default_region)
            candidates.append(e164)
        except Exception:
            # If not a (valid) phone, try raw forms for email/username/phone-as-stored
            pass

        # Also try a normalized local-digit form (in case DB stored local form)
        digits = normalize_local_digits(str(ident))
        if digits:
            candidates.append(digits)

        # Also try the literal ident (for email/username or already-E.164)
        candidates.append(str(ident).strip())

        # Deduplicate while preserving order
        seen, unique = set(), []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        # Lookup: phone exact match against any candidate, or email/username case-insensitive
        q = Q()
        for c in unique:
            q |= Q(phone=c)
        q |= Q(email__iexact=ident) | Q(username__iexact=ident)

        user = User.objects.filter(q, is_active=True).first()
        if user is None:
            return None

        if not user.check_password(password):
            return None

        # update last_login_at similar to auth.login behavior
        try:
            user.last_login_at = timezone.now()
            user.save(update_fields=["last_login_at"])
        except Exception:
            pass

        return user
