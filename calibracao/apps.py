from django.apps import AppConfig
from django.db.models.signals import post_migrate, pre_save
from django.http import JsonResponse


class CalibracaoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "calibracao"
    verbose_name = "Gestão Metrológica"

    def ready(self):
        from django.contrib.auth.models import Group, Permission
        from .admin import InstrumentoAdmin
        from .models import Instrumento
        from .balance_models import CalibracaoBalanca
        from .models import (
            Calibracao,
            CalibracaoColorimetro,
            CalibracaoCondutividade,
            CalibracaoPressao,
            CalibracaoTurbidez,
        )
        from .ph_models import CalibracaoPH
        from .safety_models import CalibracaoDispositivoSegurancaPressao
        from .sphyg_models import CalibracaoEsfigmomanometro
        from .services.ordem_servico import preencher_ordem_servico_da_calibracao

        from .access_groups import apply_default_access_groups

        def ensure_default_groups(**kwargs):
            apply_default_access_groups(Group, Permission)

        post_migrate.connect(
            ensure_default_groups,
            sender=self,
            dispatch_uid="calibracao.ensure_default_access_groups",
        )
        # As permissões de documentos/certificados ainda não existem quando o
        # post_migrate de calibracao é emitido em uma instalação nova.
        from django.apps import apps

        post_migrate.connect(
            ensure_default_groups,
            sender=apps.get_app_config("certificados"),
            dispatch_uid="calibracao.ensure_default_access_groups_after_certificados",
        )
        post_migrate.connect(
            ensure_default_groups,
            sender=apps.get_app_config("qualidade"),
            dispatch_uid="calibracao.ensure_default_access_groups_after_qualidade",
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

        modelos_com_ordem_servico = (
            Calibracao,
            CalibracaoTurbidez,
            CalibracaoColorimetro,
            CalibracaoPressao,
            CalibracaoCondutividade,
            CalibracaoPH,
            CalibracaoBalanca,
            CalibracaoDispositivoSegurancaPressao,
            CalibracaoEsfigmomanometro,
        )
        for modelo in modelos_com_ordem_servico:
            pre_save.connect(
                preencher_ordem_servico_da_calibracao,
                sender=modelo,
                dispatch_uid=f"calibracao.preencher_ordem_servico.{modelo._meta.label_lower}",
            )
