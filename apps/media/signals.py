# media/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ProcessingJob, MediaAsset, MediaVariant, MediaMetrics

@receiver(post_save, sender=ProcessingJob)
def on_job_finished(sender, instance, **kwargs):
    # If a processing job completes with useful result_meta, we might create variants or update labels.
    if instance.status == "done":
        result = instance.result_meta or {}
        # Example: if phash was computed, save to labels
        phash = result.get("phash")
        if phash:
            asset = instance.asset
            labels = asset.labels or {}
            labels.setdefault("phash", phash)
            asset.labels = labels
            asset.save(update_fields=["labels", "updated_at"])
        # Create variant when pipeline returns a derived URL
        derived = result.get("derived_variant")
        if derived:
            MediaVariant.objects.create(
                asset=instance.asset,
                purpose=derived.get("purpose", "generated"),
                codec=derived.get("codec", ""),
                dims=derived.get("dims", ""),
                bytes=derived.get("bytes", 0),
                url=derived.get("url"),
                variant_meta=derived.get("variant_meta", {})
            )
