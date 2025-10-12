# media/management/commands/recompute_media_metrics.py
from django.core.management.base import BaseCommand
from media.models import MediaAsset, MediaMetrics

class Command(BaseCommand):
    help = "Recompute media metrics for all assets (placeholder)"

    def handle(self, *args, **options):
        total = 0
        for asset in MediaAsset.objects.all():
            metrics, _ = MediaMetrics.objects.get_or_create(asset=asset)
            # Very naive recompute - reset (in prod you'd aggregate events)
            metrics.views = 0
            metrics.stream_minutes = 0
            metrics.downloads = 0
            metrics.carbon_grams = 0.0
            metrics.save()
            total += 1
        self.stdout.write(self.style.SUCCESS(f"Reset metrics for {total} assets."))
