# app/views.py
import hmac, secrets, string, logging
from hashlib import sha256

from django.conf import settings
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

from .models import PhoneOTP

logger = logging.getLogger(__name__)
User = get_user_model()

OTP_LENGTH = 6
OTP_TTL_SECONDS = 5 * 60
RESEND_COOLDOWN_SECONDS = 60
MAX_ATTEMPTS = 5

ALLOWED_PURPOSES = {"register", "login"}
ALLOWED_CHANNELS = {"sms"}

def generate_otp(length: int = OTP_LENGTH) -> str:
    import string, secrets
    return ''.join(secrets.choice(string.digits) for _ in range(length))

def make_code_hash(phone: str, purpose: str, code: str) -> str:
    msg = f"{phone}|{purpose}|{code}".encode("utf-8")
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, msg, sha256).hexdigest()

def send_sms_via_provider(phone: str, body: str) -> None:
    try:
        logger.info("SMS queued to %s: %s", phone, body)
    except Exception as e:
        logger.warning("SMS send failed (dev non-fatal): %s", e)

@method_decorator(csrf_exempt, name="dispatch")
class OtpInitiateView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        phone = (request.data.get("phone") or "").strip()
        purpose = (request.data.get("purpose") or "register").strip()
        channel = (request.data.get("channel") or "sms").strip()
        if not phone:
            return Response({"success": False, "message": "phone required"}, status=400)
        if purpose not in ALLOWED_PURPOSES:
            return Response({"success": False, "message": "invalid purpose"}, status=400)
        if channel not in ALLOWED_CHANNELS:
            return Response({"success": False, "message": "invalid channel"}, status=400)

        now = timezone.now()
        last = (PhoneOTP.objects
                .filter(phone=phone, purpose=purpose)
                .order_by("-created_at").first())
        if last and (now - last.created_at).total_seconds() < RESEND_COOLDOWN_SECONDS:
            retry_after = RESEND_COOLDOWN_SECONDS - int((now - last.created_at).total_seconds())
            return Response(
                {"success": False, "message": "Please wait before requesting another code.", "retry_after": max(retry_after, 1)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        code = generate_otp(OTP_LENGTH)
        code_hash = make_code_hash(phone, purpose, code)
        expires_at = PhoneOTP.new_expiry(OTP_TTL_SECONDS)

        PhoneOTP.objects.filter(phone=phone, purpose=purpose, expires_at__gt=now).delete()
        PhoneOTP.objects.create(phone=phone, purpose=purpose, code_hash=code_hash, expires_at=expires_at, attempts=0)

        if settings.DEBUG:
            print(f"[DEV] OTP for {phone} ({purpose}): {code}")
            logger.warning("[DEV] OTP for %s (%s): %s", phone, purpose, code)

        try:
            send_sms_via_provider(phone, f"Your verification code is {code}. It expires in 5 minutes.")
        except Exception as e:
            logger.exception("Provider send failed: %s", e)

        return Response({"success": True, "expires_in": OTP_TTL_SECONDS, "cooldown": RESEND_COOLDOWN_SECONDS}, status=200)

@method_decorator(csrf_exempt, name="dispatch")
class OtpVerifyView(APIView):
    """
    POST /api/v1/auth/otp/verify/
    body: { phone, purpose='register', code }
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        phone = (request.data.get("phone") or "").strip()
        purpose = (request.data.get("purpose") or "register").strip()
        code = (request.data.get("code") or "").strip()

        if not phone or not code:
            return Response({"success": False, "message": "phone and code required"}, status=400)
        if purpose not in ALLOWED_PURPOSES:
            return Response({"success": False, "message": "invalid purpose"}, status=400)

        now = timezone.now()
        otp = (PhoneOTP.objects
               .filter(phone=phone, purpose=purpose)
               .order_by("-created_at").first())
        if not otp or otp.expires_at <= now:
            return Response({"success": False, "message": "code expired or not found"}, status=400)
        if otp.attempts >= MAX_ATTEMPTS:
            return Response({"success": False, "message": "too many attempts"}, status=429)

        expected_hash = make_code_hash(phone, purpose, code)
        if not hmac.compare_digest(expected_hash, otp.code_hash):
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            return Response({"success": False, "message": "invalid code"}, status=400)

        # ✅ Success: consume OTP and activate user
        otp.delete()

        user = User.objects.filter(phone=phone).first()
        if not user:
            return Response({"success": False, "message": "user not found"}, status=404)

        # mark verification/activation
        v = dict(user.verification or {})
        v["phone"] = {"verified": True, "verified_at": timezone.now().isoformat()}
        user.verification = v
        user.status = "active"
        user.is_active = True
        user.save(update_fields=["verification", "status", "is_active", "updated_at"])

        return Response(
            {
                "success": True,
                "user": {
                    "id": user.id,
                    "phone": user.phone,
                    "status": user.status,
                    "is_active": user.is_active,
                    "verification": user.verification,
                },
            },
            status=200,
        )