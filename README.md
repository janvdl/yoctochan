# Yoctochan

A very small, classic-style imageboard built with Django. This is a spare-time
project and a work in progress.

## Project status

**Early development — not production-ready.** The reading and posting flows work
end to end, but there is no moderation tooling, no abuse/rate-limiting
protection, and no deployment/production configuration yet. Runs on SQLite with
Django's development server. Expect breaking changes and schema churn.

Progress is tracked in [ROADMAP.md](ROADMAP.md). Roughly where things stand:

| Area | Status |
| --- | --- |
| Browsing — homepage, board index, threads, catalogue, pagination | Working |
| Post rendering — greentext, `>>` post references, auto-linking, HTML escaping | Working |
| Posting — create threads, reply, bumping, bump limits, thread locking | Working |
| Image uploads — one image per post (JPG/PNG/GIF/WebP), server-side thumbnails, click-to-expand | Working |
| Error pages (400/403/404/500) | Working |
| Moderation — delete/lock/sticky, reports, bans, mod dashboard | Not started (Django admin only) |
| Abuse & security — rate limiting, flood control, spam detection, CAPTCHA, secure headers | Not started |
| Performance — caching, Redis, HTMX, background jobs, search, archival | Not started |
| Production — settings split, deployment, HTTPS, media storage, backups, monitoring | Not started |

## Tech stack

- Python 3.13, [Django](https://www.djangoproject.com/) 6.1
- SQLite for now (PostgreSQL planned)
- [Pillow](https://python-pillow.org/) for image handling and thumbnails
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

The bundled `config/settings.py` ships with `DEBUG = True` and an insecure
`SECRET_KEY`; it is for local development only.

## Running the tests

```sh
python manage.py test
```

## License

[GNU AGPL v3.0](LICENSE).
