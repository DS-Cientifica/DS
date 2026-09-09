import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

from clientes.models import Cliente
from comercial.models import Prospecto, ProspeccaoComercial
from financeiro.models import PedidoCompra


class Command(BaseCommand):
    help = "Remove clientes inativos já preservados na Base de prospects."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--backup", type=Path)

    def handle(self, *args, **options):
        clientes = list(Cliente.objects.filter(ativo=False).order_by("codigo"))
        plano = []
        for cliente in clientes:
            marcador = f"Cliente AXION inativo: {cliente.pk} ({cliente.codigo})"
            prospects = list(Prospecto.objects.filter(observacoes__contains=marcador))
            if len(prospects) != 1:
                raise CommandError(
                    f"O cliente {cliente.codigo} possui {len(prospects)} vínculos na Base de prospects; esperado: 1."
                )
            pedidos = list(cliente.pedidos_compra.all())
            incompletos = [
                pedido.numero_pedido for pedido in pedidos
                if not pedido.fornecedor_razao_social_snapshot or not pedido.fornecedor_cnpj_snapshot
            ]
            if incompletos:
                raise CommandError(
                    f"Pedidos sem snapshot completo para {cliente.codigo}: {', '.join(incompletos)}"
                )
            prospeccoes = list(cliente.prospeccaocomercial_set.all())
            plano.append((cliente, prospects[0], pedidos, prospeccoes))

        resumo = {
            "clientes_a_remover": len(plano),
            "prospects_preservados": len(plano),
            "contatos_em_cascata": sum(cliente.contatos.count() for cliente, *_ in plano),
            "pedidos_compra_preservados": sum(len(item[2]) for item in plano),
            "historicos_prospeccao_a_religar": sum(len(item[3]) for item in plano),
            "clientes_ativos_preservados": Cliente.objects.filter(ativo=True).count(),
            "modo": "aplicacao" if options["apply"] else "pre_validacao",
        }
        self.stdout.write(json.dumps(resumo, ensure_ascii=False, indent=2))
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Prévia concluída; nenhum cliente foi removido."))
            return
        if not options["backup"]:
            raise CommandError("Informe --backup para permitir a exclusão recuperável.")

        backup = options["backup"].expanduser().resolve()
        if backup.exists():
            raise CommandError(f"O arquivo de backup já existe: {backup}")
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(
            json.dumps(self._backup(plano), ensure_ascii=False, indent=2, cls=DjangoJSONEncoder),
            encoding="utf-8",
        )

        with transaction.atomic():
            for cliente, prospecto, _, prospeccoes in plano:
                for prospeccao in prospeccoes:
                    if prospeccao.prospecto_id and prospeccao.prospecto_id != prospecto.pk:
                        raise CommandError(
                            f"Histórico {prospeccao.pk} aponta para outro prospect."
                        )
                    prospeccao.prospecto = prospecto
                    prospeccao.save(update_fields=("prospecto",))
            Cliente.objects.filter(pk__in=[item[0].pk for item in plano]).delete()

        self.stdout.write(self.style.SUCCESS(f"{len(plano)} clientes inativos removidos. Backup: {backup}"))

    def _backup(self, plano):
        def dados_modelo(objeto):
            dados = {}
            for field in objeto._meta.concrete_fields:
                valor = getattr(objeto, field.attname)
                if hasattr(valor, "name"):
                    valor = valor.name
                dados[field.name] = valor
            return dados

        return {
            "clientes": [dados_modelo(item[0]) for item in plano],
            "contatos": [dados_modelo(contato) for item in plano for contato in item[0].contatos.all()],
            "vinculos_prospectos": [
                {"cliente_id": item[0].pk, "cliente_codigo": item[0].codigo, "prospecto_id": item[1].pk, "prospecto_codigo": item[1].codigo}
                for item in plano
            ],
            "pedidos_compra": [dados_modelo(pedido) for item in plano for pedido in item[2]],
            "prospeccoes_comerciais": [dados_modelo(registro) for item in plano for registro in item[3]],
        }
