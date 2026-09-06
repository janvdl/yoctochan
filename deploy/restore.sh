#!/bin/sh
# Restores a backup made by backup.sh. DESTRUCTIVE: drops and recreates
# every table in the target database first. Run from this directory:
#   ./restore.sh backups/yoctochan-20260101-120000.sql.gz
set -eu

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup-file.sql.gz>" >&2
    exit 1
fi

cd "$(dirname "$0")"
dump="$1"

if [ ! -f "$dump" ]; then
    echo "No such file: $dump" >&2
    exit 1
fi

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

db="${POSTGRES_DB:-yoctochan}"
user="${POSTGRES_USER:-yoctochan}"

printf 'This will drop and replace every table in "%s". Continue? [y/N] ' "$db"
read -r confirm
case "$confirm" in
    y | Y | yes) ;;
    *)
        echo "Aborted."
        exit 1
        ;;
esac

gunzip -c "$dump" | $compose exec -T db psql -U "$user" -d "$db" -v ON_ERROR_STOP=1

echo "Restored from $dump."
