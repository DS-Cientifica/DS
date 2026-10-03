import os
import secrets

from django.core.exceptions import ImproperlyConfigured


DEVELOPMENT_SECRET_PREFIX = "django-insecure-axion-ephemeral-development-"
_DEVELOPMENT_SECRET_KEY = DEVELOPMENT_SECRET_PREFIX + secrets.token_urlsafe(50)


def secret_key_from_environment(*, debug, environ=None):
    environ = os.environ if environ is None else environ
    secret_key = (environ.get("DJANGO_SECRET_KEY") or "").strip()
    if secret_key:
        return secret_key
    if debug:
        return _DEVELOPMENT_SECRET_KEY
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY deve ser configurada externamente quando DEBUG=False."
    )


def database_password_from_environment(*, debug, database_url, environ=None):
    environ = os.environ if environ is None else environ
    password = (environ.get("DB_PASSWORD") or "").strip()
    if database_url or password or debug:
        return password
    raise ImproperlyConfigured(
        "DATABASE_URL ou DB_PASSWORD deve ser configurada externamente quando DEBUG=False."
    )
