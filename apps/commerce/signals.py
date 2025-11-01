
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product, Shop, AIRecommendation
from .tasks import compute_recommendations


@receiver(post_save, sender=Product)
def on_product_save(sender, instance, created, **kwargs):
    # update AIRecommendation cache or enqueue recompute for followers
    if created:
        # naive: compute recommendations for users following shop (background)
        compute_recommendations.delay(str(instance.shop.owner.id))


@receiver(post_save, sender=Shop)
def on_shop_update(sender, instance, **kwargs):
    # update trust badges summary, etc.
    pass
