from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CalibracaoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "calibracao"
    verbose_name = "Gestão Metrológica"

    def ready(self):
        from django.contrib.auth.models import Group, Permission

        from .access_groups import apply_default_access_groups

        def ensure_default_groups(**kwargs):
            apply_default_access_groups(Group, Permission)

        post_migrate.connect(
            ensure_default_groups,
            sender=self,
            dispatch_uid="calibracao.ensure_default_access_groups",
        )
