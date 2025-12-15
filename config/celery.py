# config/celery.py
import os
from celery import Celery

# Use your environment-specific settings module (local/production gets selected by manage.py)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("kis")

# Read CELERY_* settings from Django
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in all INSTALLED_APPS
app.autodiscover_tasks()
