"""
Production settings. Select with ``DJANGO_SETTINGS_MODULE=config.settings.prod``.

This doesn't hardcode a "production configuration" — everything still comes
from the environment via base.py. What it adds is fail-safe validation: if
the environment isn't actually set up for production (debug left on, no
real secret key, no allowed hosts), refuse to start rather than quietly
serving an insecure site.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS, DATABASE_ENGINE, DATABASES, DEBUG, SECRET_KEY

if DEBUG:
    raise ImproperlyConfigured(
        "config.settings.prod requires DJANGO_DEBUG=false in the environment."
    )

if SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured(
        "config.settings.prod requires DJANGO_SECRET_KEY to be set to a "
        "real, unique secret (the fallback dev key is still active)."
    )

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "config.settings.prod requires DJANGO_ALLOWED_HOSTS "
        "(comma-separated) to be set."
    )

if DATABASE_ENGINE == "postgresql" and not DATABASES["default"]["PASSWORD"]:
    raise ImproperlyConfigured(
        "config.settings.prod requires POSTGRES_PASSWORD to be set when "
        "DATABASE_ENGINE=postgresql."
    )
