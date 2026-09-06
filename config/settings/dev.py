"""
Development settings. This is the default (see manage.py/wsgi.py/asgi.py) —
running the project locally with no environment configured at all lands
here, with DEBUG on, the insecure fallback SECRET_KEY, and SQLite.
Everything is still overridable via environment variables / a local
``.env`` file (see base.py and ``.env.example``).
"""

from .base import *  # noqa: F401,F403
