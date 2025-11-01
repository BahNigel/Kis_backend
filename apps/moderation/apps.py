from django.apps import AppConfig


class ModerationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.moderation'
    label = 'Moderation'
    verbose_name = "Moderation (KIS)"
