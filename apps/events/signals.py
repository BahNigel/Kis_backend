
from django.dispatch import receiver
from django.db.models.signals import post_save
from . import models


@receiver(post_save, sender=models.TicketSale)
def on_ticket_sale(sender, instance, created, **kwargs):
    if created and instance.status == "completed":
        # link to waitlist, send receipts, allocate seats, call downstream billing systems.
        # We purposely keep this function small and call services asynchronously (celery)
        from .services import enqueue_post_purchase_tasks

        enqueue_post_purchase_tasks(instance.id)