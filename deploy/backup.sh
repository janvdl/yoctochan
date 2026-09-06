#!/bin/sh
# Dumps the database to backups/yoctochan-<timestamp>.sql.gz. Run from this
# directory: ./backup.sh
#
# Media isn't included here — back it up separately, it's just files, e.g.:
#   podman/docker run --rm -v deploy_media_volume:/from:ro -v "$PWD/backups":/to \
#       alpine tar czf /to/media-$(date +%Y%m%d).tar.gz -C /from .
# (volume name may differ — check with `podman/docker volume ls`.)
set -eu

cd "$(dirname "$0")"
mkdir -p backups

if docker compose version >/dev/null 2>&1; then
    compose="docker compose --env-file ../.env"
elif command -v podman-compose >/dev/null 2>&1; then
    compose="podman-compose --env-file ../.env"
else
    echo "Neither 'docker compose' nor 'podman-compose' found." >&2
    exit 1
fi

# shellcheck disable=SC1091
[ -f ../.env ] && . ../.env

out="backups/yoctochan-$(date +%Y%m%d-%H%M%S).sql.gz"

# --clean --if-exists: the dump drops each object before recreating it, so
# restore.sh can restore straight into a database that already has the old
# (or a partial/corrupt) schema in it, not just a freshly-created empty one.
$compose exec -T db pg_dump --clean --if-exists \
        -U "${POSTGRES_USER:-yoctochan}" "${POSTGRES_DB:-yoctochan}" \
    | gzip > "$out"

echo "Wrote $out ($(du -h "$out" | cut -f1))"
