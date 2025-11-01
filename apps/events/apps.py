from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.events'
    verbose_name = 'Events (KIS)'
    
    def ready(self):
        # import signals to ensure they are registered
        from . import signals  # noqa
