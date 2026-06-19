from django.apps import AppConfig
from django.db.models.signals import post_migrate

from .admin_bootstrap import ensure_admin_user


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        post_migrate.connect(
            lambda **kwargs: ensure_admin_user(),
            sender=self,
            dispatch_uid="core.ensure_admin_user",
        )
