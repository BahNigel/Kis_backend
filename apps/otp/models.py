# app/models.py
from django.db import models
from django.utils import timezone
from datetime import timedelta

class PhoneOTP(models.Model):
    PURPOSE_CHOICES = (("register", "register"), ("login", "login"))
    phone = models.CharField(max_length=20, db_index=True)
    purpose = models.CharField(max_length=16, choices=PURPOSE_CHOICES)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def new_expiry(cls, ttl_seconds: int):
        return timezone.now() + timedelta(seconds=ttl_seconds)
