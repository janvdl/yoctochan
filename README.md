# Yoctochan

A very small, classic-style imageboard built with Django. This is a spare-time
project and a work in progress.

## Project status

**Early development — not production-ready.** The reading and posting flows work
end to end, with most of the classic imageboard posting conventions
(tripcodes, sage, backlinks, "You" highlighting, a client-side thread
watcher) in place. Phase 4 moderation is complete (soft-delete, lock,
sticky, an audit log, board-scoped moderators, poster-IP capture, a report
queue, and IP bans with expiry), and Phase 5 abuse/security protections are
in place (rate limiting, spam/duplicate detection, secure headers and
cookies) aside from a CAPTCHA, which is deliberately deferred. Settings are
split into dev/prod modules driven by environment variables, and the
database can be SQLite (default, zero setup) or PostgreSQL. Boards get
per-board search, automatic thread archival once a board fills up, and a
first pass of indexes/query cleanup targeted at the hottest paths (ban
checks, rate limiting, the reports queue). There's a real deployment now
too: a Docker/Podman Compose stack (see [deploy/](deploy/)) with gunicorn,
PostgreSQL, Redis, and Caddy handling TLS and static/media — tested end to
end, including a genuine backup-and-restore cycle, not just written and
assumed to work. Expect breaking changes and schema churn regardless.

Progress is tracked in [ROADMAP.md](ROADMAP.md). Roughly where things stand:

| Area | Status |
| --- | --- |
| Browsing — homepage, board index, threads, catalogue, pagination | Working |
| Post rendering — greentext, `>>` post references, auto-linking, HTML escaping | Working |
| Posting — create threads, reply, bumping, bump limits, thread locking | Working |
| Imageboard conventions — name field, tripcodes, sage, backlinks, "You" highlighting, thread watcher | Working |
| Image uploads — one image per post (JPG/PNG/GIF/WebP, plus HEIC/HEIF converted on the way in), server-side thumbnails, EXIF stripped, click-to-expand | Working |
| Error pages (400/403/404/500) | Working |
| Moderation — soft-delete post/thread, lock, sticky, `/mod/` dashboard, audit log, board-scoped moderators, poster IP capture, report queue, IP bans (global + per-board) with expiry | Working |
| Abuse & security — rate limiting, flood control, spam detection, secure headers | Working (no CAPTCHA yet) |
| Performance — per-board search, thread archival, hot-path indexes, query cleanup, Redis | Working (no cached views or background jobs yet) |
| Config — environment-driven settings, dev/prod split, PostgreSQL | Working |
| Production — Docker/Podman Compose deployment, HTTPS, static/media serving, logging, backups (tested restore) | Working |

## Tech stack

- Python 3.13, [Django](https://www.djangoproject.com/) 6.1
- SQLite by default; PostgreSQL supported (via [psycopg](https://www.psycopg.org/))
- [Pillow](https://python-pillow.org/) for image handling and thumbnails, with
  [pillow-heif](https://github.com/bigcat88/pillow_heif) for HEIC/HEIF uploads
- Server-rendered templates, plain CSS, a small amount of vanilla JavaScript (no frontend framework)

## Running locally

```sh
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then open http://127.0.0.1:8000/. Boards are created through the Django admin at
`/admin/` (there is no public board-creation UI). Uploaded images are written to
`media/` in development.

No configuration is required for the above — it runs with `DEBUG = True`, an
insecure development `SECRET_KEY`, and SQLite. To override any of that
(including switching to PostgreSQL), copy `.env.example` to `.env` and fill
in what you need; `config/settings/base.py` reads it automatically and real
environment variables always take precedence over `.env`. See
`.env.example` for the full list of variables, including `DATABASE_ENGINE`,
`POSTGRES_*`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, and `DJANGO_ALLOWED_HOSTS`.

Settings are split into `config/settings/dev.py` (the default) and
`config/settings/prod.py`. `prod.py` shares the same environment-driven
settings but refuses to start unless `DJANGO_DEBUG=false`, a real
`DJANGO_SECRET_KEY` (not the dev fallback), and a non-empty
`DJANGO_ALLOWED_HOSTS` are all set (and, if `DATABASE_ENGINE=postgresql`,
a real `POSTGRES_PASSWORD`) — select it by exporting
`DJANGO_SETTINGS_MODULE=config.settings.prod` before running `manage.py` or
your WSGI/ASGI server. See [Deployment](#deployment) below for the actual
container stack that runs it this way.

Posting supports a few classic imageboard conventions on top of the plain
name field: typing `Name#password` derives a tripcode (`!xxxxxxxxxx`) from
the password so a poster can prove they're the same person across posts,
without an account — the password itself is salted with `SECRET_KEY` and
never recoverable from it. A reply can be marked "sage" to post without
bumping the thread. Each post shows a "Replies:" backlink to any post that
`>>`-referenced it. "You" highlighting and the thread watcher (a small
persistent widget listing threads you've pinned, with new-reply counts) are
both client-side only, backed by this browser's `localStorage` — there's no
poster account for either to attach to server-side.

An uploaded image goes through a small pipeline before it's stored: a HEIC/HEIF
photo (the default format on modern iPhones) is converted to JPEG so it isn't
just rejected outright; EXIF metadata (GPS coordinates, camera make/model,
timestamps) is then stripped from JPEG/PNG/WEBP uploads — real deanonymising
data on a board where poster IPs and names are already kept private or
hidden — with orientation baked into the pixels first so removing the tag
doesn't leave the image sideways. An upload with no EXIF to strip, or in an
already-fine format, is stored byte-for-byte as uploaded rather than being
needlessly re-encoded.

Each board has a `[ Search ]` link — a plain case-insensitive match over
post content and thread subjects (subject matches surface the thread's OP),
scoped to that board. It's deliberately simple (works identically on SQLite
and PostgreSQL); a real full-text index would be a Phase 6 follow-up if a
board ever gets large enough to need it. Boards also archive themselves
automatically: once a board has more active threads than its `max_pages *
threads_per_page` (both set per-board, in the admin), the oldest
non-pinned threads are frozen (no more replies, dropped from the active
listing) to make room — still directly viewable at their URL, just no
longer part of the live board.

Moderation lives at `/mod/`. Any staff user who is a superuser, or who has a
`Moderator` record (created in the admin), can log in there; a `Moderator` with
no boards selected is global, otherwise they are scoped to the boards listed.
Moderators see inline delete/lock/sticky controls on threads and posts, poster
IPs (captured server-side, never shown publicly), a report queue at
`/mod/reports/` (anyone can report a post), and IP bans at `/mod/bans/`. Bans
are global or per-board, carry a preset duration (or permanent), and block
posting with a "you are banned" page until they expire or are lifted. A scoped
moderator can only issue bans for their own boards.

## Deployment

```sh
cp .env.example .env    # fill in DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, POSTGRES_PASSWORD
cd deploy
docker compose up -d --build      # or: podman-compose --env-file ../.env up -d --build
```

That's the whole thing: gunicorn + PostgreSQL + Redis + Caddy (TLS,
static/media serving), wired together and — unusually for a "here's a
Dockerfile" README — actually run end to end while building this,
including destroying the database volume and proving `deploy/restore.sh`
brings every row back from a `deploy/backup.sh` dump. Full details,
including the HTTPS/domain story and how backups work, are in
[deploy/README.md](deploy/README.md).

## Running the tests

```sh
python manage.py test
```

## License

[GNU AGPL v3.0](LICENSE).
