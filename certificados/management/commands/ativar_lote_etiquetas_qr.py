from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from certificados.models import EtiquetaCalibracaoQR


class Command(BaseCommand):
    help = "Ativa um lote de etiquetas somente depois da conferência da impressão física."

    def add_arguments(self, parser):
        parser.add_argument("--lote", required=True)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Confirma a ativação. Sem esta opção, executa somente a simulação.",
        )

    def handle(self, *args, **options):
        lote = options["lote"].strip()
        if not lote:
            raise CommandError("Informe o lote.")
        queryset = EtiquetaCalibracaoQR.objects.filter(lote=lote)
        total = queryset.count()
        if not total:
            raise CommandError(f"Lote {lote} não localizado.")
        aguardando = queryset.filter(
            status=EtiquetaCalibracaoQR.Status.AGUARDANDO_IMPRESSAO
        ).count()
        outros = total - aguardando
        self.stdout.write(
            f"Lote: {lote} | total: {total} | aguardando impressão: {aguardando} | outros status: {outros}"
        )
        if outros:
            raise CommandError(
                "O lote possui etiquetas fora do estado aguardando impressão; ativação bloqueada."
            )
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("SIMULAÇÃO: use --apply para confirmar."))
            return
        with transaction.atomic():
            atualizadas = (
                EtiquetaCalibracaoQR.objects.select_for_update()
                .filter(
                    lote=lote,
                    status=EtiquetaCalibracaoQR.Status.AGUARDANDO_IMPRESSAO,
                )
                .update(status=EtiquetaCalibracaoQR.Status.DISPONIVEL)
            )
        self.stdout.write(
            self.style.SUCCESS(f"Lote {lote} ativado com {atualizadas} etiquetas disponíveis.")
        )
