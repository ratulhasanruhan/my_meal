"""Django settings for the My Meal tracker."""

import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

# `os.environ.get(key, default)` returns "" when the variable exists but is
# empty, and Django then dies with a bare "SECRET_KEY must not be empty".
# Treat empty as unset, and say so plainly rather than shipping a known key.
SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if DEBUG or "collectstatic" in sys.argv:
        SECRET_KEY = "django-insecure-dev-key-change-me"
    else:
        raise ImproperlyConfigured(
            "SECRET_KEY is empty. Set it to a long random string. If you pasted "
            "it as a .env block, note that '#' starts a comment — use a key made "
            "only of letters and digits."
        )

ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"]
if os.environ.get("SITE_URL"):
    CSRF_TRUSTED_ORIGINS.append(os.environ["SITE_URL"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "meals",
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
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "meals.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Supabase Postgres in production; SQLite locally when no URL is configured.
# POSTGRES_URL is what Vercel's Supabase integration injects, so accept it as a
# fallback — but DATABASE_URL wins, since it is the one we document.
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=0,
            ssl_require=True,
        )
    }
    # Without a timeout, an unreachable host (Supabase's direct endpoint is
    # IPv6-only) leaves the connection hanging until the platform kills the
    # function — which logs no traceback at all. Fail fast and say why instead.
    DATABASES["default"].setdefault("OPTIONS", {}).setdefault("connect_timeout", 8)
    # Belongs on the database, not at module level — Supabase's transaction
    # pooler cannot hold a server-side cursor open across statements.
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
elif "collectstatic" in sys.argv:
    # The Vercel build step collects static files without a database.
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
else:
    # Falling back to SQLite in production would "work" until the first write,
    # then fail with a read-only-database error on a serverless filesystem.
    # Fail here instead, where the cause is obvious.
    raise ImproperlyConfigured(
        "No database configured. Set DATABASE_URL to the Supabase transaction "
        "pooler URL (port 6543) — note that Vercel's Supabase integration adds "
        "POSTGRES_* and SUPABASE_* variables but not DATABASE_URL. "
        "Or set DEBUG=True to use local SQLite."
    )

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "Asia/Dhaka")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Vercel publishes `staticfiles_build/` as static assets, so collectstatic
# writes into its `static/` subdirectory to line up with STATIC_URL.
STATIC_ROOT = BASE_DIR / "staticfiles_build" / "static"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # No manifest: on Vercel the static build and the lambda are separate
    # filesystems, so the lambda cannot read a staticfiles.json manifest.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# Currency symbol shown across the UI.
CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL", "৳")

# Vercel terminates TLS in front of the app, so trust its forwarded scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
