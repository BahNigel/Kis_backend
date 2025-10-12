from django.apps import AppConfig


class SurveysConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.surveys'
    
    
    def ready(self):
        # import signals to connect them
        from . import signals  # noqa
