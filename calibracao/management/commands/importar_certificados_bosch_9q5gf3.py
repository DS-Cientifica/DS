from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from clientes.models import Cliente
from calibracao.models import (
    Calibracao,
    HistoricoNumeroCertificado,
    Instrumento,
    InstrumentoTecnico,
    NumeroCertificadoEmitido,
    Padrao,
)


DEFAULT_SOURCE = Path(
    r"C:\Users\User\Desktop\BBOSCH-DSC- 9Q5GF3-16102026\Versão Final"
)


@dataclass(frozen=True)
class CertificadoImportacao:
    sequencia: int
    arquivo: str
    sha256: str
    numero: str
    instrumento: str
    descricao: str
    marca: str
    modelo: str
    numero_serie: str
    data_calibracao: date
    temperatura: Decimal | None
    umidade: Decimal | None
    padroes: tuple[str, ...]
    metodo: str
    unidade: str
    faixa_calibracao: str
    faixa_indicacao: str
    resolucao: Decimal | None
    resultado: str


def _d(valor):
    return Decimal(str(valor))


ARQUIVOS_PRESSAO = (
    (2, "BBGB-292", "E303B72C167A25FC76A45D3749C1905633FC751BE63C839EE68378A368CCAC21"),
    (3, "BBGB-300", "FA1300CB83945DDB89E5B191D57217FCC9A9A5E79C3CAE9F70FA97BB626F85DC"),
    (4, "BBGB-295", "2A22F0407C165E9F1ECE570580A560DE17D3841E92ECCF7BE4201715D3C9C90A"),
    (5, "BBGB-293", "B802BD56BE390BCA0DA34DC17237582C2DBEBAF41762B39500E5426A4C72A865"),
    (6, "BBGB-294", "3405D2BF1111E12C17DC31149AB81ACEFACC3170451B06E533454BC7803C6300"),
    (7, "BBGB-296", "A2C92247981AE4A91EAAA8C2C4EA6E33180E5361C03C0BCCB0B77B2466988189"),
    (8, "BBGB-297", "0DA1F68EFC83F526171F0B1E84923222A0F74E78628529BC9700DB4D4D0EBB97"),
    (9, "BBGB-298", "B94A8F79470354CF45D1E72CD04885BA9AA545CE5793F6571795D0EE8E51C499"),
    (10, "BBGB-299", "24612F85B06156DF367BA17EECC9F5A14B87413ACEE5BABAEF96F870E2EA0DF9"),
    (11, "BBGB-301", "9E23AA877425937E4121EFA02463E3D8F6AE8053D09DA55A11C2DDD66943C062"),
)


CERTIFICADOS = (
    CertificadoImportacao(
        1,
        "BBOSCH-DSC- 9Q5GF3-01-15102026.pdf",
        "51DD82DD60D93335A1CD549E33C84B0ACDDFDF4C498D7466E82581CD1479FAB7",
        "DSC-9Q5GF3-01-REV.01",
        "BBGB-183",
        "Válvula de segurança e alívio",
        "Caleffi",
        "WN20402",
        "Não consta",
        date(2026, 10, 15),
        None,
        None,
        ("DSP-010",),
        "Ensaio e ajuste conforme ASME Seção VIII, ASME PTC 25, NR-13 e ABNT NBR ISO/IEC 17025",
        "kgf/cm²",
        "Pressão final ajustada: 3,56 kgf/cm²",
        "Pressão requerida: 3,52 kgf/cm²",
        None,
        "aprovado",
    ),
    *(
        CertificadoImportacao(
            sequencia,
            f"BBOSCH-DSC- 9Q5GF3-{sequencia:02d}-15102026.pdf",
            sha256,
            f"DSC-9Q5GF3-{sequencia:02d}/2026",
            instrumento,
            "Manômetro analógico",
            "Prostec",
            "CL.A",
            "Não consta",
            date(2026, 10, 15),
            _d("23"),
            _d("55"),
            ("DSP-010", "DSP-022"),
            "MDS-018 Revisão 00",
            "kgf/cm²",
            "0 a 7 kgf/cm²",
            "0 a 7 kgf/cm²",
            _d("0.1"),
            "nao_declarado",
        )
        for sequencia, instrumento, sha256 in ARQUIVOS_PRESSAO
    ),
    CertificadoImportacao(
        12,
        "BBOSCH-DSC- 9Q5GF3-12-15102026.pdf",
        "E47F56C3D6EFF226D8E3AC04AF549AD7E6FBB57C3EB98CC796B06E7D409B1CED",
        "DSC-9Q5GF3-12/2026",
        "BBGB-302",
        "Termômetro de vidro",
        "Incoterm",
        "L001/26",
        "Não consta",
        date(2026, 10, 22),
        _d("23"),
        _d("55"),
        ("DSP-017", "DSP-022"),
        "MDS-004 Revisão 00",
        "°C",
        "-10 a 150 °C",
        "-10 a 150 °C",
        _d("1"),
        "nao_declarado",
    ),
    CertificadoImportacao(
        13,
        "BBOSCH-DSC- 9Q5GF3-13-22102026.pdf",
        "5E7C89B032339B26BFC7504277CE4F11869A60A80AC8439E78C9EB6AE21AEDEE",
        "DSC-9Q5GF3-13/2026",
        "BBGB-303",
        "Termômetro de vidro",
        "Incoterm",
        "L001/26",
        "Não consta",
        date(2026, 10, 22),
        _d("23"),
        _d("55"),
        ("DSP-017", "DSP-022"),
        "MDS-004 Revisão 00",
        "°C",
        "-10 a 150 °C",
        "-10 a 150 °C",
        _d("1"),
        "nao_declarado",
    ),
)


def _sha256(caminho):
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest().upper()


def _sha256_storage(campo_arquivo):
    digest = hashlib.sha256()
    campo_arquivo.open("rb")
    try:
        for bloco in iter(lambda: campo_arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    finally:
        campo_arquivo.close()
    return digest.hexdigest().upper()


def _observacoes(item):
    linhas = [
        "PDF final arquivado integralmente, incluindo os certificados de rastreabilidade anexos.",
        f"Unidade de medição conforme certificado: {item.unidade}.",
        f"Faixa de indicação: {item.faixa_indicacao}.",
        f"Faixa de calibração: {item.faixa_calibracao}.",
        "O certificado não informa data de próxima calibração; nenhuma validade foi presumida no cadastro.",
    ]
    if item.temperatura is None:
        linhas.append("Condições ambientais não declaradas no certificado principal.")
    else:
        linhas.append(
            f"Condições ambientais iniciais: {item.temperatura} °C e {item.umidade} %ur."
        )
    if item.resultado == "nao_declarado":
        linhas.append(
            "O documento apresenta resultados de medição, mas não contém declaração de conformidade; "
            "não foi atribuído resultado aprovado/reprovado pelo AXION."
        )
    else:
        linhas.append("Laudo inicial declarado no certificado: Aprovado.")
    return "\n".join(linhas)


class Command(BaseCommand):
    help = "Pré-visualiza ou importa de forma controlada os 13 certificados Bosch DSC-9Q5GF3."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        source = options["source"].resolve()
        aplicar = options["apply"]
        cliente, preflight = self._preflight(source)

        self.stdout.write(f"Fonte: {source}")
        self.stdout.write(f"Cliente: {cliente.codigo} | {cliente.razao_social}")
        self.stdout.write(f"Arquivos validados: {len(preflight)}")
        for item, caminho, instrumento, existente in preflight:
            acao = "EXISTENTE" if existente else ("CRIAR" if aplicar else "CRIARIA")
            instrumento_status = "existente" if instrumento else "será cadastrado"
            self.stdout.write(
                f"{acao:9} {item.numero} | {item.instrumento} ({instrumento_status}) | "
                f"{item.data_calibracao:%d/%m/%Y} | {','.join(item.padroes)} | "
                f"resultado={item.resultado} | sha256={_sha256(caminho)[:12]}"
            )

        pendentes = [linha for linha in preflight if not linha[3]]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING(
                    f"Prévia concluída: {len(pendentes)} certificado(s) seriam criados. "
                    "Use --apply para confirmar."
                )
            )
            return
        if not pendentes:
            self.stdout.write(
                self.style.SUCCESS("Nenhuma gravação pendente; os 13 certificados já existem.")
            )
            return

        arquivos_gravados = []
        instrumentos_criados = 0
        try:
            with transaction.atomic():
                for item, caminho, instrumento, _existente in pendentes:
                    if instrumento is None:
                        instrumento = Instrumento(
                            codigo=item.instrumento,
                            tag=item.instrumento,
                            descricao=item.descricao,
                            marca=item.marca,
                            modelo=item.modelo,
                            numero_serie=item.numero_serie,
                            cliente=cliente,
                            status="ativo",
                            ativo=True,
                        )
                        instrumento.full_clean()
                        instrumento.save()
                        instrumentos_criados += 1

                    tecnico, _criado = InstrumentoTecnico.objects.get_or_create(
                        instrumento=instrumento
                    )
                    alterado = False
                    for campo, valor in (
                        ("faixa_medicao", item.faixa_calibracao),
                        ("capacidade_total", item.faixa_indicacao),
                        ("unidade", item.unidade),
                        ("menor_resolucao", item.resolucao),
                    ):
                        if valor is not None and not getattr(tecnico, campo):
                            setattr(tecnico, campo, valor)
                            alterado = True
                    if alterado:
                        tecnico.full_clean()
                        tecnico.save()

                    instrumento.padroes.add(
                        *Padrao.objects.filter(codigo__in=item.padroes)
                    )
                    calibracao = Calibracao(
                        instrumento=instrumento,
                        data_calibracao=item.data_calibracao,
                        validade=None,
                        status="concluida",
                        resultado=item.resultado,
                        certificado_numero=item.numero,
                        empresa_emissora="DS Científica",
                        origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
                        metodo=item.metodo,
                        padroes=", ".join(item.padroes),
                        temperatura=item.temperatura,
                        umidade=item.umidade,
                        local_calibracao="in_loco",
                        observacoes=_observacoes(item),
                    )
                    with caminho.open("rb") as arquivo:
                        calibracao.certificado_arquivo.save(
                            caminho.name, File(arquivo), save=False
                        )
                    arquivos_gravados.append(calibracao.certificado_arquivo.name)
                    calibracao.full_clean()
                    calibracao.save()
                    # A periodicidade do instrumento não pode preencher uma data que o
                    # documento não declarou.
                    Calibracao.objects.filter(pk=calibracao.pk).update(validade=None)
                    calibracao.validade = None
                    if (
                        calibracao.certificado_numero != item.numero
                        or _sha256_storage(calibracao.certificado_arquivo) != item.sha256
                    ):
                        raise CommandError(f"Divergência após salvar {item.numero}.")
        except Exception:
            storage = Calibracao._meta.get_field("certificado_arquivo").storage
            for nome in arquivos_gravados:
                try:
                    storage.delete(nome)
                except Exception:
                    pass
            raise

        self.stdout.write(
            self.style.SUCCESS(
                f"Importação concluída: {len(pendentes)} certificados e "
                f"{instrumentos_criados} instrumentos criados."
            )
        )

    def _preflight(self, source):
        if not source.is_dir():
            raise CommandError(f"Pasta de origem não localizada: {source}")

        esperados = {item.arquivo for item in CERTIFICADOS}
        encontrados = {caminho.name for caminho in source.glob("*.pdf")}
        faltantes = sorted(esperados - encontrados)
        extras = sorted(encontrados - esperados)
        if faltantes or extras:
            raise CommandError(
                f"Conjunto de PDFs divergente. Faltantes={faltantes or '-'}; "
                f"extras={extras or '-'}"
            )

        clientes = list(
            Cliente.objects.filter(codigo="CL-0002", razao_social__icontains="BOSCH")
        )
        if len(clientes) != 1:
            raise CommandError(
                "O cliente CL-0002 Bosch não foi localizado de forma inequívoca."
            )
        cliente = clientes[0]

        codigos = {item.instrumento for item in CERTIFICADOS}
        instrumentos = {
            instrumento.codigo: instrumento
            for instrumento in Instrumento.objects.select_related("cliente").filter(
                codigo__in=codigos
            )
        }
        for codigo, instrumento in instrumentos.items():
            if instrumento.cliente_id != cliente.pk:
                raise CommandError(f"Instrumento {codigo} pertence a outro cliente.")
            if instrumento.tag and instrumento.tag.casefold() != codigo.casefold():
                raise CommandError(
                    f"Instrumento {codigo} possui TAG divergente: {instrumento.tag}."
                )

        codigos_padroes = {codigo for item in CERTIFICADOS for codigo in item.padroes}
        padroes = {
            padrao.codigo: padrao
            for padrao in Padrao.objects.filter(codigo__in=codigos_padroes)
        }
        ausentes = sorted(codigos_padroes - padroes.keys())
        if ausentes:
            raise CommandError("Padrões não localizados: " + ", ".join(ausentes))

        resultado = []
        for item in CERTIFICADOS:
            caminho = source / item.arquivo
            if caminho.stat().st_size <= 0:
                raise CommandError(f"Arquivo vazio: {caminho.name}")
            if _sha256(caminho) != item.sha256:
                raise CommandError(f"Integridade divergente em {caminho.name}.")
            for codigo in item.padroes:
                try:
                    padroes[codigo].validar_utilizacao_em(item.data_calibracao)
                except ValidationError as exc:
                    raise CommandError(
                        f"Padrão inadequado para {item.numero}: {' '.join(exc.messages)}"
                    ) from exc

            instrumento = instrumentos.get(item.instrumento)
            por_numero = (
                Calibracao.objects.filter(certificado_numero=item.numero)
                .select_related("instrumento")
                .first()
            )
            por_instrumento_data = None
            if instrumento:
                por_instrumento_data = Calibracao.objects.filter(
                    instrumento=instrumento,
                    data_calibracao=item.data_calibracao,
                ).first()
            existente = por_numero or por_instrumento_data

            if existente:
                arquivo_integro = bool(existente.certificado_arquivo)
                if arquivo_integro:
                    arquivo_integro = (
                        _sha256_storage(existente.certificado_arquivo) == item.sha256
                    )
                if not (
                    existente.certificado_numero == item.numero
                    and existente.instrumento.codigo == item.instrumento
                    and existente.data_calibracao == item.data_calibracao
                    and existente.validade is None
                    and existente.resultado == item.resultado
                    and existente.local_calibracao == "in_loco"
                    and existente.origem_certificado
                    == Calibracao.OrigemCertificado.EMITIDO_DS
                    and arquivo_integro
                ):
                    raise CommandError(
                        f"Conflito com cadastro existente para "
                        f"{item.numero}/{item.instrumento}/{item.data_calibracao}."
                    )
            else:
                reservado = NumeroCertificadoEmitido.objects.filter(
                    codigo=item.numero
                ).exists()
                historico = HistoricoNumeroCertificado.objects.filter(
                    numero_anterior=item.numero
                ).exists() or HistoricoNumeroCertificado.objects.filter(
                    numero_novo=item.numero
                ).exists()
                if reservado or historico:
                    raise CommandError(
                        f"O número {item.numero} já está reservado ou pertence ao histórico."
                    )

            resultado.append((item, caminho, instrumento, existente))
        return cliente, resultado
