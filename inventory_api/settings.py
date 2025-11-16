from pathlib import Path
import os
from datetime import timedelta

# -----------------------------
# BASE DIR
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')

print(f"BASE_DIR is set to: {BASE_DIR}")
print(f"TEMPLATES_DIR is set to: {TEMPLATES_DIR}")

# -----------------------------
# ENVIRONMENT CONFIG
# -----------------------------
DEBUG = True  # Force True for local development
SECRET_KEY = "django-insecure-meherinmart-2024-local-dev-key"

# -----------------------------
# HOSTS AND CORS
# -----------------------------
ALLOWED_HOSTS = [
    "meherinmart.xyz",
    "www.meherinmart.xyz",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
]

CSRF_TRUSTED_ORIGINS = [
    "https://meherinmart.xyz",
    "https://www.meherinmart.xyz",
]

CORS_ALLOWED_ORIGINS = [
    "https://meherinmart.xyz",
    "https://www.meherinmart.xyz",
]

CORS_ALLOW_ALL_ORIGINS = True  # Allow all in local development

# -----------------------------
# LOGIN
# -----------------------------
APPEND_SLASH = True
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/admin/'

# -----------------------------
# DATABASE - SIMPLE SQLITE FOR LOCAL
# -----------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

print("✅ Using SQLite for local development")

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

    # Dev tools
    'django_extensions',

    # Third-party
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
    "branch_warehouse",
    'accounts',
    'reports',
    'expenses',
    'customers',
    'suppliers',
    'money_receipts',
    'transactions',
    'supplier_payment',
    "core.apps.CoreConfig",
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
]

ROOT_URLCONF = 'inventory_api.urls'

# -----------------------------
# TEMPLATES
# -----------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATES_DIR],
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

WSGI_APPLICATION = 'inventory_api.wsgi.application'

# -----------------------------
# JWT SETTINGS
# -----------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# -----------------------------
# AUTH
# -----------------------------
AUTH_USER_MODEL = 'core.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
}

# -----------------------------
# PASSWORD VALIDATORS
# -----------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
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
# STATIC FILES
# -----------------------------
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# -----------------------------
# DEFAULT AUTO FIELD
# -----------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# -----------------------------
# MEDIA FILES
# -----------------------------
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Ensure media directories exist
def ensure_media_dirs():
    media_dirs = [
        'company/logos',
        'users/profile_pictures', 
        'staff/images',
        'products',
        'documents'
    ]
    for directory in media_dirs:
        dir_path = os.path.join(MEDIA_ROOT, directory)
        os.makedirs(dir_path, exist_ok=True)
        print(f"✅ Ensured directory: {dir_path}")

os.makedirs(MEDIA_ROOT, exist_ok=True)
ensure_media_dirs()

# -----------------------------
# SECURITY - DISABLE FOR LOCAL DEV
# -----------------------------
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# -----------------------------
# LOGGING
# -----------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# -----------------------------
# CUSTOM SETTINGS
# -----------------------------
COMPANY_COOKIE_NAME = 'company_id'
DEFAULT_CURRENCY = 'BDT'
DEFAULT_TIMEZONE = 'Asia/Dhaka'
LOW_STOCK_ALERT = True
AUTO_UPDATE_STOCK = True

DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760

SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 1209600

print("✅ Django settings loaded successfully!")
print(f"✅ Debug mode: {DEBUG}")
print(f"✅ Using SQLite database")