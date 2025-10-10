from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from . import models
from django.utils import timezone

# ---------------------------
# Update member counts automatically
# ---------------------------
@receiver(post_save, sender=models.Membership)
@receiver(post_delete, sender=models.Membership)
def update_group_member_count(sender, instance, **kwargs):
    if instance.group:
        instance.group.recalc_member_count()


# ---------------------------
# Automatically mark invites as used
# ---------------------------
@receiver(post_save, sender=models.Membership)
def mark_invite_used(sender, instance, created, **kwargs):
    if created and hasattr(instance, 'invite') and instance.invite:
        instance.invite.used_count += 1
        instance.invite.save()


# ---------------------------
# Default role assignment
# ---------------------------
@receiver(post_save, sender=models.Membership)
def assign_default_role(sender, instance, created, **kwargs):
    if created:
        default_role = models.Role.objects.filter(is_default=True, scope='GROUP').first()
        if default_role:
            models.RoleAssignment.objects.get_or_create(
                role=default_role,
                principal_type='USER',
                principal_id=instance.user_object_id,
                target_type='GROUP',
                target_id=instance.group.id
            )
