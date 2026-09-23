"""
Racheeta 2.0 — Django settings.

Single settings module driven entirely by environment variables (12-factor).
No secrets live in this file. Every variable is documented in `.env.example`.

Local development:  `.env` in the repository root is loaded automatically.
Production/Railway: variables are injected by the platform; no file is read.
"""

from datetime import timedelta
from pathlib import Path

import environ

# ---------------------------------------------------------------------------
# Paths & environment
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
REPO_DIR = BASE_DIR.parent  # racheeta-platform/

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
    DB_CONN_MAX_AGE=(int, 60),
    ACCESS_TOKEN_LIFETIME_MINUTES=(int, 15),
    REFRESH_TOKEN_LIFETIME_DAYS=(int, 14),
    ADMIN_URL_PATH=(str, "admin/"),
    SPA_DIST_DIR=(str, ""),
    LOG_LEVEL=(str, "INFO"),
    SECURE_PROXY_SSL=(bool, False),
    EMAIL_URL=(str, "consolemail://"),
    DEFAULT_FROM_EMAIL=(str, "Racheeta <no-reply@racheeta.local>"),
    FRONTEND_URL=(str, "http://localhost:5173"),
    PASSWORD_RESET_TIMEOUT_MINUTES=(int, 60),
    EMAIL_VERIFICATION_TIMEOUT_HOURS=(int, 24),
    FIREBASE_VERIFIER=(str, "apps.accounts.firebase.DisabledVerifier"),
    FIREBASE_CREDENTIALS_FILE=(str, ""),
)

# Load repo-root .env if present (developer machines only; harmless elsewhere).
_env_file = REPO_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY")  # Required. No default on purpose.
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# Railway health checks hit the service via its internal hostname. Allowing
# the platform-provided public domain keeps the checks working without a
# manual ALLOWED_HOSTS entry. Both are optional and empty locally.
for _var in ("RAILWAY_PUBLIC_DOMAIN", "RAILWAY_PRIVATE_DOMAIN"):
    _domain = env(_var, default="")
    if _domain and _domain not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_domain)

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    # Racheeta modules (modular monolith — see docs/ARCHITECTURE.md)
    "apps.core",
    "apps.accounts",
    "apps.geography",
    "apps.specialties",
    "apps.providers",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Localises validation messages per request (Accept-Language); default "ar".
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database — PostgreSQL only. DATABASE_URL is required.
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env.db_url("DATABASE_URL"),
}
DATABASES["default"]["CONN_MAX_AGE"] = env("DB_CONN_MAX_AGE")
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DATABASES["default"].setdefault("OPTIONS", {})

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.Account"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ("email", "full_name")},
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": (),
    "DEFAULT_THROTTLE_RATES": {
        "auth": "10/min",
        "password_reset": "5/min",
        "email_verification": "3/min",
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

if DEBUG:
    # Browsable API is convenient locally; JSON-only in production.
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    )

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("ACCESS_TOKEN_LIFETIME_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("REFRESH_TOKEN_LIFETIME_DAYS")),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "sub",
    "TOKEN_OBTAIN_SERIALIZER": "apps.accounts.serializers.LoginSerializer",
    "TOKEN_REFRESH_SERIALIZER": "apps.accounts.serializers.RefreshSerializer",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Racheeta API",
    "DESCRIPTION": "Racheeta 2.0 — canonical API consumed by web, mobile and dashboards.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": True,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "ENUM_NAME_OVERRIDES": {
        "AccountRoleEnum": "apps.accounts.roles.AccountRole.choices",
        "SelfRegistrationRoleEnum": "apps.accounts.roles.SELF_REGISTRATION_ROLE_CHOICES",
    },
}

# Django's stateless password-reset tokens (HMAC over user state + timestamp).
PASSWORD_RESET_TIMEOUT = env("PASSWORD_RESET_TIMEOUT_MINUTES") * 60

# ---------------------------------------------------------------------------
# Email — EMAIL_URL, e.g. consolemail:// (dev), smtp://user:pass@host:587?tls=True
# A production deployment must not use the console backend (see apps.core.checks).
# ---------------------------------------------------------------------------
vars().update(env.email_url("EMAIL_URL"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ---------------------------------------------------------------------------
# CORS / CSRF
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
CORS_ALLOW_CREDENTIALS = False  # Bearer tokens, not cookies, for the API.

# ---------------------------------------------------------------------------
# Security hardening (active whenever DEBUG is false)
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL = env("SECURE_PROXY_SSL")
if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "same-origin"
    if SECURE_PROXY_SSL:
        # Railway terminates TLS at its edge and forwards X-Forwarded-Proto.
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
        SECURE_SSL_REDIRECT = True
        SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days; raise after verifying HTTPS
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = False

# ---------------------------------------------------------------------------
# Internationalisation — Arabic-first, English-ready
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "ar"
LANGUAGES = [("ar", "Arabic"), ("en", "English")]
# API timestamps are rendered in UTC ("Z"); clients localise for display.
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files & SPA
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
# Media: local filesystem is a development placeholder only. Production must
# use S3-compatible object storage (see docs/ARCHITECTURE.md, Phase "media").
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# If the React build exists, WhiteNoise serves its assets from the URL root
# and apps.core.views.spa_index serves index.html for non-API routes.
SPA_DIST_DIR = Path(env("SPA_DIST_DIR")) if env("SPA_DIST_DIR") else None
if SPA_DIST_DIR and SPA_DIST_DIR.is_dir():
    WHITENOISE_ROOT = SPA_DIST_DIR
    WHITENOISE_INDEX_FILE = False
else:
    SPA_DIST_DIR = None

# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
ADMIN_URL_PATH = env("ADMIN_URL_PATH").strip("/") + "/"

# ---------------------------------------------------------------------------
# Logging — JSON-ish single-line records to stdout (Railway collects stdout).
# Never log tokens or passwords; see docs/SECURITY.md.
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL")},
    "loggers": {
        "django.request": {"level": "WARNING", "propagate": True},
        "django.security": {"level": "WARNING", "propagate": True},
    },
}

# ---------------------------------------------------------------------------
# Racheeta application settings
# ---------------------------------------------------------------------------
RACHEETA = {
    # Roles a client is allowed to choose at registration. ADMIN is never
    # client-assignable (see apps.accounts.roles).
    "SELF_REGISTRATION_ROLES": ("PATIENT", "PROVIDER", "MEDICAL_COMPANY", "REAL_ESTATE_SELLER"),
    # Public origin of the web app; used to build links in emails.
    "FRONTEND_URL": env("FRONTEND_URL").rstrip("/"),
    "EMAIL_VERIFICATION_TIMEOUT": timedelta(hours=env("EMAIL_VERIFICATION_TIMEOUT_HOURS")),
    # Dotted path to a FirebaseVerifier implementation (apps.accounts.firebase).
    "FIREBASE_VERIFIER": env("FIREBASE_VERIFIER"),
    "FIREBASE_CREDENTIALS_FILE": env("FIREBASE_CREDENTIALS_FILE"),
    # Currencies accepted for service prices (ISO 4217). IQD first.
    "CURRENCIES": ("IQD", "USD"),
}
