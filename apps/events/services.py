
from django.conf import settings
from . import models


def enqueue_post_purchase_tasks(ticket_sale_id):
    # In production this would push to Celery/RQ. Here we call a synchronous placeholder.
    try:
        sale = models.TicketSale.objects.get(id=ticket_sale_id)
        # 1) Send receipt via email (external accounts app handles user email)
        # 2) Mint NFT (if configured)
        if sale.ticket.nft_token_id is None and sale.ticket.type != "free":
            # call blockchain service (placeholder)
            sale.ticket.nft_token_id = f"nft-{sale.id.hex[:12]}"
            sale.ticket.blockchain_tx_hash = "tx-placeholder"
            sale.ticket.save()
    except models.TicketSale.DoesNotExist:
        return
