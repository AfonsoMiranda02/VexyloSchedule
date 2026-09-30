import os
import dj_database_url
from dotenv import load_dotenv
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# 1. PARSING ROBUSTO DE DEBUG - Fails safe para False por omissão
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

# 2. SECRET_KEY FAIL-SAFE
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        # Fallback local apenas para desenvolvimento ativo
        SECRET_KEY = 'django-insecure-local-dev-key-vexylo-schedule-not-for-production'
    else:
        raise ImproperlyConfigured("CRÍTICO: A variável de ambiente SECRET_KEY é obrigatória em ambiente de produção (DEBUG=False).")

# 3. ALLOWED_HOSTS & HOST CANÓNICO
raw_allowed_hosts = os.getenv('ALLOWED_HOSTS', os.getenv('DJANGO_ALLOWED_HOSTS', ''))
if raw_allowed_hosts:
    ALLOWED_HOSTS = [h.strip() for h in raw_allowed_hosts.split(',') if h.strip()]
else:
    if DEBUG:
        ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']
    else:
        ALLOWED_HOSTS = ['.onrender.com', 'localhost', '127.0.0.1']

# Adicionar testserver durante testes automatizados
import sys
if 'test' in sys.argv or os.getenv('DJANGO_TEST') == 'true':
    if 'testserver' not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append('testserver')

if not DEBUG and '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured("SEGURANÇA: O wildcard '*' é proibido em ALLOWED_HOSTS em produção para prevenir envenenamento de cabeçalho Host.")

from urllib.parse import urlparse

raw_app_base_url = os.getenv('APP_BASE_URL', '').strip().rstrip('/')
if not raw_app_base_url:
    if DEBUG:
        APP_BASE_URL = 'http://localhost:8000'
    else:
        raise ImproperlyConfigured(
            "CRÍTICO DE PRODUÇÃO: A variável de ambiente APP_BASE_URL é obrigatória quando DEBUG=False "
            "para garantir a integridade dos links externos e mitigar Host Header Poisoning."
        )
else:
    parsed_base = urlparse(raw_app_base_url)
    if not parsed_base.scheme or not parsed_base.netloc:
        raise ImproperlyConfigured(
            f"CONFIGURAÇÃO INVÁLIDA: APP_BASE_URL ('{raw_app_base_url}') deve conter um esquema e um domínio válidos (ex: https://dominio.pt)."
        )
    if not DEBUG and parsed_base.scheme != 'https':
        raise ImproperlyConfigured(
            f"SEGURANÇA: Em produção (DEBUG=False), APP_BASE_URL deve utilizar obrigatoriamente o protocolo seguro HTTPS ('{raw_app_base_url}' fornecido)."
        )
    APP_BASE_URL = raw_app_base_url

# CANONICAL_HOST: Mantido temporariamente para retrocompatibilidade, derivado estritamente de APP_BASE_URL
raw_canonical = os.getenv('CANONICAL_HOST', '').strip()
if raw_canonical:
    CANONICAL_HOST = urlparse(raw_canonical if '://' in raw_canonical else f'https://{raw_canonical}').netloc or raw_canonical
else:
    CANONICAL_HOST = urlparse(APP_BASE_URL).netloc or APP_BASE_URL

# Suporte para Reverse Proxy em serviços na nuvem (evita falhas de CSRF / Login em HTTPS)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
TRUST_PROXY_HEADERS = os.getenv('TRUST_PROXY_HEADERS', '').lower() in ('true', '1', 't') or bool(os.getenv('RENDER'))

raw_csrf_origins = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if raw_csrf_origins:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in raw_csrf_origins.split(',') if o.strip()]
else:
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
    'django.contrib.sites',

    # My Apps
    'website',

    # ALLAUTH
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
]

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',    
]

# Google OAuth Provider Config
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()
GOOGLE_OAUTH_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
            'prompt': 'select_account',
        },
        'APP': {
            'client_id': GOOGLE_CLIENT_ID,
            'secret': GOOGLE_CLIENT_SECRET,
            'key': ''
        }
    }
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'website.middleware.TermsAcceptanceMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'website' / 'templates'],
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

# 4. DATABASE FAIL-SAFE CONFIGURATION
database_url = os.getenv('DATABASE_URL')
use_postgres_tests = os.getenv('USE_REAL_POSTGRES_TESTS', 'false').lower() in ('true', '1', 't')

if 'test' in sys.argv and not use_postgres_tests:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
elif not database_url:
    if DEBUG:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
    else:
        raise ImproperlyConfigured("CRÍTICO: A variável de ambiente DATABASE_URL é obrigatória em ambiente de produção (DEBUG=False).")
else:
    DATABASES = {
        'default': dj_database_url.parse(
            database_url,
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

# Django 5.2 STORAGES setting
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# CACHES: LocMemCache em desenvolvimento e testes, persistente/partilhado em produção
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache' if (DEBUG or ('test' in sys.argv)) else 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'vexylo_cache_table',
    }
}

# 5. CONFIGURAÇÃO DE EMAIL FAIL-SAFE
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
    EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False').lower() in ('true', '1', 't')
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
    EMAIL_TIMEOUT = 10
    EMAIL_CONFIGURED = True
else:
    EMAIL_CONFIGURED = False
    if DEBUG or ('test' in sys.argv):
        EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    else:
        disable_email = os.getenv('DISABLE_EMAIL_IN_PROD', 'false').lower() in ('true', '1', 't')
        if not disable_email:
            raise ImproperlyConfigured(
                "CRÍTICO DE PRODUÇÃO: As credenciais de envio de email (EMAIL_HOST_USER e EMAIL_HOST_PASSWORD) "
                "são obrigatórias quando DEBUG=False para assegurar a recuperação de password. "
                "Para desativar explicitamente o envio de email em produção, defina DISABLE_EMAIL_IN_PROD=true."
            )
        EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# 6. ALLAUTH HARDENING
SOCIALACCOUNT_LOGIN_ON_GET = False
ACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_AUTO_SIGNUP = True
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_LOGIN_METHODS = {'email', 'username'}
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False
ACCOUNT_LOGOUT_ON_GET = False

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

JAZZMIN_SETTINGS = {
    "site_title": "VexyloSchedule",
    "site_header": "VexyloSchedule",
    "site_brand": "VexyloSchedule",
    "welcome_sign": "Bem-vindo ao VexyloSchedule",
    "copyright": "VexyloSchedule",
    "show_sidebar": True,
    "navigation_expanded": True,
    
    "topmenu_links": [
        {"name": "Início",  "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Ver Site", "url": "/", "new_window": True},
        {"name": "Nova Marcação", "url": "admin:website_appointment_add", "permissions": ["website.add_appointment"], "icon": "fas fa-calendar-plus"},
        {"name": "Novo Cliente", "url": "admin:website_utilizador_add", "permissions": ["auth.add_user"], "icon": "fas fa-user-plus"},
        {"name": "Nova Categoria", "url": "admin:website_servicecategory_add", "permissions": ["website.add_servicecategory"], "icon": "fas fa-tags"},
    ],

    "hide_models": ["auth.Group"],
    "hide_apps": ["account", "socialaccount", "sites"],
    
    "order_with_respect_to": [
        "website.utilizador",
        "website.appointment",
        "website.businessinfo",
        "website.servicecategory",
        "website.service",
        "website.staffmember",
        "website.testimonial",
    ],

    "icons": {
        "website.utilizador": "fas fa-users-cog",
        "website.appointment": "fas fa-calendar-check",
        "website.service": "fas fa-list",
        "website.servicecategory": "fas fa-tags",
        "website.staffmember": "fas fa-user-tie",
        "website.businessinfo": "fas fa-info-circle",
        "website.testimonial": "fas fa-comment",
        "website.userprofile": "fas fa-id-card",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": False,
    "custom_css": "css/custom_admin.css",
    "custom_js": "js/custom_admin.js",
    "show_ui_builder": False,
}

JAZZMIN_UI_TWEAKS = {
    "theme": "litera",
}

# 7. SEGURANÇA E SSL EM PRODUÇÃO (Render ou not DEBUG)
is_running_tests = 'test' in sys.argv or os.getenv('DJANGO_TEST') == 'true'

if (os.getenv('RENDER') or (not DEBUG and os.getenv('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 't'))) and not is_running_tests:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000 # 1 ano
    SECURE_HSTS_PRELOAD = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
else:
    SECURE_SSL_REDIRECT = False


# 8. LOGGING ESTRUTURADO
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'website': {
            'handlers': ['console'],
            'level': os.getenv('LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}
