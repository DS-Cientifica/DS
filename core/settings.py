from pathlib import Path
import os

import dj_database_url

from .configuration import database_password_from_environment, secret_key_from_environment

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
DEBUG = os.getenv("DEBUG", "False").lower() in ("1", "true", "yes", "on")

SECRET_KEY = secret_key_from_environment(debug=DEBUG)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,.onrender.com").split(",")
    if host.strip()
]

# Quando configurado, este host aceita somente consultas públicas de
# certificados/etiquetas. O restante do AXION retorna 404 nesse domínio.
PUBLIC_CERTIFICATE_HOSTS = [
    host.strip()
    for host in os.getenv("PUBLIC_CERTIFICATE_HOSTS", "").split(",")
    if host.strip()
]
PUBLIC_CERTIFICATE_BASE_URL = os.getenv("PUBLIC_CERTIFICATE_BASE_URL", "").strip().rstrip("/")

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "https://*.onrender.com").split(",")
    if origin.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv(
    "SECURE_SSL_REDIRECT", "0" if DEBUG else "1"
).lower() in ("1", "true", "yes", "on")
SESSION_COOKIE_SECURE = os.getenv(
    "SESSION_COOKIE_SECURE", "0" if DEBUG else "1"
).lower() in ("1", "true", "yes", "on")
CSRF_COOKIE_SECURE = os.getenv(
    "CSRF_COOKIE_SECURE", "0" if DEBUG else "1"
).lower() in ("1", "true", "yes", "on")
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", "0"
).lower() in ("1", "true", "yes", "on")
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "0").lower() in (
    "1", "true", "yes", "on"
)


# ========================
# APPLICATIONS
# ========================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_extensions",
    "storages",
    "clientes",
    "calibracao",
    "manutencao.apps.ManutencaoConfig",
    "comercial",
    "financeiro",
    "qualidade",
    "planejamento.apps.PlanejamentoConfig",
    "gestao.apps.GestaoConfig",
    "projetos.apps.ProjetosConfig",
    "documentos.apps.DocumentosConfig",
    "certificados.apps.CertificadosConfig",
    "core.apps.CoreConfig",
]


# ========================
# MIDDLEWARE
# ========================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.public_certificate_middleware.PublicCertificateHostMiddleware",
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
# A aplicação core também fornece as tags de navegação compartilhadas do Admin.
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
DB_PASSWORD = database_password_from_environment(
    debug=DEBUG,
    database_url=DATABASE_URL,
)

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
            "PASSWORD": DB_PASSWORD,
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


# ========================
# CLOUD/R2 STORAGE
# ========================
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "auto")
AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_S3_CUSTOM_DOMAIN")

USE_CLOUD_MEDIA = all(
    [
        AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY,
        AWS_STORAGE_BUCKET_NAME,
        AWS_S3_ENDPOINT_URL,
    ]
)

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}


# ========================
# MEDIA FILES
# ========================
if USE_CLOUD_MEDIA:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "endpoint_url": AWS_S3_ENDPOINT_URL,
            "region_name": AWS_S3_REGION_NAME,
            "default_acl": None,
            "querystring_auth": False,
            "file_overwrite": False,
        },
    }
    if AWS_S3_CUSTOM_DOMAIN:
        MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"
    else:
        MEDIA_URL = f"{AWS_S3_ENDPOINT_URL.rstrip('/')}/{AWS_STORAGE_BUCKET_NAME}/"
    MEDIA_ROOT = BASE_DIR / "media"

# Documentos controlados: armazenamento local privado como padrão e R2 opcional.
else:
    STORAGES["default"] = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

DOCUMENT_STORAGE_MODE = os.getenv("DOCUMENT_STORAGE_MODE", "local").strip().lower()
DOCUMENT_LOCAL_ROOT = Path(os.getenv("DOCUMENT_LOCAL_ROOT", BASE_DIR / "private_documents"))
DOCUMENT_R2_ENABLED = os.getenv(
    "DOCUMENT_R2_ENABLED", "1" if USE_CLOUD_MEDIA else "0"
).strip().lower() in {"1", "true", "yes", "on"}
DOCUMENT_R2_BUCKET = AWS_STORAGE_BUCKET_NAME
DOCUMENT_R2_ENDPOINT_URL = AWS_S3_ENDPOINT_URL
DOCUMENT_R2_ACCESS_KEY_ID = AWS_ACCESS_KEY_ID
DOCUMENT_R2_SECRET_ACCESS_KEY = AWS_SECRET_ACCESS_KEY
DOCUMENT_R2_REGION = AWS_S3_REGION_NAME
DOCUMENT_R2_PRESIGNED_URL_TTL = int(os.getenv("DOCUMENT_R2_PRESIGNED_URL_TTL", "600"))


# ========================
# DJANGO DEFAULTS
# ========================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ========================
# EMAIL
# ========================
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("1", "true", "yes", "on")
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in ("1", "true", "yes", "on")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "contato@dscientifica.com.br")

WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "")

LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/admin/login/"

ADMIN_SITE_HEADER = "DS Científica"
ADMIN_SITE_TITLE = "Sistema DS Científica"
ADMIN_INDEX_TITLE = "Gestão de Calibração"
