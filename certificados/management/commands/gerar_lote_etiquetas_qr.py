from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max

from calibracao.models import (
    HistoricoNumeroCertificado,
    NumeroCertificadoEmitido,
    _candidato_numero_certificado,
    _variantes_numero_certificado,
)
from certificados.models import EtiquetaCalibracaoQR


class Command(BaseCommand):
    help = "Gera, de forma controlada, um lote de etiquetas QR pré-reservadas."

    def add_arguments(self, parser):
        parser.add_argument("--lote", required=True)
        parser.add_argument("--quantidade", required=True, type=int)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Confirma a gravação. Sem esta opção, executa somente a simulação.",
        )

    def handle(self, *args, **options):
        lote = options["lote"].strip()
        quantidade = options["quantidade"]

        if not lote or len(lote) > 50:
            raise CommandError("O lote deve possuir entre 1 e 50 caracteres.")
        if quantidade < 1 or quantidade > 500:
            raise CommandError("A quantidade deve estar entre 1 e 500 etiquetas.")
        existentes = EtiquetaCalibracaoQR.objects.filter(lote=lote)
        if existentes.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Lote {lote} já existe com {existentes.count()} etiqueta(s); nenhuma alteração realizada."
                )
            )
            return

        ultima = EtiquetaCalibracaoQR.objects.aggregate(valor=Max("sequencia"))["valor"] or 0
        primeiro = ultima + 1
        ultimo = ultima + quantidade
        self.stdout.write(
            f"Lote: {lote} | quantidade: {quantidade} | formato: "
            "6 caracteres aleatórios (3 letras e 3 números)"
        )
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("SIMULAÇÃO: use --apply para confirmar."))
            return

        with transaction.atomic():
            bloqueados = set(EtiquetaCalibracaoQR.objects.values_list("codigo", flat=True))
            bloqueados.update(NumeroCertificadoEmitido.objects.values_list("codigo", flat=True))
            for anterior, novo in HistoricoNumeroCertificado.objects.values_list(
                "numero_anterior", "numero_novo"
            ):
                bloqueados.update(_variantes_numero_certificado(anterior))
                bloqueados.update(_variantes_numero_certificado(novo))

            codigos = []
            tentativas = 0
            while len(codigos) < quantidade and tentativas < quantidade * 500:
                tentativas += 1
                candidato = _candidato_numero_certificado()
                variantes = _variantes_numero_certificado(candidato)
                if variantes & bloqueados:
                    continue
                codigos.append(candidato)
                bloqueados.update(variantes)
            if len(codigos) != quantidade:
                raise CommandError("Não foi possível gerar todos os códigos exclusivos do lote.")

            EtiquetaCalibracaoQR.objects.bulk_create(
                [
                    EtiquetaCalibracaoQR(
                        codigo=codigo,
                        lote=lote,
                        sequencia=numero,
                        status=EtiquetaCalibracaoQR.Status.AGUARDANDO_IMPRESSAO,
                    )
                    for numero, codigo in zip(range(primeiro, ultimo + 1), codigos)
                ]
            )
        amostra = ", ".join(codigos[:5])
        self.stdout.write(
            self.style.SUCCESS(
                f"Lote {lote} criado com {quantidade} etiquetas. Amostra: {amostra}."
            )
        )
