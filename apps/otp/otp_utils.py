# app/otp_utils.py
import os, hmac, hashlib, random
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

def generate_otp(length: int = 6) -> str:
    digits = "0123456789"
    return "".join(random.SystemRandom().choice(digits) for _ in range(length))

def code_hash(phone: str, code: str) -> str:
    # phone as salt to prevent rainbow reuse; add project-wide secret
    secret = getattr(settings, "OTP_HASH_SECRET", "dev-secret-change-me")
    return hmac.new(
        key=(str(phone) + secret).encode(),
        msg=str(code).encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

def expires_in(seconds: int = 5 * 60):
    return timezone.now() + timedelta(seconds=seconds)

def send_sms_infobip(phone: str, text: str) -> None:
    """
    Replace this with your actual Infobip/Twilio client call.
    In dev we still call the provider, but we also print to console.
    """
    print(f"[DEV OTP] Sending to {phone}: {text}")  # <-- visible in console
    # real_sms_client.send(phone, text)  # implement for your provider
