"""
Django settings for the Saticoy lemon storage tracker (v1).

Everything environment-specific comes from environment variables so the same
code runs against local SQLite + local files and against Supabase Postgres +
Supabase Storage. See README for the variable list.
"""

import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [x.strip() for x in os.environ.get(name, default).split(',') if x.strip()]


# --- Core -------------------------------------------------------------------

ENVIRONMENT = os.environ.get('DJANGO_ENV', 'development').strip().lower()
DEBUG = env_bool('DJANGO_DEBUG', default=ENVIRONMENT == 'development')
DEMO_MODE = env_bool('DEMO_MODE', default=DEBUG)
if ENVIRONMENT == 'production' and DEBUG:
    raise ImproperlyConfigured('DJANGO_DEBUG must be false in production.')
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY', 'django-insecure-dev-only-w!^#sa(f4co54ple=j)3$d59w8qz92gnb4m%gmqw'
)
if not DEBUG and SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set outside development.')
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')
if ENVIRONMENT == 'production':
    required_names = [
        'DJANGO_ALLOWED_HOSTS',
        'DJANGO_CSRF_TRUSTED_ORIGINS',
        'SUPABASE_DB_HOST',
        'SUPABASE_DB_PASSWORD',
        'SUPABASE_S3_ENDPOINT',
        'SUPABASE_S3_ACCESS_KEY',
        'SUPABASE_S3_SECRET_KEY',
        'EMAIL_HOST',
    ]
    missing = [name for name in required_names if not os.environ.get(name, '').strip()]
    if missing:
        raise ImproperlyConfigured(
            f'Production configuration is missing: {", ".join(missing)}'
        )

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SESSION_COOKIE_HTTPONLY = True
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    # Platform probes hit these over internal HTTP; a 301 would read as unhealthy.
    SECURE_REDIRECT_EXEMPT = [r'^healthz/$', r'^readyz/$']
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_SECURE_HSTS_SECONDS', '3600'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS')
    SECURE_HSTS_PRELOAD = env_bool('DJANGO_SECURE_HSTS_PRELOAD')
    if env_bool('DJANGO_BEHIND_HTTPS_PROXY'):
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Absolute URL of this deployment, used for links in the Monday report email.
SITE_URL = os.environ.get('SITE_URL', 'http://127.0.0.1:8000').rstrip('/')
if ENVIRONMENT == 'production' and not SITE_URL.startswith('https://'):
    raise ImproperlyConfigured('SITE_URL must use https:// in production.')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'lots',
    'sampling',
    'forecast',
    'warehouse',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.csp.ContentSecurityPolicyMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'lots.audit.AuditUserMiddleware',
    'lots.middleware.ForemanLanguageMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

_image_sources = [CSP.SELF, 'data:', 'blob:']
if os.environ.get('SUPABASE_S3_ENDPOINT'):
    _s3_url = urlsplit(os.environ['SUPABASE_S3_ENDPOINT'])
    _image_sources.append(f'{_s3_url.scheme}://{_s3_url.netloc}')

SECURE_CSP = {
    'default-src': [CSP.SELF],
    'base-uri': [CSP.SELF],
    'connect-src': [CSP.SELF],
    'font-src': [CSP.SELF],
    'form-action': [CSP.SELF],
    'frame-ancestors': [CSP.NONE],
    'img-src': _image_sources,
    'object-src': [CSP.NONE],
    'script-src': [CSP.SELF, CSP.UNSAFE_INLINE],
    'style-src': [CSP.SELF, CSP.UNSAFE_INLINE],
}
SECURE_CSP_REPORT_ONLY = {}

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'lots.context_processors.roles',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# --- Database ---------------------------------------------------------------
#
# SQLite for local development. For Supabase Postgres set SUPABASE_DB_HOST and
# SUPABASE_DB_PASSWORD (plus _PORT/_NAME/_USER if they differ). Requires
# `pip install psycopg[binary]`. Use the Supabase *session pooler* host so the
# ORM's persistent connections behave.

if os.environ.get('SUPABASE_DB_HOST'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': os.environ['SUPABASE_DB_HOST'],
            'PORT': os.environ.get('SUPABASE_DB_PORT', '5432'),
            'NAME': os.environ.get('SUPABASE_DB_NAME', 'postgres'),
            'USER': os.environ.get('SUPABASE_DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('SUPABASE_DB_PASSWORD', ''),
            'OPTIONS': {'sslmode': 'require' if ENVIRONMENT == 'production' else os.environ.get('DATABASE_SSLMODE', 'require')},
            'CONN_MAX_AGE': 60,
            'CONN_HEALTH_CHECKS': True,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- Auth -------------------------------------------------------------------
#
# Three groups: foreman, gm, admin (created by `manage.py setup_roles`). A
# user's plant lives on lots.UserProfile. Foreman sessions persist 30 days so
# the phone stays logged in between weekly visits.

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
SESSION_COOKIE_AGE = 30 * 24 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
CSRF_COOKIE_AGE = SESSION_COOKIE_AGE

ROLE_GROUPS = ('foreman', 'gm', 'admin')


# --- I18N -------------------------------------------------------------------

LANGUAGE_CODE = 'en-us'
LANGUAGES = [('en', 'English'), ('es', 'Español')]
LOCALE_PATHS = [BASE_DIR / 'locale']
# Plant-floor default for foreman accounts that have not chosen a language
# from the header toggle. GMs and admins default to LANGUAGE_CODE.
FOREMAN_DEFAULT_LANGUAGE = os.environ.get('FOREMAN_DEFAULT_LANGUAGE', 'es').strip()
LANGUAGE_COOKIE_AGE = SESSION_COOKIE_AGE
TIME_ZONE = 'America/Los_Angeles'
USE_I18N = True
USE_TZ = True


# --- Static & media ---------------------------------------------------------
#
# Photos are never served from MEDIA_URL. They go through sampling.views.photo,
# which checks login and then either streams the file (local storage) or
# redirects to a short-lived signed URL (Supabase Storage via its S3 endpoint).

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

if os.environ.get('SUPABASE_S3_ENDPOINT'):
    # Supabase Storage speaks S3. Endpoint looks like
    # https://<project-ref>.supabase.co/storage/v1/s3 ; create the bucket
    # (private) in the Supabase dashboard and an S3 access key pair under
    # Storage -> S3 connection. Requires `pip install django-storages[s3]`.
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3.S3Storage',
            'OPTIONS': {
                'endpoint_url': os.environ['SUPABASE_S3_ENDPOINT'],
                'bucket_name': os.environ.get('SUPABASE_S3_BUCKET', 'lemon-photos'),
                'access_key': os.environ.get('SUPABASE_S3_ACCESS_KEY', ''),
                'secret_key': os.environ.get('SUPABASE_S3_SECRET_KEY', ''),
                'region_name': os.environ.get('SUPABASE_S3_REGION', 'us-west-1'),
                'addressing_style': 'path',
                'signature_version': 's3v4',
                'default_acl': None,
                'file_overwrite': False,
                'querystring_auth': True,
                'querystring_expire': 3600,
            },
        },
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
    }
    PHOTO_URLS_ARE_SIGNED = True
else:
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
    }
    PHOTO_URLS_ARE_SIGNED = False

WHITENOISE_MAX_AGE = 31536000 if not DEBUG else 0

# Phone photos are large; allow ~25 MB uploads (two photos per sample).
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024


# --- Email ------------------------------------------------------------------
#
# Console backend locally. Set EMAIL_HOST (+ port/user/password) for SMTP.

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'lemon-tracker@localhost')

if os.environ.get('EMAIL_HOST'):
    MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
            'OPTIONS': {
                'host': os.environ['EMAIL_HOST'],
                'port': int(os.environ.get('EMAIL_PORT', '587')),
                'username': os.environ.get('EMAIL_HOST_USER', ''),
                'password': os.environ.get('EMAIL_HOST_PASSWORD', ''),
                'use_tls': env_bool('EMAIL_USE_TLS', default=True),
            },
        },
    }
else:
    if not DEBUG:
        raise ImproperlyConfigured('EMAIL_HOST must be set outside development.')
    MAILERS = {
        'default': {'BACKEND': 'django.core.mail.backends.console.EmailBackend'},
    }


# --- Logging ----------------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO')},
}
