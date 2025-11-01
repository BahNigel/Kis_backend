from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Local DB: leave default sqlite unless DATABASE_URL provided.
DATABASE_URL = os.environ.get("DATABASE_URL", None)
if DATABASE_URL:
    # If you have dj-database-url available, parse here. For simplicity, we keep sqlite in example.
    pass

# In local, make email backend console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
