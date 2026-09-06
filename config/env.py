"""
Small, dependency-free helpers for reading configuration from the
environment (and, in development, from a local ``.env`` file).

Nothing here is Django-specific; it exists so ``config/settings/base.py``
doesn't need a third-party package just to read a boolean or a list out of
the environment.
"""

import os


def load_dotenv(path):
    """
    Populate ``os.environ`` from a simple ``KEY=VALUE`` file, one setting per
    line (blank lines and ``#`` comments are skipped). Real environment
    variables always win: this only fills in keys that aren't already set,
    so ``FOO=bar python manage.py ...`` overrides whatever ``.env`` says.

    Missing file is not an error — ``.env`` is a local-dev convenience and
    is gitignored; production deployments set real environment variables.
    """
    if not path.exists():
        return

    for line in path.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]

        os.environ.setdefault(key, value)


def env_str(name, default=""):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in ("1", "true", "yes", "on")


def env_int(name, default):
    value = os.environ.get(name)

    return int(value) if value not in (None, "") else default


def env_list(name, default=()):
    """Comma-separated list, e.g. ``DJANGO_ALLOWED_HOSTS=example.com,www.example.com``."""
    value = os.environ.get(name)

    if value is None:
        return list(default)

    return [item.strip() for item in value.split(",") if item.strip()]
