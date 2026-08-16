"""Django settings for the My Meal tracker."""

import os
import sys
import zoneinfo
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(name, default=""):
    """Read an environment variable, treating empty or blank as unset.

    `os.environ.get(name, default)` only falls back when the variable is
    absent. A dashboard that stores a key with no value hands back "", which
    then reaches Django as a real setting — an empty SECRET_KEY, or a
    TIME_ZONE that ZoneInfo rejects. Both took this deployment down with no
    usable traceback, so every variable is read through here instead.
    """
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


# True only for an explicit "true"; anything else, including blank, is False.
DEBUG = env("DEBUG", "False").lower() == "true"

BUILDING = "collectstatic" in sys.argv

SECRET_KEY = env("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG or BUILDING:
        SECRET_KEY = "django-insecure-dev-key-change-me"
    else:
        raise ImproperlyConfigured(
            "SECRET_KEY is empty. Set it to a long random string. If you pasted "
            "it as a .env block, note that '#' starts a comment — use a key made "
            "only of letters and digits."
        )

ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"]
SITE_URL = env("SITE_URL")
if SITE_URL:
    # Django rejects a trusted origin without a scheme, and it rejects it while
    # handling a POST, so a bare hostname here breaks only form submissions.
    if "://" not in SITE_URL:
        SITE_URL = f"https://{SITE_URL}"
    CSRF_TRUSTED_ORIGINS.append(SITE_URL.rstrip("/"))

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
DATABASE_URL = env("DATABASE_URL") or env("POSTGRES_URL")
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

# Every view starts with timezone.localdate(), so an unusable TIME_ZONE breaks
# the whole site — and it breaks the debug page too, which formats dates, so
# the error recurses until the process dies with nothing logged. Validate it
# here and fall back rather than let that happen; TIME_ZONE_ERROR surfaces the
# bad value on /healthz/.
DEFAULT_TIME_ZONE = "Asia/Dhaka"
TIME_ZONE = env("TIME_ZONE", DEFAULT_TIME_ZONE)
TIME_ZONE_ERROR = ""
try:
    zoneinfo.ZoneInfo(TIME_ZONE)
except Exception as exc:
    TIME_ZONE_ERROR = f"{TIME_ZONE!r} is not a valid IANA time zone ({exc}); using {DEFAULT_TIME_ZONE}"
    TIME_ZONE = DEFAULT_TIME_ZONE

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
CURRENCY_SYMBOL = env("CURRENCY_SYMBOL", "৳")

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
