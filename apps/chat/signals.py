from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Conversation, ConversationMember
from .tasks import notify_nest_conversation_created, notify_nest_conversation_created_task


@receiver(post_save, sender=Conversation)
def conversation_created_notify(sender, instance: Conversation, created: bool, **kwargs) -> None:
    if not created:
        return

    def _enqueue() -> None:
        user_ids = list(
            ConversationMember.objects.filter(
                conversation=instance,
                left_at__isnull=True,
            ).values_list("user_id", flat=True)
        )
        if not user_ids:
            return

        try:
            notify_nest_conversation_created_task.delay(str(instance.id), user_ids)
        except Exception:
            notify_nest_conversation_created(str(instance.id), user_ids)

    transaction.on_commit(_enqueue)
