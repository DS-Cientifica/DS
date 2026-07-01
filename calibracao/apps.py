from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.http import JsonResponse


class CalibracaoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "calibracao"
    verbose_name = "Gestão Metrológica"

    def ready(self):
        from django.contrib.auth.models import Group, Permission
        from .admin import InstrumentoAdmin
        from .models import Instrumento

        from .access_groups import apply_default_access_groups

        def ensure_default_groups(**kwargs):
            apply_default_access_groups(Group, Permission)

        post_migrate.connect(
            ensure_default_groups,
            sender=self,
            dispatch_uid="calibracao.ensure_default_access_groups",
        )

        def check_duplicate_view_por_cliente_tag(self, request):
            cliente_id = request.GET.get("cliente_id")
            tag = (request.GET.get("tag") or "").strip()
            object_id = request.GET.get("object_id")

            if not cliente_id or not tag:
                return JsonResponse({"duplicate": False})

            duplicado = Instrumento.objects.filter(
                cliente_id=cliente_id,
                tag__iexact=tag,
            )
            if object_id:
                duplicado = duplicado.exclude(pk=object_id)

            if duplicado.exists():
                return JsonResponse(
                    {
                        "duplicate": True,
                        "message": "Já existe instrumento cadastrado para este cliente com a mesma TAG.",
                    }
                )

            return JsonResponse({"duplicate": False})

        InstrumentoAdmin.check_duplicate_view = check_duplicate_view_por_cliente_tag
