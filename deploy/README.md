# Deploying yoctochan

A self-contained container stack for running yoctochan on a box you
control (a VPS, a home server, ...): the Django app behind gunicorn,
PostgreSQL, Redis (cache), and Caddy as a reverse proxy handling TLS and
serving static/media files directly. Works with either `docker compose` or
`podman-compose`.

## First-time setup

```sh
cp ../.env.example ../.env
# edit ../.env — at minimum set DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS,
# and POSTGRES_PASSWORD. See ../.env.example's comments for everything else.

docker compose up -d --build
# or: podman-compose --env-file ../.env up -d --build
```

`config.settings.prod` (which the compose file selects) refuses to start
at all if `.env` is missing something it needs — that's deliberate, not a
bug, and the error names exactly what's missing.

Then open `https://<DOMAIN or localhost>/`, create a superuser, and add a
board:

```sh
docker compose exec app python manage.py createsuperuser
```

Boards are still only created through `/admin/` — there's no public
board-creation UI (see the main README).

### About that first HTTPS certificate

`DOMAIN` defaults to `localhost` (see `../.env.example`), for which Caddy
issues a locally-trusted certificate from its own internal CA — no DNS or
public reachability needed, useful for a first look or a pure-LAN
deployment. Once you have a real domain's DNS pointed at this host with
ports 80/443 reachable from the internet, set `DOMAIN` in `.env` to it and
restart the `caddy` service — Caddy then automatically obtains and renews
a real Let's Encrypt certificate instead. Update `DJANGO_ALLOWED_HOSTS` to
match either way.

## What's in the stack

| Service | Role |
| --- | --- |
| `app` | Django via gunicorn. Runs `collectstatic` and `migrate` on every start (see `entrypoint.sh`) — safe to re-run, both are no-ops once up to date. |
| `db` | PostgreSQL. Data in the `postgres_data` volume. |
| `redis` | Cache backend (`CACHES`, via `REDIS_URL`). No volume — losing it on restart just means the next few requests repopulate it. |
| `caddy` | Reverse proxy: TLS termination, and serves `/static/*` and `/media/*` directly from shared volumes (never touches gunicorn for those). |

`docker compose logs -f app` (or `podman-compose ...`) for the application
log — everything goes to stdout, collected by the container runtime's own
log driver rather than a file inside the container (see
`config/settings/base.py`'s `LOGGING`).

## Health and monitoring

`/healthz/` checks real database connectivity (not just that the process
is running) and backs the `app` service's healthcheck in
`docker-compose.yml`; check status with `docker compose ps` /
`podman ps`, or point an external uptime check at it. There's nothing
beyond that here (no Prometheus/Grafana or similar) — this is a
spare-time project's deployment, not a fleet's; add one if this ever
needs it.

## Backups

```sh
./backup.sh                              # writes backups/yoctochan-<timestamp>.sql.gz
./restore.sh backups/yoctochan-....sql.gz  # DESTRUCTIVE — confirms before running
```

`backup.sh` dumps the database with `pg_dump --clean --if-exists`, so the
resulting file can be restored straight into a database that already has
the old (or a partial/corrupt) schema in it, not just an empty one.
**This restore procedure has actually been run** — verified end to end by
destroying the `postgres_data` volume entirely and confirming
`restore.sh` brought every row back — this isn't just a script that looks
right.

Media isn't included in `backup.sh` (it's files, not database rows) —
back up the `media_volume` volume separately, e.g.:

```sh
docker run --rm -v deploy_media_volume:/from:ro -v "$PWD/backups":/to \
    alpine tar czf /to/media-$(date +%Y%m%d).tar.gz -C /from .
```

(volume name may differ — check with `docker volume ls` / `podman volume ls`)

Put `backup.sh` on a cron job (or a systemd timer) for anything beyond
"I'll remember to run it" — neither is set up automatically here.

## PostgreSQL tuning

Nothing elaborate: the app already uses persistent connections
(`CONN_MAX_AGE`, `config/settings/base.py`) to avoid a fresh TCP+auth
handshake per request, which is the tuning knob that actually matters at
this project's scale. The stock `postgres:16-alpine` defaults are
otherwise left alone — tuning `shared_buffers`/`work_mem`/etc. without
real production load to measure against is just guessing, and guessing
wrong tends to hurt more than the defaults do.

## Updating

```sh
git pull
docker compose up -d --build
```

`collectstatic` and `migrate` run again automatically on the new
container's start.
