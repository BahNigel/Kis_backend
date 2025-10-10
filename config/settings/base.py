"""
Base settings. Intended to be imported by local.py and production.py.
Contains production-safe defaults and advanced configuration patterns.
"""
import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent.parent
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
    "rest_framework.authtoken",
    "drf_spectacular",            # OpenAPI generation
    "django_extensions",          # useful utilities in dev
    "django_celery_beat",         # periodic tasks scheduler
    "django_celery_results",

    # Local apps
    "apps.accounts.apps.AccountsConfig",
    "apps.core.apps.CoreConfig",
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
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
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

# Authentication backends (Django-level). Add your token backend here so `authenticate()` can accept token param.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    # path to the TokenAuthBackend we placed in apps/accounts/auth_backends.py
    "apps.accounts.auth_backends.TokenAuthBackend",
]

# REST Framework + JWT settings
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Keep JWTAuthentication but prepend our ApiToken DRF authenticator
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # Custom DRF authenticator implemented in views (or move to a dedicated module)
        "apps.accounts.authentication.ApiTokenDRFAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 25,
}

# drf-spectacular settings
SPECTACULAR_SETTINGS = {
    "TITLE": "KIS Accounts & Identity API",
    "DESCRIPTION": "OpenAPI schema for KIS Accounts & Identity service",
    "VERSION": "1.0.0",
    # display bearer auth in the UI (JWT & bearer token)
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVE_INCLUDE_SCHEMA": False,
    "POSTPROCESSING_HOOKS": [],
    # Security schemes - both JWT and generic bearer token are acceptable in UI
    "SECURITY": [{"bearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                # swagger UI will show "Bearer" — both JWT and ApiToken will use this header
                "bearerFormat": "Token",
            }
        }
    },
}

# Simple JWT defaults (optional; you may use both JWT and ApiToken flows)
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.environ.get("JWT_ACCESS_MINUTES", 60))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", 7))),
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
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

# Celery settings (optional; configured in production)
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

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
