from pathlib import Path
import os
import dj_database_url

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ========================
# BASE
# ========================
BASE_DIR = Path(__file__).resolve().parent.parent

# ========================
# SECURITY
# ========================
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-key"
)

DEBUG = os.getenv("DEBUG", "False").lower() in ("1", "true", "yes", "on")


ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,.onrender.com").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "https://*.onrender.com").split(",")
    if origin.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ========================
# APPLICATIONS
# ========================
INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_extensions",

    "clientes",
    "calibracao",
    "comercial",
    "financeiro",
    'qualidade',
]

# ========================
# MIDDLEWARE
# ========================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

# ========================
# TEMPLATES
# ========================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "core/templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# ========================
# DATABASE
# ========================

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            conn_max_age=600,
            ssl_require=not DEBUG,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "axion_db"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", "DSc@1301"),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }
# ========================
# PASSWORD VALIDATION
# ========================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ========================
# INTERNATIONALIZATION
# ========================
LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True
USE_TZ = True

# ========================
# STATIC FILES
# ========================
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# ========================
# MEDIA FILES
# ========================
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ========================
# DJANGO DEFAULTS
# ========================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/admin/login/"

# ========================
# JAZZMIN SETTINGS
# ========================
JAZZMIN_SETTINGS = {
    "site_title": "AXION",
    "site_header": "AXION",
    "site_brand": "AXION",

    "welcome_sign": "AXION — A Gestão Estratégica da Sua Empresa",
    "copyright": "AXION",

    # Logos
    "site_logo": "img/logo_ds.png",
    "login_logo": "img/capa_ds.png",
    "site_logo_classes": "img-circle elevation-3",

    # UI
    "use_google_fonts_cdn": True,
    "show_ui_builder": True,
    "navigation_expanded": True,

    # Busca global
    "search_model": [
        "auth.User",
        "clientes.Cliente",
        "calibracao.Instrumento",
        "calibracao.OrdemServico",
        "comercial.Proposta",
    ],

    # Ícones
    "icons": {
        "clientes.Cliente": "fas fa-users",
        "clientes.ContatoCliente": "fas fa-id-card",

        "calibracao.Instrumento": "fas fa-tools",
        "calibracao.OrdemServico": "fas fa-clipboard-list",
        "calibracao.Padrao": "fas fa-ruler-combined",
        "calibracao.Documento": "fas fa-file-alt",

        "comercial.Proposta": "fas fa-file-signature",

        "financeiro.ContaReceber": "fas fa-hand-holding-usd",
        "financeiro.ContaPagar": "fas fa-file-invoice-dollar",
        "financeiro.Imposto": "fas fa-percentage",
    },

    # Menu superior
    "topmenu_links": [
        {"name": "Início", "url": "admin:index"},
        {"model": "clientes.Cliente"},
        {"model": "calibracao.Instrumento"},
        {"model": "comercial.Proposta"},
        {"model": "financeiro.ContaReceber"},
    ],
}

# ========================
# JAZZMIN UI TWEAKS
# ========================
JAZZMIN_UI_TWEAKS = {
    "brand_colour": "navbar-navy",
    "accent": "accent-primary",

    "navbar": "navbar-white navbar-light",
    "navbar_fixed": True,

    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-navy",

    "theme": "default",
}

ADMIN_SITE_HEADER = "DS Científica"
ADMIN_SITE_TITLE = "Sistema DS"
ADMIN_INDEX_TITLE = "Gestão de Calibração"
