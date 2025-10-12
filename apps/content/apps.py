# content/apps.py
from django.apps import AppConfig

class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content"
    verbose_name = "Content (Engagement & Analytics)"

    def ready(self):
        # import signals to ensure they are registered
        from . import signals  # noqa
