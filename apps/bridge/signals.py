from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import BridgeMessage
from .tasks import process_inbound_message

@receiver(post_save, sender=BridgeMessage)
def on_message_saved(sender, instance, created, **kwargs):
    if created and instance.direction == 'INBOUND':
        # schedule enrichment, moderation, routing
        process_inbound_message.delay({'message_id': str(instance.id)})