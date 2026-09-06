#!/bin/sh
set -e

# Both are safe to re-run on every start: collectstatic just overwrites
# same-named files (no cache-busted filenames here to go stale), and
# migrate is a no-op once the schema's up to date. Postgres/Redis being
# reachable is handled by compose's healthcheck-gated depends_on, not here.
python manage.py collectstatic --noinput
python manage.py migrate --noinput

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-30}" \
    --access-logfile - \
    --error-logfile -
