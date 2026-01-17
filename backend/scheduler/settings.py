"""
Django settings for scheduler project.
Production-ready Appointment Scheduling System
"""
import os
from pathlib import Path
from datetime import timedelta
import dj_database_url
import environ
import ipaddress
import socket

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from BASE_DIR/.env (if present) and process environment
env = environ.Env(
    DEBUG=(bool, False),
)
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(str(env_file))

# Security settings
SECRET_KEY = env('SECRET_KEY', default='django-insecure-dev-key-change-this')
DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = [
    h.strip() for h in env('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    
    # Local apps
    'core',
    'authentication',
    'slots',
    'bookings',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'scheduler.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'scheduler.wsgi.application'

# Database - Supabase PostgreSQL
DATABASE_URL = env('DATABASE_URL', default='')
if DATABASE_URL:
    db_config = dj_database_url.parse(DATABASE_URL, engine='django.db.backends.postgresql')

    # Some hosting providers do not have IPv6 egress enabled. If the DB host resolves
    # to IPv6 first, connections may fail with "Network is unreachable".
    # Prefer an IPv4 address when available.
    host = (db_config.get('HOST') or '').strip()
    if host and not host.startswith('/'):
        try:
            ipaddress.ip_address(host)
        except ValueError:
            # Not an IP literal, try resolving an IPv4 address.
            try:
                infos = socket.getaddrinfo(host, None, socket.AF_INET)
                if infos:
                    ipv4 = infos[0][4][0]
                    if ipv4:
                        db_config['HOST'] = ipv4
            except socket.gaierror:
                # DNS failure: keep the original host.
                pass
    # Connection options
    options = dict(db_config.get('OPTIONS') or {})
    # Set search path for Supabase to use public schema
    options['options'] = '-c search_path=public'

    # SSL settings
    # - For Supabase, enforce SSL by default
    # - For local dev (e.g. docker compose host=db), do not force SSL unless explicitly set
    sslmode = env('DB_SSLMODE', default='')
    host = (db_config.get('HOST') or '').lower()
    if not sslmode and 'supabase' in host:
        sslmode = 'require'
    if sslmode:
        options['sslmode'] = sslmode

    db_config['OPTIONS'] = options
    DATABASES = {'default': db_config}
else:
    # Fallback for local development using SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'core.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=int(env('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=60))
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=int(env('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7))
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# CORS Configuration
if DEBUG:
    # In development, allow all origins for easier testing
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = [
        origin.strip() 
        for origin in env(
            'CORS_ALLOWED_ORIGINS', 
            default='http://localhost:5173,http://localhost:5174'
        ).split(',')
        if origin.strip()
    ]

    CORS_ALLOWED_ORIGIN_REGEXES = [
        regex.strip()
        for regex in env('CORS_ALLOWED_ORIGIN_REGEXES', default='').split(',')
        if regex.strip()
    ]
CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins (needed for Django admin / any cookie-based flows behind HTTPS)
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in env('CSRF_TRUSTED_ORIGINS', default='').split(',')
    if origin.strip()
]

# Security / proxy settings (Render, etc.)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
    SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=True)
    CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=True)

# SSO Configuration
SSO_MODE = env('SSO_MODE', default='mock')  # 'mock' or 'real'
PBL_API_URL = env('PBL_API_URL', default='')
# Do not hardcode; must come from .env or process environment
PBL_API_KEY = env('PBL_API_KEY', default=os.environ.get('PBL_API_KEY', ''))

# Dev login (development-only endpoint: /api/dev/sso-login/)
# Keep this disabled unless you intentionally use it.
ALLOW_DEV_LOGIN = env('ALLOW_DEV_LOGIN', default='0')
DEV_LOGIN_SECRET = env('DEV_LOGIN_SECRET', default='')

# Frontend URLs
STUDENT_FRONTEND_URL = env('STUDENT_FRONTEND_URL', default='http://localhost:5173')
FACULTY_FRONTEND_URL = env('FACULTY_FRONTEND_URL', default='http://localhost:5174')

# Business Rules Configuration
CANCELLATION_WINDOW_HOURS = int(env('CANCELLATION_WINDOW_HOURS', default=24))

# Group/team identification
# Options: 'external', 'local', 'external_then_local', 'local_then_external'
GROUP_ID_SOURCE = env('GROUP_ID_SOURCE', default='external_then_local')

# Optional: explicitly set the Supabase roster table name (public schema) that contains
# columns: email, group_id, is_leader (and optionally roll_number).
GROUP_ROSTER_TABLE = env('GROUP_ROSTER_TABLE', default='')

# If enabled, only group leaders can create bookings.
# Leader info is only available when GROUP_ID_SOURCE uses 'local' roster lookup.
BOOKING_LEADER_ONLY = env.bool('BOOKING_LEADER_ONLY', default=False)

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': env('DJANGO_LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
    },
}

# Optional SQL query logging (use only for debugging / staging)
SQL_DEBUG = env.bool('SQL_DEBUG', default=False)
if SQL_DEBUG:
    LOGGING.setdefault('loggers', {})
    LOGGING['loggers']['django.db.backends'] = {
        'handlers': ['console'],
        'level': 'DEBUG',
        'propagate': False,
    }
