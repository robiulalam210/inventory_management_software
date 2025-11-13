from pathlib import Path
import os
import dj_database_url
from datetime import timedelta

# -----------------------------
# BASE DIR
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
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-dev-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"

# ✅ Render domain এবং localhost অনুমোদিত করো
ALLOWED_HOSTS = [
    "inventory-management-software-1.onrender.com",
    "localhost",
    "127.0.0.1",
]

# ✅ Render এর CSRF সাপোর্টের জন্য অবশ্যই দরকার
CSRF_TRUSTED_ORIGINS = [
    "https://inventory-management-software-1.onrender.com",
]

# (যদি ফ্রন্টএন্ড আলাদা হোস্টে থাকে, সেটা এখানে যোগ করো)
CORS_ALLOWED_ORIGINS = [
    "https://inventory-management-software-1.onrender.com",
]

APPEND_SLASH = True
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/admin/dashboard/'   # Optional, for post-login redirect
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
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ✅ whitenoise উপরে রাখো
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
# DATABASE
# -----------------------------
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# -----------------------------
# AUTH
# -----------------------------
AUTH_USER_MODEL = 'core.User'

# -----------------------------
# REST FRAMEWORK
# -----------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
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
TIME_ZONE = 'Asia/Dhaka'  # ✅ তোমার জন্য লোকাল টাইম
USE_I18N = True
USE_TZ = True

# -----------------------------
# STATIC FILES
# -----------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# -----------------------------
# DEFAULT AUTO FIELD
# -----------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
