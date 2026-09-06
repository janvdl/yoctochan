"""
Django settings for config project.

This module holds everything ``dev.py`` and ``prod.py`` share. Neither of
those is "the real settings" on its own — pick one via
``DJANGO_SETTINGS_MODULE`` (``manage.py``/``wsgi.py``/``asgi.py`` default to
``config.settings.dev``, so local development needs no configuration at
all). See ``dev.py`` and ``prod.py`` for what each one changes.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.1/ref/settings/
"""

from pathlib import Path

from config.env import env_bool, env_int, env_list, env_str, load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Local-dev convenience: fill in anything not already set in the real
# environment from a ``.env`` file at the project root (gitignored, not
# required to exist). Production deployments should set real environment
# variables instead and can leave this file absent.
load_dotenv(BASE_DIR / ".env")


# SECURITY WARNING: keep the secret key used in production secret!
#
# The fallback below is the key `django-admin startproject` generated for
# this project. It's fine for `dev.py` (nothing it protects leaves your
# machine); `prod.py` refuses to start unless DJANGO_SECRET_KEY overrides it.
SECRET_KEY = env_str(
    "DJANGO_SECRET_KEY",
    "django-insecure-sntyuc+-$x*c3(nw4fyqqh1cuwr6uvw_s-!_z__e7^ge^==_zj",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool("DJANGO_DEBUG", default=True)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'boards'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases
#
# Defaults to SQLite so `python manage.py runserver` keeps working with zero
# setup. Set DATABASE_ENGINE=postgresql (plus the POSTGRES_* variables below)
# to run against PostgreSQL instead — the same settings serve both dev and
# prod, only the environment differs. Requires the `psycopg` package
# (already in requirements.txt).

DATABASE_ENGINE = env_str("DATABASE_ENGINE", "sqlite3")

if DATABASE_ENGINE == "postgresql":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env_str("POSTGRES_DB", "yoctochan"),
            'USER': env_str("POSTGRES_USER", "yoctochan"),
            'PASSWORD': env_str("POSTGRES_PASSWORD", ""),
            'HOST': env_str("POSTGRES_HOST", "localhost"),
            'PORT': env_str("POSTGRES_PORT", "5432"),
            'CONN_MAX_AGE': env_int("POSTGRES_CONN_MAX_AGE", 60),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]


# Media files (user uploads)

MEDIA_URL = "media/"

MEDIA_ROOT = BASE_DIR / "media"

# Uploaded images: accepted formats and maximum file size.
ALLOWED_IMAGE_FORMATS = ("JPEG", "PNG", "GIF", "WEBP")

ALLOWED_IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "gif", "webp")

MAX_IMAGE_SIZE = 5 * 1024 * 1024

# Bounding box (width, height) for the thumbnail shown in threads and the
# catalogue. Originals within this box are served directly without a thumbnail.
THUMBNAIL_SIZE = (250, 250)

# Post size limits.
#
# Message text is capped at the form level (CreateThreadForm/CreatePostForm,
# max_length=4_000); images are capped by MAX_IMAGE_SIZE above, checked once
# the upload is fully received. Everything else in a request body (all
# non-file fields combined) is bounded by Django's own
# DATA_UPLOAD_MAX_MEMORY_SIZE, which defaults to 2.5 MB — comfortably above
# what this form ever sends, so it's left at its default rather than
# duplicated here.

# Reject a post whose text is identical to another post made to the same
# thread (replies) or board (new threads) within this many seconds, or whose
# image is byte-for-byte identical to one made in that window. Guards against
# double-submits and rapid reposts (including a re-upload of the same file
# under a new name).
DUPLICATE_POST_WINDOW_SECONDS = 120

# Spam heuristics: reject a post outright when its text trips one of these.
# Pure content checks, no external service.
SPAM_MAX_LINKS = 3  # more than this many http(s):// links in one post
SPAM_MAX_CHAR_REPEAT = 10  # the same character repeated this many times in a row
SPAM_BLOCKED_PHRASES = []  # case-insensitive substrings; populate per-deployment

# Minimum time a single IP must wait between posts (thread or reply). Basic
# flood protection independent of content.
RATE_LIMIT_REPLY_COOLDOWN_SECONDS = 10

# An IP may start at most RATE_LIMIT_THREAD_MAX threads (across all boards)
# within this many seconds.
RATE_LIMIT_THREAD_WINDOW_SECONDS = 600
RATE_LIMIT_THREAD_MAX = 3

# Set to True only when the app runs behind a reverse proxy that sets a
# trustworthy X-Forwarded-For header; otherwise poster IPs come from REMOTE_ADDR.
TRUST_X_FORWARDED_FOR = env_bool("TRUST_X_FORWARDED_FOR", default=False)


# Security: cookies and browser-enforced headers
# https://docs.djangoproject.com/en/6.1/topics/security/
#
# Django's own defaults already cover SESSION_COOKIE_HTTPONLY,
# SECURE_CONTENT_TYPE_NOSNIFF, X_FRAME_OPTIONS and SECURE_REFERRER_POLICY.
# CSRF_COOKIE_HTTPONLY is off by default (some sites read the cookie from JS);
# this app never does, so lock it down.
CSRF_COOKIE_HTTPONLY = True

# HTTPS-only protections. These would break local `runserver` use over plain
# HTTP, so they're tied to DEBUG rather than hardcoded — flip DEBUG off for a
# production deployment (behind HTTPS) and they switch on automatically.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000  # 1 year, once behind HTTPS
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG


# Authentication (moderation area)

LOGIN_URL = "mod-login"

LOGIN_REDIRECT_URL = "mod-dashboard"

LOGOUT_REDIRECT_URL = "mod-login"


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

EMAIL_BACKEND = env_str(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
