from dataclasses import dataclass
from datetime import date
import hashlib
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from calibracao.models import CalibracaoColorimetro, CalibracaoTurbidez
from certificados.models import CertificadoCalibracao, RevisaoCertificado
from documentos.models import DocumentoArquivo
from documentos.services.documentos import registrar_documento
from documentos.services.storages import storage_para_backend


DEFAULT_SOURCE = Path(r"C:\Users\User\Desktop")
OBSERVACAO = "Certificado editado para envio."


@dataclass(frozen=True)
class CertificadoImportacao:
    arquivo: str
    numero: str
    modelo: type
    objeto_id: str
    data_calibracao: date
    data_emissao: date
    revisao: int
    sha256: str


CERTIFICADOS = (
    CertificadoImportacao(
        arquivo="EDLAB - 5PFF64DS-.pdf",
        numero="5PFF64DS",
        modelo=CalibracaoColorimetro,
        objeto_id="89c05dba-7edd-4f72-8845-0a03b937a19c",
        data_calibracao=date(2026, 6, 15),
        data_emissao=date(2026, 6, 15),
        revisao=0,
        sha256="6f6f385b50456a232c9a722bc197706e0debfaff60f9b6fc49ef2e3f09d0e3be",
    ),
    CertificadoImportacao(
        arquivo="EDLAB-7Z0KO4DS-.pdf",
        numero="7Z0KO4DS-R01",
        modelo=CalibracaoTurbidez,
        objeto_id="0a902e89-7616-4147-ac7f-b0c2f992de85",
        data_calibracao=date(2026, 6, 12),
        data_emissao=date(2026, 8, 27),
        revisao=1,
        sha256="955f6fb000b8f49fa436591dce4f68ab06e875bb2a14f4373793b3c792ed4fd8",
    ),
    CertificadoImportacao(
        arquivo="EDLAB-X160KDDS.pdf",
        numero="X160KDDS",
        modelo=CalibracaoColorimetro,
        objeto_id="7f4dab50-d16f-4b67-b7e5-019961e9b81f",
        data_calibracao=date(2026, 6, 12),
        data_emissao=date(2026, 6, 15),
        revisao=0,
        sha256="2449d6697a40cf9ccb0f5deecc7d67fe5fd2e008a27ea2e519dbe4e77f101a67",
    ),
)


def calcular_sha256(caminho):
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


class Command(BaseCommand):
    help = "Previsualiza ou importa os tres certificados EDLAB editados para envio."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Confirma a gravacao controlada dos documentos e registros.",
        )

    def handle(self, *args, **options):
        source = options["source"].resolve()
        aplicar = options["apply"]
        preflight = self._preflight(source)

        self.stdout.write(f"Fonte: {source}")
        for item, caminho, calibracao, existente in preflight:
            acao = "EXISTENTE" if existente else ("CRIAR" if aplicar else "CRIARIA")
            self.stdout.write(
                f"{acao:9} {item.numero} | {calibracao.instrumento.codigo} | "
                f"{item.data_calibracao:%d/%m/%Y} | Rev. {item.revisao:02d} | "
                f"sha256={calcular_sha256(caminho)[:12]}"
            )

        pendentes = [linha for linha in preflight if linha[3] is None]
        if not aplicar:
            self.stdout.write(self.style.WARNING(
                f"Previa concluida: {len(pendentes)} certificado(s) seriam criados "
                "como Em revisao, sem publicacao ou download publico."
            ))
            return
        if not pendentes:
            self.stdout.write(self.style.SUCCESS("Nenhuma gravacao pendente."))
            return

        documentos_criados = []
        try:
            with transaction.atomic():
                for item, caminho, calibracao, _ in pendentes:
                    with caminho.open("rb") as arquivo:
                        documento = registrar_documento(
                            File(arquivo, name=caminho.name),
                            tipo_documento="certificado_calibracao_editado_envio",
                            objeto=calibracao,
                            imutavel=True,
                        )
                    documentos_criados.append(documento)
                    content_type = ContentType.objects.get_for_model(
                        calibracao, for_concrete_model=False
                    )
                    certificado = CertificadoCalibracao.objects.create(
                        numero=item.numero,
                        calibracao_content_type=content_type,
                        calibracao_object_id=str(calibracao.pk),
                        instrumento=calibracao.instrumento,
                        cliente=calibracao.cliente,
                        documento=documento,
                        data_calibracao=item.data_calibracao,
                        data_emissao=item.data_emissao,
                        status=CertificadoCalibracao.Status.EM_REVISAO,
                        revisao=item.revisao,
                        motivo_status=OBSERVACAO,
                        publicado=False,
                        permitir_download_publico=False,
                    )
                    RevisaoCertificado.objects.create(
                        certificado=certificado,
                        acao="importado",
                        justificativa=OBSERVACAO,
                    )
        except Exception:
            for documento in documentos_criados:
                try:
                    storage_para_backend(documento.backend_primario).delete(
                        documento.chave_armazenamento
                    )
                except Exception:
                    pass
            raise

        self.stdout.write(self.style.SUCCESS(
            f"Importacao concluida: {len(pendentes)} certificado(s) em revisao."
        ))

    def _preflight(self, source):
        if not source.is_dir():
            raise CommandError(f"Pasta de origem nao localizada: {source}")

        resultado = []
        for item in CERTIFICADOS:
            caminho = source / item.arquivo
            if not caminho.is_file() or caminho.stat().st_size == 0:
                raise CommandError(f"PDF ausente ou vazio: {caminho}")
            hash_atual = calcular_sha256(caminho)
            if hash_atual != item.sha256:
                raise CommandError(
                    f"Conteudo divergente para {item.arquivo}: sha256={hash_atual}"
                )

            try:
                calibracao = item.modelo.objects.select_related(
                    "instrumento", "cliente"
                ).get(pk=item.objeto_id)
            except item.modelo.DoesNotExist as exc:
                raise CommandError(
                    f"Calibracao de origem nao localizada para {item.numero}."
                ) from exc

            divergencias = []
            if calibracao.numero_certificado != item.numero:
                divergencias.append("numero")
            if calibracao.data_calibracao != item.data_calibracao:
                divergencias.append("data de calibracao")
            if calibracao.data_emissao != item.data_emissao:
                divergencias.append("data de emissao")
            if int(calibracao.revisao or 0) != item.revisao:
                divergencias.append("revisao")
            if divergencias:
                raise CommandError(
                    f"Dados divergentes em {item.numero}: {', '.join(divergencias)}."
                )

            content_type = ContentType.objects.get_for_model(
                calibracao, for_concrete_model=False
            )
            existente_objeto = CertificadoCalibracao.objects.filter(
                calibracao_content_type=content_type,
                calibracao_object_id=str(calibracao.pk),
            ).first()
            existente_numero = CertificadoCalibracao.objects.filter(
                numero=item.numero
            ).first()
            if existente_objeto and existente_numero and existente_objeto.pk != existente_numero.pk:
                raise CommandError(
                    f"Conflito: objeto e numero apontam para certificados diferentes ({item.numero})."
                )
            existente = existente_objeto or existente_numero
            if existente:
                if (
                    existente.numero != item.numero
                    or existente.calibracao_content_type_id != content_type.pk
                    or existente.calibracao_object_id != str(calibracao.pk)
                ):
                    raise CommandError(f"Cadastro existente divergente para {item.numero}.")
                if not existente.documento_id or existente.documento.sha256 != item.sha256:
                    raise CommandError(f"Arquivo existente divergente para {item.numero}.")
            elif DocumentoArquivo.objects.filter(sha256=item.sha256).exists():
                raise CommandError(
                    f"O PDF de {item.numero} ja existe no repositorio documental sem este vinculo."
                )

            resultado.append((item, caminho, calibracao, existente))
        return resultado
