"""
Signals to automatically create Profile + UsageQuota for new Users,
and lightweight audit hooks for important models.
"""

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from typing import Tuple

from .models import (
    User,
    Profile,
    UsageQuota,
    AccountTier,
    ApiToken,
    Subscription,
    AuditLog,
)

AUDIT_MODELS = (User, Profile, ApiToken, Subscription, AccountTier)

@receiver(post_save, sender=User)
def create_profile_and_quota(sender, instance: User, created: bool, **kwargs):
    """
    On user creation:
      - ensure Profile exists (idempotent)
      - ensure a default UsageQuota exists
      - attempt to set default tier if AccountTier 'Basic' exists
    """
    if not created:
        return

    with transaction.atomic():
        # Profile
        if not hasattr(instance, "profile"):
            Profile.objects.create(user=instance)

        # UsageQuota
        if not UsageQuota.objects.filter(user=instance).exists():
            UsageQuota.objects.create(
                user=instance,
                quotas_json={"ai_queries_per_day": 10},
                last_reset_at=timezone.now(),
            )

        # Default tier assignment (if exists)
        try:
            basic = AccountTier.objects.filter(name__iexact="Basic").first()
            if basic and instance.tier != basic.name:
                instance.tier = basic.name
                instance.save(update_fields=["tier", "updated_at"])
        except Exception:
            # Do not fail user creation if tiers unavailable
            pass

# ---------------------------------------------------------------------
# Audit log hooks (keep small; consider offloading to async worker)
# ---------------------------------------------------------------------
@receiver(post_save)
def _audit_post_save(sender, instance, created, **kwargs):
    """
    Generic post_save audit hook for configured models.
    Creates AuditLog entries like: 'user.create' or 'profile.update'.
    """
    if sender not in AUDIT_MODELS:
        return
    try:
        actor = getattr(instance, "user", None) or getattr(instance, "actor", None) or None
        action = "create" if created else "update"
        AuditLog.log(actor, f"{sender.__name__.lower()}.{action}", {"id": str(instance.id)})
    except Exception:
        # Never raise from signal
        pass

@receiver(pre_delete)
def _audit_pre_delete(sender, instance, **kwargs):
    """
    Generic pre_delete audit hook for configured models.
    """
    if sender not in AUDIT_MODELS:
        return
    try:
        actor = getattr(instance, "user", None) or getattr(instance, "actor", None) or None
        AuditLog.log(actor, f"{sender.__name__.lower()}.delete", {"id": str(instance.id)})
    except Exception:
        pass

# ---------------------------------------------------------------------
# Profile post-save: recompute completion score (prevent recursion)
# ---------------------------------------------------------------------
@receiver(post_save, sender=Profile)
def _profile_post_save(sender, instance: Profile, **kwargs):
    if getattr(instance, "_updating_completion", False):
        return  # prevent recursion

    try:
        instance._updating_completion = True
        instance.update_completion()
    finally:
        instance._updating_completion = False
