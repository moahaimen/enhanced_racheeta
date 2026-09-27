"""Settings used by pytest only. Keep differences from production minimal."""

import os
import secrets

# Tests never need a real secret; generate one per run if none is provided.
# (token_urlsafe never starts with "$", which django-environ would treat as a reference.)
os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(50))
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("ALLOWED_HOSTS", "testserver,localhost")
# Not used to send anything: pytest swaps in the locmem backend at runtime. It
# only keeps the production email check (racheeta.E001) satisfied under DEBUG=false.
os.environ.setdefault("EMAIL_URL", "smtp://localhost:25")
os.environ.setdefault("FRONTEND_URL", "https://app.test")

from config.settings import *  # noqa: E402, F403

# Fast hashing keeps the account tests quick; production uses PBKDF2/Argon2.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# Throttling is tested explicitly by patching the rate; keep it out of the
# way for every other test (the cache is also cleared per test in conftest).
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        "auth": "10000/min",
        "password_reset": "10000/min",
        "email_verification": "10000/min",
        "jobs_create": "10000/min",
        "jobs_apply": "10000/min",
        "talent_search": "10000/min",
        "talent_invite": "10000/min",
        "recruitment_messages": "10000/min",
    },
}
# No collectstatic in tests: serve admin/DRF assets straight from app finders.
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
STATIC_ROOT = None
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
