from django.core.management.base import BaseCommand
from django.utils import timezone

from projetos.marketing import processar_envio_campanha
from projetos.models import EnvioCampanha


class Command(BaseCommand):
    help = "Processa a caixa de saída de campanhas de marketing autorizadas."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=100)
        parser.add_argument(
            "--reprocessar-falhas",
            action="store_true",
            help="Inclui envios que falharam em execução anterior.",
        )

    def handle(self, *args, **options):
        statuses = ["pendente"]
        if options["reprocessar_falhas"]:
            statuses.append("falha")
        envios = list(
            EnvioCampanha.objects.filter(
                status__in=statuses,
                agendado_para__lte=timezone.now(),
            )
            .order_by("agendado_para", "created_at")
            .values_list("pk", flat=True)[: max(options["limite"], 0)]
        )
        totais = {}
        for envio_id in envios:
            resultado = processar_envio_campanha(envio_id)
            totais[resultado] = totais.get(resultado, 0) + 1
        resumo = ", ".join(f"{status}: {quantidade}" for status, quantidade in sorted(totais.items()))
        self.stdout.write(self.style.SUCCESS(resumo or "Nenhum envio pendente para processar."))
