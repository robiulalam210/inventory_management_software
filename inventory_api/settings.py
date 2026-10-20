from pathlib import Path
import os
from datetime import timedelta

# -----------------------------
# BASE DIR
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / 'templates'


# -----------------------------
# SECURITY
# -----------------------------
# সার্ভারে .env / cPanel environment থেকে নেওয়া হয়; না থাকলে আগের মান
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', "django-insecure-meherinmart-xyz-2024-secret-key-change-this-in-production")
# DJANGO_DEBUG=0 দিলে production (https বাধ্যতামূলক, নিরাপদ cookie)। না দিলে আগের মতো True
DEBUG = os.environ.get('DJANGO_DEBUG', '1') not in ('0', 'false', 'False')
ALLOWED_HOSTS = [
    'dokankhata.meherinmart.com',
    'www.dokankhata.meherinmart.com',
    'inventoryapp.meherinmart.xyz',
    'www.inventoryapp.meherinmart.xyz',
    'localhost',
    '127.0.0.1',
    '10.0.2.2',
    '0.0.0.0',
    '192.168.0.140',
    '192.168.1.100',
]

APPEND_SLASH = True
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/admin/'

# -----------------------------
# INSTALLED APPS
# -----------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',

    'rest_framework',
    'django_filters',
    'rest_framework_simplejwt',
    'corsheaders',

    # Project apps
    'purchases',
    'products',
    'sales',
    'company',
    'returns',
    'branch_warehouse',
    'accounts',
    'reports',
    'expenses',
    'income',
    'customers',
    'suppliers',
    'money_receipts',
    'transactions',
    'supplier_payment',
    'account_transfer',
    'shop',
    'payroll',  # Payroll app
    'stockops',  # Stock Adjustment / Stocktake / Day Close
    'core.apps.CoreConfig',
    'offline_sync.apps.OfflineSyncConfig',
    'web.apps.WebConfig',  # web software (/app/) — admin panel নয়
]

# -----------------------------
# MIDDLEWARE
# -----------------------------
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
    'core.middleware.CompanyMiddleware',
    'offline_sync.middleware.AuditContextMiddleware',
    'offline_sync.middleware.IdempotencyMiddleware',
]

ROOT_URLCONF = 'inventory_api.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATES_DIR],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'web.context_processors.web_shell',
            ],
        },
    },
]

WSGI_APPLICATION = 'inventory_api.wsgi.application'

# -----------------------------
# DATABASE CONFIGURATION
# -----------------------------
# SQLite (development)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        # একসাথে অনেক request এলে "database is locked" এ worker আটকে যেত।
        # timeout: লক খুললে ৩০ সেকেন্ড পর্যন্ত অপেক্ষা; WAL: পড়া আর লেখা একে অপরকে আটকায় না।
        'OPTIONS': {
            'timeout': 30,
            'init_command': 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;',
            'transaction_mode': 'IMMEDIATE',
        },
    }
}

# MySQL চাইলে: ENGINE 'django.db.backends.mysql' + NAME/USER/PASSWORD — পাসওয়ার্ড কোডে নয়,
# environment variable থেকে নিন (os.environ['DB_PASSWORD'])।

# -----------------------------
# AUTH
# -----------------------------
AUTH_USER_MODEL = 'core.User'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# -----------------------------
# PASSWORD VALIDATION
# -----------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# -----------------------------
# INTERNATIONALIZATION
# -----------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

# -----------------------------
# STATIC & MEDIA FILES
# -----------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Create dirs if missing
os.makedirs(STATICFILES_DIRS[0], exist_ok=True)
os.makedirs(MEDIA_ROOT, exist_ok=True)

# Django 5 এ STATICFILES_STORAGE আর কাজ করে না — STORAGES দিতে হয়।
# production: whitenoise ফাইলগুলো gzip/brotli করে আর নামে hash যোগ করে, তাই ব্রাউজার লম্বা সময় cache রাখে,
# আর নতুন আপডেট দিলে সাথে সাথে নতুন ফাইল নেয়।
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG
                    else 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# -----------------------------
# CORS
# -----------------------------
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = [
        "https://dokankhata.meherinmart.com",
        "https://inventoryapp.meherinmart.xyz",
        "https://www.inventoryapp.meherinmart.xyz",
    ]

# -----------------------------
# SECURITY (production)
# -----------------------------
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_PROXY_SSL_HEADER = None

# https পাতার ফর্ম (লগইন, রেজিস্টার) — এটা না থাকলে "CSRF verification failed" (403) আসে
CSRF_TRUSTED_ORIGINS = [
    'https://dokankhata.meherinmart.com',
    'https://www.dokankhata.meherinmart.com',
    'https://inventoryapp.meherinmart.xyz',
] + [o for o in os.environ.get('DJANGO_EXTRA_ORIGINS', '').split(',') if o.strip()]  # অন্য domain লাগলে: কমা দিয়ে
# একই domain গুলো ALLOWED_HOSTS এও (https://x.com → x.com)
ALLOWED_HOSTS += [o.strip().split('://')[-1].split('/')[0].split(':')[0]
                  for o in os.environ.get('DJANGO_EXTRA_ORIGINS', '').split(',') if o.strip()]

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # ব্রাউজারকে বলা: এই সাইট সবসময় https এ খুলবে (৩০ দিন মনে রাখবে)। subdomain গুলোতে চাপানো হয় না।
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'

# -----------------------------
# DEFAULT AUTO FIELD
# -----------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + ["x-device-id", "x-client-source", "x-idempotency-key"]

# -----------------------------
# CACHE — লগইন-লক আর রেট-লিমিট এর হিসাব
# cPanel একসাথে কয়েকটা process চালায়; memory cache হলে প্রতিটার হিসাব আলাদা হত আর লক কাজ করত না।
# তাই ফাইলে রাখা হয় — সব process একই হিসাব দেখে।
# -----------------------------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(BASE_DIR / 'tmp' / 'cache'),
        'TIMEOUT': 60 * 60,
        'OPTIONS': {'MAX_ENTRIES': 5000},
    }
}

# -----------------------------
# LOGGING — সার্ভারে কোনো error হলে logs/error.log এ লেখা থাকে (তারিখ, পাতা, পুরো traceback)
# প্রতিদিন নতুন ফাইল, ১৪ দিনের পুরনো নিজে মুছে যায়।
# -----------------------------
LOG_DIR = BASE_DIR / 'logs'
os.makedirs(LOG_DIR, exist_ok=True)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'plain': {'format': '[{asctime}] {levelname} {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': str(LOG_DIR / 'error.log'),
            'when': 'midnight',
            'backupCount': 14,
            'encoding': 'utf-8',
            'formatter': 'plain',
        },
        'console': {'class': 'logging.StreamHandler', 'formatter': 'plain'},
    },
    'loggers': {
        'django': {'handlers': ['console', 'error_file'], 'level': 'WARNING'},
        'django.request': {'handlers': ['error_file'], 'level': 'ERROR', 'propagate': False},
    },
}

# ফাইল আপলোডের সীমা (ছবি / লোগো) — ১০ MB এর বেশি অনুরোধ নেওয়া হয় না
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# HSTS subdomain/preload ইচ্ছা করে বন্ধ — meherinmart.com এর অন্য subdomain গুলো সবসময় https এ নাও থাকতে পারে
SILENCED_SYSTEM_CHECKS = ['security.W005', 'security.W021']
