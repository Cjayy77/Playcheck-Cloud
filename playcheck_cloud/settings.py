"""Playcheck Cloud settings.

Postgres in production via DATABASE_URL; SQLite fallback for local dev so the
app runs on a machine without a Postgres server. One service, one database.
"""
import os
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "dev-only-insecure-key-change-in-production"
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
INTERNAL_IPS = ["127.0.0.1"]  # lets templates show dev-only hints via {{ debug }}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.github",
    "orgs",
    "projects",
    "previews",
    "billing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "playcheck_cloud.urls"

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
                "projects.context_processors.sidebar_projects",
            ],
        },
    },
]

WSGI_APPLICATION = "playcheck_cloud.wsgi.application"


def _database_from_env():
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith(("postgres://", "postgresql://")):
        parsed = urlparse(url)
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username or "",
            "PASSWORD": parsed.password or "",
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
        }
    return {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}


DATABASES = {"default": _database_from_env()}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
if not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }

# --- production hardening ---------------------------------------------------
if not DEBUG:
    if SECRET_KEY == "dev-only-insecure-key-change-in-production":
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY when DJANGO_DEBUG=0")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

# Ingest rate limit (uploads per project per minute); locmem cache is enough
# for a single-process deployment — revisit only if we ever scale out.
INGEST_UPLOADS_PER_MINUTE = int(os.environ.get("INGEST_UPLOADS_PER_MINUTE", "30"))

# --- billing: Creem.io (merchant of record) --------------------------------
# Use https://test-api.creem.io while testing with sandbox keys.
CREEM_API_BASE = os.environ.get("CREEM_API_BASE", "https://api.creem.io")
CREEM_API_KEY = os.environ.get("CREEM_API_KEY", "")
CREEM_WEBHOOK_SECRET = os.environ.get("CREEM_WEBHOOK_SECRET", "")
CREEM_PRODUCT_ID_TEAM = os.environ.get("CREEM_PRODUCT_ID_TEAM", "")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- auth: GitHub OAuth via allauth ---------------------------------------
SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/accounts/login/"
ACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_PROVIDERS = {
    "github": {
        "SCOPE": ["read:user", "user:email"],
        "APP": {
            # Real credentials come from the environment in production. The
            # placeholders keep the login page renderable in local dev.
            "client_id": os.environ.get("GITHUB_CLIENT_ID", "dev-placeholder"),
            "secret": os.environ.get("GITHUB_CLIENT_SECRET", "dev-placeholder"),
        },
    }
}
