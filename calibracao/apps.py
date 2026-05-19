from django.apps import AppConfig


class CalibracaoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "calibracao"
    verbose_name = "Gestão Metrológica"

    def ready(self):
        # Importações futuras:
        # from . import signals
        pass

