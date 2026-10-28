"""
Delight Care Plus — settings.

Everything secret or environment-specific is read from environment variables
(or a local `.env` file — see `.env.example`).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file():
    """Tiny .env loader so no extra package is needed."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    return env(key, str(default)).lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", "dev-only-change-me-in-production")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in env("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Delight Care Plus apps
    "core",
    "catalog",
    "cart",
    "orders",
    "accounts",
    "chat",
    "blog",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 days — keeps carts & wishlists

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Delight Care Plus <no-reply@delightcareplus.com>")
ADMIN_EMAILS = [e.strip() for e in env("ADMIN_EMAILS", "").split(",") if e.strip()]

# ---------------------------------------------------------------------------
# Shop
# ---------------------------------------------------------------------------
SITE_NAME = "Delight Care Plus"
SITE_URL = env("SITE_URL", "http://127.0.0.1:8000")
CURRENCY = "KES"
# Delivery is priced by zone + pickup/home + parcel weight (see Delivery Zones in admin).
# Optional promo: free delivery when the order is at least this much. 0 = switched off.
WHATSAPP_NUMBER = env("WHATSAPP_NUMBER", "254795180079")
SUPPORT_PHONE = env("SUPPORT_PHONE", "+254 795 180 079")
SUPPORT_EMAIL = env("SUPPORT_EMAIL", "support@delightcareplus.com")
INSTAGRAM_URL = env("INSTAGRAM_URL", "https://www.instagram.com/")
TIKTOK_URL = env("TIKTOK_URL", "")
FACEBOOK_URL = env("FACEBOOK_URL", "")

# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
MPESA_ENVIRONMENT = env("MPESA_ENVIRONMENT", "production")  # production | sandbox
MPESA_BASE_URL = env(
    "MPESA_BASE_URL",
    "https://api.safaricom.co.ke" if MPESA_ENVIRONMENT == "production" else "https://sandbox.safaricom.co.ke",
)
MPESA_CONSUMER_KEY = env("MPESA_CONSUMER_KEY", "")
MPESA_CONSUMER_SECRET = env("MPESA_CONSUMER_SECRET", "")
MPESA_SHORTCODE = env("MPESA_SHORTCODE", "4701129")  # Delight Care Plus PayBill
MPESA_PASSKEY = env("MPESA_PASSKEY", "")
MPESA_PARTY_B = env("MPESA_PARTY_B", MPESA_SHORTCODE)
MPESA_TRANSACTION_TYPE = env("MPESA_TRANSACTION_TYPE", "CustomerPayBillOnline")
MPESA_CALLBACK_URL = env("MPESA_CALLBACK_URL", f"{SITE_URL}/orders/mpesa/callback/")
# Any long random string. Safaricom calls back with it, so forged "payment received" calls are ignored.
MPESA_CALLBACK_TOKEN = env("MPESA_CALLBACK_TOKEN", "")

AIRTEL_MONEY_NUMBER = env("AIRTEL_MONEY_NUMBER", "")  # shown to customers paying by Airtel Money

# ---------------------------------------------------------------------------
# Production security (active when DEBUG=False)
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "orders": {"handlers": ["console"], "level": "INFO"},
        "core": {"handlers": ["console"], "level": "INFO"},
    },
}
