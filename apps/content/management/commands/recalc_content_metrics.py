# content/management/commands/recalc_content_metrics.py
from django.core.management.base import BaseCommand
from content.models import Content

class Command(BaseCommand):
    help = "Recompute content metrics for all contents"

    def handle(self, *args, **options):
        total = 0
        for content in Content.objects.all():
            content.recalc_metrics()
            total += 1
        self.stdout.write(self.style.SUCCESS(f"Recomputed metrics for {total} contents."))
