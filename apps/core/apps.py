from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'  # optional but recommended in Django 3.2+
    name = 'apps.core' 
    
    def ready(self):
        import apps.core.signals  # noqa
