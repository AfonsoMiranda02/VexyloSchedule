import os
import secrets
import dj_database_url
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_urlsafe(50)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = (os.getenv('DEBUG') or 'True') == 'True'

ALLOWED_HOSTS = ['*', 'localhost', '127.0.0.1', '.onrender.com']

CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
    'http://localhost:5010',
    'http://127.0.0.1:5010',
    'http://localhost:8000',
    'http://127.0.0.1:8000'
]

# Application definition
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'website',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'website.context_processors.business_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL') or f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-pt'
TIME_ZONE = 'Europe/Lisbon'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

JAZZMIN_SETTINGS = {
    "site_title": "NexoraSchedule",
    "site_header": "NexoraSchedule",
    "site_brand": "NexoraSchedule",
    "welcome_sign": "Bem-vindo ao NexoraSchedule",
    "copyright": "NexoraSchedule",
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "website.appointment": "fas fa-calendar-check",
        "website.service": "fas fa-list",
        "website.servicecategory": "fas fa-tags",
        "website.staffmember": "fas fa-user-tie",
        "website.businessinfo": "fas fa-info-circle",
        "website.testimonial": "fas fa-comment",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": False,
    "custom_css": "css/custom_admin.css",
    "custom_js": None,
    "show_ui_builder": False,
}

JAZZMIN_UI_TWEAKS = {
    "theme": "litera",
}
