"""Settings used by pytest only. Keep differences from production minimal."""

import os

from django.core.management.utils import get_random_secret_key

# Tests never need a real secret; generate one per run if none is provided.
os.environ.setdefault("SECRET_KEY", get_random_secret_key())
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("ALLOWED_HOSTS", "testserver,localhost")

from config.settings import *  # noqa: E402, F403

# Fast hashing keeps the account tests quick; production uses PBKDF2/Argon2.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# Throttling is tested explicitly by patching the rate; keep it out of the
# way for every other test (the cache is also cleared per test in conftest).
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"auth": "10000/min"}}  # noqa: F405
# No collectstatic in tests: serve admin/DRF assets straight from app finders.
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
STATIC_ROOT = None
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
