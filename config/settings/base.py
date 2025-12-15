"""
Base settings. Intended to be imported by local.py and production.py.
Contains production-safe defaults and advanced configuration patterns.
"""
import os
from pathlib import Path
from datetime import timedelta

# NEW: load .env early so all os.environ lookups work everywhere
try:
    from dotenv import load_dotenv  # pip install python-dotenv
except ImportError:  # optional safety if not installed yet
    def load_dotenv(*args, **kwargs):
        return False

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")  # reads .env at project root

ENV = os.environ.get("DJANGO_ENV", "local")

# SECRET_KEY should be overridden via environment in production
SECRET_KEY = os.environ.get("SECRET_KEY", "replace-me-for-dev-only")
DEBUG = os.environ.get("DEBUG", "False").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Application definition
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    # "rest_framework.authtoken",  # optional: remove if no longer using opaque tokens
    "drf_spectacular",
    "django_extensions",
    "django_celery_beat",
    "django_celery_results",
    "django_filters",  # NEW: needed for DjangoFilterBackend

    # Local apps
    "apps.accounts.apps.AccountsConfig",
    "apps.core.apps.CoreConfig",
    "apps.content.apps.ContentConfig",
    "apps.media.apps.MediaConfig",
    "apps.events.apps.EventsConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.moderation.apps.ModerationConfig",
    "apps.ai_integration.apps.AIIntegrationConfig",
    "apps.commerce.apps.CommerceConfig",
    "apps.surveys.apps.SurveysConfig",
    "apps.bridge.apps.BridgeConfig",
    "apps.analytics.apps.AnalyticsConfig",
    "apps.tiers.apps.TiersConfig",
    "apps.otp.apps.OtpConfig",
    "apps.background_removal.apps.BackgroundRemovalConfig",

    # chats
    "apps.chat.apps.ChatConfig",
    "apps.partners.apps.PartnersConfig",
    "apps.communities.apps.CommunitiesConfig",
    "apps.groups.apps.GroupsConfig",
    "apps.channels.apps.ChannelsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # Common middleware
    "common.middleware.RequestLoggingMiddleware",
    "common.middleware.QuotaEnforcementMiddleware",  # custom quota enforcement
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database default is sqlite (override in local/production)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "UTC")
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static and media
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom user
AUTH_USER_MODEL = "accounts.User"

# Authentication backends (Django-level).
AUTHENTICATION_BACKENDS = [
    "apps.accounts.auth_backends.PhoneOrEmailBackend",  # our custom backend
    "django.contrib.auth.backends.ModelBackend",   # keep as fallback
]

# REST Framework + JWT settings
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        # Keep SessionAuthentication for browsable API if you like:
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
}

# drf-spectacular settings
SPECTACULAR_SETTINGS = {
    "TITLE": "KIS Accounts & Identity API",
    "DESCRIPTION": "OpenAPI schema for KIS Accounts & Identity service",
    "VERSION": "1.0.0",
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVE_INCLUDE_SCHEMA": False,
    "POSTPROCESSING_HOOKS": [],
    "SECURITY": [{"bearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}

# Simple JWT — read signing/validation config from environment
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.environ.get("JWT_ACCESS_MINUTES", 60))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", 7))),
    "ALGORITHM": "HS256",

    # Use your JWT secret from the environment (fallback to SECRET_KEY for dev)
    "SIGNING_KEY": os.environ.get("JWT_SECRET", SECRET_KEY),

    # Optional but recommended for strict validation
    # Set these in .env to have them embedded in tokens and enforced by verifiers
    "ISSUER": os.environ.get("JWT_ISSUER", None),          # e.g., "http://localhost:8000"
    "AUDIENCE": os.environ.get("JWT_AUDIENCE", None),      # e.g., "messaging-platform"

    "AUTH_HEADER_TYPES": ("Bearer",),
    "UPDATE_LAST_LOGIN": True,
}

# Token / entitlement configuration (override these in environment-specific settings if desired)
ENTITLEMENTS_CACHE_TTL = int(os.environ.get("ENTITLEMENTS_CACHE_TTL", 300))  # seconds
API_TOKEN_PLAIN_LENGTH = int(os.environ.get("API_TOKEN_PLAIN_LENGTH", 32))  # used by secrets.token_urlsafe(n)
API_TOKEN_DEFAULT_EXPIRES_DAYS = int(os.environ.get("API_TOKEN_DEFAULT_EXPIRES_DAYS", 30))

# Caching (e.g., Redis) — used by quota enforcement and feature flags
CACHES = {
    "default": {
        # For local/dev the locmem cache is fine; override in production to Redis/Memcached
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# Celery settings
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# NEW: media-service URL for background removal microservice
# This is what your Celery task uses to call the external service.
MEDIA_SERVICE_URL = os.environ.get(
    "MEDIA_SERVICE_URL",
    "http://localhost:9000/process/background-removal",
)

# Logging - keep it verbose for dev, JSON-friendly for prod
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(levelname)s %(asctime)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "DEBUG")},
}
