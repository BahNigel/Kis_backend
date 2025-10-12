from django.apps import AppConfig


class CommerceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.commerce'
    verbose_name = 'Commerce & Shops'
    
    def ready(self):
        # import signals to ensure they are registered
        from . import signals  # noqa