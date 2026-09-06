# Built with context = repo root (see docker-compose.yml's `build:` block),
# so paths below are relative to the project root, not this file.
FROM docker.io/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# libpq5: the runtime half of psycopg[binary]'s Postgres client library.
# Pillow and pillow-heif ship their own bundled libraries in their wheels,
# so nothing else is needed here.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x deploy/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["deploy/entrypoint.sh"]
