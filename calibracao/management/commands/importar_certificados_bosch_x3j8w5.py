from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
from pathlib import Path

from dateutil.relativedelta import relativedelta
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from calibracao.models import (
    Calibracao,
    Instrumento,
    InstrumentoTecnico,
    Padrao,
    Periodicidade,
)


DEFAULT_SOURCE = Path(
    r"C:\Users\User\Desktop\BBOSCH-DSC- X3J8W5-20072026\ENVIADO"
)


@dataclass(frozen=True)
class CertificadoImportacao:
    sequencia: int
    arquivo: str
    instrumento: str
    data_calibracao: date
    temperatura_inicial: Decimal | None
    temperatura_final: Decimal | None
    umidade_inicial: Decimal | None
    umidade_final: Decimal | None
    padroes: tuple[str, ...]
    metodo: str
    unidade: str
    faixa_calibracao: str
    faixa_indicacao: str
    resolucao: Decimal | None

    @property
    def numero(self):
        return f"DSC-X3J8W5-{self.sequencia:02d}"

    @property
    def validade(self):
        return self.data_calibracao + relativedelta(years=1)


def _d(valor):
    return Decimal(str(valor))


PRESSAO = ("DSP-010", "DSP-022")
ESPESSURA = ("DSP-009", "DSP-022")
ESPESSURA_NOMINAL = ("DSP-019", "DSP-022")
TEMPERATURA = ("DSP-017", "DSP-022")
PH = ("DSP-012", "DSP-013", "DSP-014", "DSP-015", "DSP-016", "DSP-022")
BALANCA = ("DSP-002", "DSP-022")


CERTIFICADOS = (
    CertificadoImportacao(1, "BBOSCH - DSC-X3J8W5-01-20072026.pdf", "BBGB-182", date(2026, 7, 20), None, None, None, None, ("DSP-010",), "Ensaio e ajuste conforme ASME Seção VIII, ASME PTC 25 e NR-13", "kgf/cm²", "Pressão de ajuste: 9,00 kgf/cm²", "Pressão requerida: 9,03 kgf/cm²", None),
    CertificadoImportacao(2, "BBOSCH - DSC-X3J8W5-02-20072026.pdf", "BBGB-181", date(2026, 7, 20), None, None, None, None, ("DSP-010",), "Ensaio e ajuste conforme ASME Seção VIII, ASME PTC 25 e NR-13", "kgf/cm²", "Pressão de ajuste: 9,00 kgf/cm²", "Pressão requerida: 9,03 kgf/cm²", None),
    CertificadoImportacao(3, "BBOSCH - DSC-X3J8W5-03-20072026.pdf", "BBGB-193", date(2026, 7, 20), _d("22.9"), _d("23"), _d("53"), _d("54"), PRESSAO, "MDS-018 Revisão 00", "kgf/cm²", "0 a 14 kgf/cm²", "0 a 14 kgf/cm²", _d("0.2")),
    CertificadoImportacao(4, "BBOSCH - DSC-X3J8W5-04-20072026.pdf", "BBGB-076", date(2026, 7, 20), _d("23"), _d("23"), _d("55"), _d("50"), ESPESSURA, "MDS-011 Revisão 00", "µm", "0 a 1000 µm", "0 a 1500 µm", _d("0.1")),
    CertificadoImportacao(5, "BBOSCH - DSC-X3J8W5-05-20072026.pdf", "BBGB-077", date(2026, 7, 20), _d("23"), _d("23"), _d("55"), _d("50"), ESPESSURA, "MDS-011 Revisão 00", "µm", "0 a 1000 µm", "0 a 1500 µm", _d("0.1")),
    CertificadoImportacao(6, "BBOSCH - DSC-X3J8W5-06-20072026.pdf", "BBGB-083", date(2026, 7, 20), _d("23"), _d("23"), _d("55"), _d("50"), ESPESSURA, "MDS-011 Revisão 00", "µm", "0 a 1000 µm", "0 a 1500 µm", _d("0.1")),
    CertificadoImportacao(7, "BBOSCH - DSC-X3J8W5-07-20072026.pdf", "BBGB-062", date(2026, 7, 20), _d("23"), _d("23"), _d("55"), _d("50"), ESPESSURA_NOMINAL, "MDS-024 Revisão 00", "µm", "50 µm", "50 µm", _d("1")),
    CertificadoImportacao(8, "BBOSCH - DSC-X3J8W5-08-20072026.pdf", "BBGB-070", date(2026, 7, 20), _d("23"), _d("23"), _d("55"), _d("50"), ESPESSURA_NOMINAL, "MDS-024 Revisão 00", "µm", "345 µm", "345 µm", _d("1")),
    CertificadoImportacao(9, "BBOSCH - DSC-X3J8W5-09-20072026.pdf", "BBGB-019", date(2026, 7, 20), _d("23"), _d("23"), _d("55"), _d("50"), ESPESSURA_NOMINAL, "MDS-024 Revisão 00", "µm", "340 µm", "340 µm", _d("1")),
    CertificadoImportacao(10, "BBOSCH - DSC-X3J8W5-10-20072026.pdf", "BBGB-018", date(2026, 7, 20), _d("23"), _d("23"), _d("55"), _d("50"), ESPESSURA_NOMINAL, "MDS-024 Revisão 00", "µm", "300 µm", "300 µm", _d("1")),
    CertificadoImportacao(11, "BBOSCH - DSC-X3J8W5-11-20072026.pdf", "BBGB-014", date(2026, 7, 20), _d("23"), _d("23"), _d("55"), _d("50"), ESPESSURA_NOMINAL, "MDS-024 Revisão 00", "µm", "118 µm", "118 µm", _d("1")),
    CertificadoImportacao(12, "BBOSCH - DSC-X3J8W5-12-20072026.pdf", "BBGB-058", date(2026, 7, 20), _d("23"), _d("23"), _d("55"), _d("50"), ESPESSURA, "MDS-011 Revisão 00", "µm", "0 a 1000 µm", "0 a 1300 µm", _d("0.1")),
    CertificadoImportacao(13, "BBOSCH - DSC-X3J8W5-13-20072026.pdf", "BBGB-187", date(2026, 7, 20), _d("22.9"), _d("23"), _d("53"), _d("54"), PRESSAO, "MDS-018 Revisão 00", "mbar", "0 a 160 mbar", "0 a 160 mbar", _d("5")),
    CertificadoImportacao(14, "BBOSCH - DSC-X3J8W5-14-20072026.pdf", "BBGB-192", date(2026, 7, 20), _d("22.9"), _d("23"), _d("53"), _d("54"), PRESSAO, "MDS-018 Revisão 00", "mbar", "0 a 160 mbar", "0 a 160 mbar", _d("5")),
    CertificadoImportacao(15, "BBOSCH - DSC-X3J8W5-15-20072026.pdf", "BBGB-185", date(2026, 7, 20), _d("22.9"), _d("23"), _d("53"), _d("54"), PRESSAO, "MDS-018 Revisão 00", "mbar", "0 a 400 mbar", "0 a 400 mbar", _d("10")),
    CertificadoImportacao(16, "BBOSCH - DSC-X3J8W5-16-20072026.pdf", "BBGB-186", date(2026, 7, 20), _d("22.9"), _d("23"), _d("53"), _d("54"), PRESSAO, "MDS-018 Revisão 00", "mbar", "0 a 250 mbar", "0 a 250 mbar", _d("10")),
    CertificadoImportacao(17, "BBOSCH - DSC-X3J8W5-17-20072026.pdf", "BBGB-264", date(2026, 7, 20), _d("22.9"), _d("23"), _d("53"), _d("54"), PRESSAO, "MDS-018 Revisão 00", "mbar", "0 a 250 mbar", "0 a 250 mbar", _d("2")),
    CertificadoImportacao(18, "BBOSCH - DSC-X3J8W5-18-20072026.pdf", "BBGB-271", date(2026, 7, 20), _d("22.9"), _d("23"), _d("53"), _d("54"), PRESSAO, "MDS-018 Revisão 00", "kgf/cm²", "0 a 7 kgf/cm²", "0 a 7 kgf/cm²", _d("0.1")),
    CertificadoImportacao(19, "BBOSCH - DSC-X3J8W5-19-20072026.pdf", "BBGB-273", date(2026, 7, 20), _d("22.9"), _d("23"), _d("53"), _d("54"), PRESSAO, "MDS-018 Revisão 00", "kgf/cm²", "0 a 7 kgf/cm²", "0 a 7 kgf/cm²", _d("0.1")),
    CertificadoImportacao(20, "BBOSCH - DSC-X3J8W5-20-20072026.pdf", "BBGB-004", date(2026, 7, 20), _d("23"), _d("23"), _d("55"), _d("50"), TEMPERATURA, "MDS-004 Revisão 00", "°C", "0 a 500 °C", "0 a 500 °C", _d("1")),
    CertificadoImportacao(21, "BBOSCH - DSC-X3J8W5-21-20072026.pdf", "BBGB-003", date(2026, 7, 20), _d("23"), _d("23"), _d("55"), _d("50"), TEMPERATURA, "MDS-004 Revisão 00", "°C", "0 a 500 °C", "0 a 500 °C", _d("1")),
    CertificadoImportacao(22, "BBOSCH - DSC-X3J8W5-22-20072026.pdf", "BBGB-008", date(2026, 7, 20), _d("23"), _d("23"), _d("55"), _d("50"), PH, "MDS-020 Revisão 00", "pH", "0 a 14 pH", "0 a 14 pH", _d("0.01")),
    CertificadoImportacao(23, "BBOSCH - DSC-X3J8W5-23-24072026.pdf", "BBGB-006", date(2026, 7, 24), _d("23"), _d("23"), _d("55"), _d("55"), BALANCA, "MDS-025 Revisão 00", "g", "0,5 a 5000 g", "0,5 a 5000 g", _d("0.01")),
    CertificadoImportacao(24, "BBOSCH - DSC-X3J8W5-24-20072026.pdf", "BBGB-074", date(2026, 7, 24), _d("23"), _d("23"), _d("55"), _d("55"), BALANCA, "MDS-025 Revisão 00", "g", "0,5 a 510 g", "0,5 a 510 g", _d("0.01")),
    CertificadoImportacao(25, "BBOSCH - DSC-X3J8W5-25-20072026.pdf", "BBGB-085", date(2026, 7, 24), _d("23"), _d("23"), _d("55"), _d("50"), TEMPERATURA, "MDS-004 Revisão 00", "°C", "-10 a 500 °C", "-60 a 1372 °C", _d("0.1")),
    CertificadoImportacao(26, "BBOSCH - DSC-X3J8W5-26-20072026.pdf", "BBGB-251", date(2026, 7, 24), _d("22.9"), _d("23"), _d("53"), _d("54"), PRESSAO, "MDS-012 Revisão 00", "mmHg", "0 a 300 mmHg", "0 a 300 mmHg", _d("1")),
    CertificadoImportacao(27, "BBOSCH - DSC-X3J8W5-27-20072026.pdf", "BBGB-250", date(2026, 7, 24), _d("22.9"), _d("23"), _d("53"), _d("54"), PRESSAO, "MDS-012 Revisão 00", "mmHg", "30 a 280 mmHg", "30 a 280 mmHg", _d("1")),
    CertificadoImportacao(28, "BBOSCH - DSC-X3J8W5-28-20072026.pdf", "BBGB-291", date(2026, 7, 6), _d("23"), _d("23"), _d("55"), _d("50"), PH, "MDS-020 Revisão 00", "pH", "0 a 14 pH", "0 a 14 pH", _d("0.01")),
)


def _sha256(caminho):
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _observacoes(item):
    linhas = [
        "Resultado aprovado conforme critério do cliente, conforme solicitação de cadastro.",
        f"Unidade de medição conforme certificado: {item.unidade}.",
        f"Faixa de indicação: {item.faixa_indicacao}.",
        f"Faixa de calibração: {item.faixa_calibracao}.",
    ]
    if item.temperatura_inicial is None:
        linhas.append("Condições ambientais não declaradas no certificado de ensaio e ajuste.")
    else:
        linhas.append(
            "Condições ambientais do certificado: "
            f"temperatura inicial {item.temperatura_inicial} °C e final {item.temperatura_final} °C; "
            f"umidade inicial {item.umidade_inicial} %ur e final {item.umidade_final} %ur."
        )
    return "\n".join(linhas)


class Command(BaseCommand):
    help = "Pré-visualiza ou importa de forma controlada os 28 certificados Bosch DSC-X3J8W5."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
        parser.add_argument("--apply", action="store_true", help="Confirma as gravações no banco e no storage.")

    def handle(self, *args, **options):
        source = options["source"].resolve()
        aplicar = options["apply"]
        preflight = self._preflight(source)

        self.stdout.write(f"Fonte: {source}")
        self.stdout.write(f"Arquivos validados: {len(preflight)}")
        for item, caminho, existente in preflight:
            acao = "EXISTENTE" if existente else ("CRIAR" if aplicar else "CRIARIA")
            self.stdout.write(
                f"{acao:9} {item.numero} | {item.instrumento} | "
                f"{item.data_calibracao:%d/%m/%Y} -> {item.validade:%d/%m/%Y} | "
                f"{','.join(item.padroes)} | sha256={_sha256(caminho)[:12]}"
            )

        pendentes = [(item, caminho) for item, caminho, existente in preflight if not existente]
        if not aplicar:
            self.stdout.write(self.style.WARNING(
                f"Prévia concluída: {len(pendentes)} certificado(s) seriam criados. Use --apply para confirmar."
            ))
            return

        if not pendentes:
            self.stdout.write(self.style.SUCCESS("Nenhuma gravação pendente; os 28 certificados já existem."))
            return

        arquivos_gravados = []
        try:
            with transaction.atomic():
                for item, caminho in pendentes:
                    instrumento = Instrumento.objects.select_for_update().get(codigo=item.instrumento)
                    Periodicidade.objects.update_or_create(
                        instrumento=instrumento,
                        tipo="calibracao",
                        defaults={"intervalo_meses": 12},
                    )
                    self._atualizar_dados_tecnicos(instrumento, item)
                    instrumento.padroes.add(*Padrao.objects.filter(codigo__in=item.padroes))

                    calibracao = Calibracao(
                        instrumento=instrumento,
                        data_calibracao=item.data_calibracao,
                        validade=item.validade,
                        status="concluida",
                        resultado="aprovado",
                        certificado_numero=item.numero,
                        empresa_emissora="DS Científica",
                        metodo=item.metodo,
                        padroes=", ".join(item.padroes),
                        temperatura=item.temperatura_inicial,
                        umidade=item.umidade_inicial,
                        local_calibracao="in_loco",
                        observacoes=_observacoes(item),
                    )
                    with caminho.open("rb") as arquivo:
                        calibracao.certificado_arquivo.save(caminho.name, File(arquivo), save=False)
                    arquivos_gravados.append(calibracao.certificado_arquivo.name)
                    calibracao.full_clean()
                    calibracao.save()
                    if calibracao.certificado_numero != item.numero or calibracao.validade != item.validade:
                        raise CommandError(f"Divergência após salvar {item.numero}.")

                    instrumento.proxima_calibracao = item.validade
                    instrumento.save(update_fields=("proxima_calibracao", "updated_at"))
        except Exception:
            storage = Calibracao._meta.get_field("certificado_arquivo").storage
            for nome in arquivos_gravados:
                try:
                    storage.delete(nome)
                except Exception:
                    pass
            raise

        self.stdout.write(self.style.SUCCESS(f"Importação concluída: {len(pendentes)} certificados criados."))

    def _preflight(self, source):
        if not source.is_dir():
            raise CommandError(f"Pasta de origem não localizada: {source}")

        esperados = {item.arquivo for item in CERTIFICADOS}
        encontrados = {caminho.name for caminho in source.glob("*.pdf")}
        faltantes = sorted(esperados - encontrados)
        extras = sorted(encontrados - esperados)
        if faltantes or extras:
            raise CommandError(
                f"Conjunto de PDFs divergente. Faltantes={faltantes or '-'}; extras={extras or '-'}"
            )

        codigos_instrumentos = {item.instrumento for item in CERTIFICADOS}
        instrumentos = {
            instrumento.codigo: instrumento
            for instrumento in Instrumento.objects.select_related("cliente").filter(codigo__in=codigos_instrumentos)
        }
        ausentes = sorted(codigos_instrumentos - instrumentos.keys())
        if ausentes:
            raise CommandError("Instrumentos não localizados: " + ", ".join(ausentes))
        incorretos = [
            codigo for codigo, instrumento in instrumentos.items()
            if "BOSCH" not in f"{instrumento.cliente.razao_social} {instrumento.cliente.nome_empresa}".upper()
        ]
        if incorretos:
            raise CommandError("Instrumentos fora do cliente Bosch: " + ", ".join(sorted(incorretos)))

        codigos_padroes = {codigo for item in CERTIFICADOS for codigo in item.padroes}
        padroes_existentes = set(
            Padrao.objects.filter(codigo__in=codigos_padroes).values_list("codigo", flat=True)
        )
        if codigos_padroes != padroes_existentes:
            raise CommandError(
                "Padrões não localizados: " + ", ".join(sorted(codigos_padroes - padroes_existentes))
            )

        resultado = []
        for item in CERTIFICADOS:
            caminho = source / item.arquivo
            if caminho.stat().st_size <= 0:
                raise CommandError(f"Arquivo vazio: {caminho.name}")
            por_numero = Calibracao.objects.filter(certificado_numero=item.numero).first()
            por_instrumento_data = Calibracao.objects.filter(
                instrumento__codigo=item.instrumento,
                data_calibracao=item.data_calibracao,
            ).first()
            existente = por_numero or por_instrumento_data
            if existente and not (
                existente.certificado_numero == item.numero
                and existente.instrumento.codigo == item.instrumento
                and existente.data_calibracao == item.data_calibracao
                and existente.validade == item.validade
                and existente.resultado == "aprovado"
                and existente.local_calibracao == "in_loco"
                and existente.certificado_arquivo
            ):
                raise CommandError(
                    f"Conflito com cadastro existente para {item.numero}/{item.instrumento}/{item.data_calibracao}."
                )
            resultado.append((item, caminho, existente))
        return resultado

    def _atualizar_dados_tecnicos(self, instrumento, item):
        tecnico, _ = InstrumentoTecnico.objects.get_or_create(instrumento=instrumento)
        tecnico.faixa_medicao = item.faixa_calibracao
        tecnico.capacidade_total = item.faixa_indicacao
        tecnico.unidade = item.unidade
        if item.resolucao is not None:
            tecnico.menor_resolucao = item.resolucao
        tecnico.save()
