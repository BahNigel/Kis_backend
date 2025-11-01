# media/apps.py
from django.apps import AppConfig

class MediaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.media"
    verbose_name = "Media & Processing"

    def ready(self):
        # ensure signals are imported
        from . import signals  # noqa: F401
