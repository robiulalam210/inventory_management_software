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
# SECURITY
# -----------------------------
SECRET_KEY = "django-insecure-meherinmart-xyz-2024-secret-key-change-this-in-production"
DEBUG = True  # Set to False in production

ALLOWED_HOSTS = [
    "meherinmart.xyz",
    "www.meherinmart.xyz",
    "localhost",
    "127.0.0.1",
    ".onrender.com",
]

CSRF_TRUSTED_ORIGINS = [
    "https://meherinmart.xyz",
    "https://www.meherinmart.xyz",
]

CORS_ALLOWED_ORIGINS = [
    "https://meherinmart.xyz",
    "https://www.meherinmart.xyz",
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
            ],
        },
    },
]

WSGI_APPLICATION = 'inventory_api.wsgi.application'

# -----------------------------
# POSTGRESQL DATABASE CONFIGURATION
# -----------------------------
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'meherinm_meherinmart_db',      # Database name
#         'USER': 'root',                          # MySQL user
#         'PASSWORD': '',       # MySQL password
#         'HOST': 'localhost',                   # MySQL host
#         'PORT': '3306',                          # MySQL default port
#         'OPTIONS': {
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#         }
#     }
# }
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'meherinm_meherinmart_db',      # Database name
#         'USER': 'meherinm_robi',                          # MySQL user
#         'PASSWORD': 'meherinmart@123',       # MySQL password
#         'HOST': '127.0.0.1',                     # MySQL host
#         'PORT': '3306',                          # MySQL default port
#         'OPTIONS': {
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#         }
#     }
# }
# -----------------------------
# SQLITE DATABASE CONFIGURATION
# -----------------------------
DATABASES = {
    'default': {                        
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'meherinm_meherinmart_db',      # Database name
        'USER': 'meherinm_robi',                          # MySQL user
        'PASSWORD': 'meherinmart@123', 
        'HOST': 'localhost',       # MySQL password
    }
}

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
# STATIC FILES
# -----------------------------
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# -----------------------------
# SECURITY SETTINGS
# -----------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# -----------------------------
# DEFAULT AUTO FIELD
# -----------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField' 