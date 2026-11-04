import hashlib
import re
from dataclasses import dataclass
from datetime import timezone as datetime_timezone
from io import BytesIO

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import signers
from pyhanko.pdf_utils.text import TextBoxStyle
from pyhanko.sign.fields import SigFieldSpec, SigSeedSubFilter
from pyhanko.sign.signers import PdfSignatureMetadata, PdfSigner
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko.stamp import TextStampStyle
from pyhanko_certvalidator import ValidationContext

from documentos.models import AssinaturaDigitalDocumento, DocumentoArquivo

from .documentos import registrar_documento
from .storages import storage_para_backend


@dataclass(frozen=True)
class ResultadoAssinaturaA1:
    pdf_assinado: bytes
    signatario_nome: str
    certificado_numero_serie: str
    certificado_emissor: str
    certificado_fingerprint_sha256: str
    certificado_valido_de: object
    certificado_valido_ate: object
    assinado_em: object
    integridade_verificada: bool


def _nome_certificado(certificado):
    atributos = certificado.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if not atributos:
        return certificado.subject.rfc4514_string()
    nome = atributos[0].value.strip()
    # Certificados ICP-Brasil de PJ normalmente usam "ID NOME:CNPJ" no CN.
    # O identificador completo continua rastreado pelo serial e fingerprint.
    correspondencia = re.match(r"^\d+\s+(.+?):\d{11,14}$", nome)
    return correspondencia.group(1).strip() if correspondencia else nome


def assinar_pdf_a1(
    pdf,
    certificado_a1,
    senha,
    *,
    motivo,
    nome_campo="AssinaturaAXION",
    assinatura_visivel=False,
    pagina_assinatura=-1,
    caixa_assinatura=(280, 10, 555, 38),
):
    """Assina um PDF em memória. O PKCS#12 e a senha nunca são persistidos."""
    if not pdf or not bytes(pdf).startswith(b"%PDF"):
        raise ValidationError("O documento de origem não é um PDF válido.")
    if not certificado_a1:
        raise ValidationError("Selecione o certificado A1 (.pfx ou .p12).")
    if not senha:
        raise ValidationError("Informe a senha do certificado A1.")

    senha_bytes = senha.encode("utf-8")
    try:
        chave, certificado, _cadeia = pkcs12.load_key_and_certificates(
            bytes(certificado_a1),
            senha_bytes,
        )
    except Exception as exc:
        raise ValidationError(
            "Não foi possível abrir o certificado A1. Confira o arquivo e a senha."
        ) from exc

    if chave is None or certificado is None:
        raise ValidationError("O arquivo A1 não contém certificado e chave privada utilizáveis.")

    agora = timezone.now()
    valido_de = certificado.not_valid_before_utc
    valido_ate = certificado.not_valid_after_utc
    agora_utc = agora.astimezone(datetime_timezone.utc)
    if agora_utc < valido_de or agora_utc > valido_ate:
        raise ValidationError(
            "O certificado A1 está fora do período de validade e não pode assinar documentos."
        )

    try:
        signer = signers.SimpleSigner.load_pkcs12_data(
            bytes(certificado_a1),
            other_certs=[],
            passphrase=senha_bytes,
        )
        if signer is None:
            raise ValueError("signer não inicializado")

        origem = BytesIO(bytes(pdf))
        destino = BytesIO()
        escritor = IncrementalPdfFileWriter(origem)
        metadados = PdfSignatureMetadata(
            field_name=nome_campo,
            md_algorithm="sha256",
            subfilter=SigSeedSubFilter.PADES,
            reason=motivo,
            name=_nome_certificado(certificado),
        )
        nome_signatario = _nome_certificado(certificado)
        especificacao_campo = None
        estilo_carimbo = None
        parametros_aparencia = None
        if assinatura_visivel:
            especificacao_campo = SigFieldSpec(
                sig_field_name=nome_campo,
                on_page=pagina_assinatura,
                box=caixa_assinatura,
                readable_field_name="Assinatura digital AXION",
            )
            estilo_carimbo = TextStampStyle(
                border_width=1,
                background_opacity=0.85,
                text_box_style=TextBoxStyle(font_size=6),
                stamp_text=(
                    "ASSINADO DIGITALMENTE POR %(signer)s\n"
                    "%(ts)s | ICP-Brasil | PAdES"
                ),
                timestamp_format="%d/%m/%Y %H:%M:%S %Z",
            )
            parametros_aparencia = {"signer": nome_signatario}
        PdfSigner(
            metadados,
            signer=signer,
            stamp_style=estilo_carimbo,
            new_field_spec=especificacao_campo,
        ).sign_pdf(
            escritor,
            output=destino,
            appearance_text_params=parametros_aparencia,
        )
        pdf_assinado = destino.getvalue()

        leitor = PdfFileReader(BytesIO(pdf_assinado))
        if not leitor.embedded_signatures:
            raise ValueError("assinatura não incorporada")
        contexto = ValidationContext(
            trust_roots=[signer.signing_cert],
            allow_fetching=False,
        )
        verificacao = validate_pdf_signature(
            leitor.embedded_signatures[-1],
            signer_validation_context=contexto,
        )
        integridade = bool(verificacao.intact and verificacao.valid)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(
            "A assinatura digital não pôde ser concluída ou verificada."
        ) from exc

    if not integridade:
        raise ValidationError("O PDF assinado não passou na verificação de integridade.")

    return ResultadoAssinaturaA1(
        pdf_assinado=pdf_assinado,
        signatario_nome=_nome_certificado(certificado),
        certificado_numero_serie=format(certificado.serial_number, "X"),
        certificado_emissor=certificado.issuer.rfc4514_string(),
        certificado_fingerprint_sha256=certificado.fingerprint(hashes.SHA256()).hex(),
        certificado_valido_de=valido_de,
        certificado_valido_ate=valido_ate,
        assinado_em=agora,
        integridade_verificada=integridade,
    )


def assinatura_atual_para_pdf(objeto, pdf_atual):
    if not objeto or not objeto.pk:
        return None
    content_type = ContentType.objects.get_for_model(objeto, for_concrete_model=False)
    hash_atual = hashlib.sha256(bytes(pdf_atual)).hexdigest()
    return (
        AssinaturaDigitalDocumento.objects.filter(
            content_type=content_type,
            object_id=str(objeto.pk),
            status=AssinaturaDigitalDocumento.Status.VALIDA,
            documento_original__sha256=hash_atual,
            integridade_verificada=True,
        )
        .select_related("documento_original", "documento_assinado", "autorizado_por")
        .first()
    )


def ultima_assinatura_do_objeto(objeto):
    if not objeto or not objeto.pk:
        return None
    content_type = ContentType.objects.get_for_model(objeto, for_concrete_model=False)
    return (
        AssinaturaDigitalDocumento.objects.filter(
            content_type=content_type,
            object_id=str(objeto.pk),
        )
        .select_related("documento_original", "documento_assinado", "autorizado_por")
        .first()
    )


def substituir_assinaturas_do_objeto(objeto):
    """Invalida assinaturas vigentes quando o conteúdo/revisão do objeto muda."""
    if not objeto or not objeto.pk:
        return 0
    content_type = ContentType.objects.get_for_model(objeto, for_concrete_model=False)
    with transaction.atomic():
        assinaturas = AssinaturaDigitalDocumento.objects.select_for_update().filter(
            content_type=content_type,
            object_id=str(objeto.pk),
            status=AssinaturaDigitalDocumento.Status.VALIDA,
        )
        documentos = list(assinaturas.values_list("documento_assinado_id", flat=True))
        quantidade = assinaturas.update(status=AssinaturaDigitalDocumento.Status.SUBSTITUIDA)
        if documentos:
            DocumentoArquivo.objects.filter(pk__in=documentos).update(
                status=DocumentoArquivo.Status.SUBSTITUIDO
            )
    return quantidade


def registrar_assinatura_pdf_a1(
    *,
    objeto,
    pdf,
    certificado_a1,
    senha,
    usuario,
    nome_arquivo,
    revisao_referencia="",
    motivo="Assinatura digital de documento no AXION",
    assinatura_visivel=False,
    pagina_assinatura=-1,
    caixa_assinatura=(280, 10, 555, 38),
):
    if not getattr(usuario, "is_authenticated", False):
        raise ValidationError("A assinatura exige um usuário autenticado.")

    resultado = assinar_pdf_a1(
        pdf,
        certificado_a1,
        senha,
        motivo=motivo,
        assinatura_visivel=assinatura_visivel,
        pagina_assinatura=pagina_assinatura,
        caixa_assinatura=caixa_assinatura,
    )
    nome_base = nome_arquivo.rsplit(".", 1)[0]
    documentos_criados = []
    try:
        with transaction.atomic():
            original = registrar_documento(
                ContentFile(bytes(pdf), name=f"{nome_base}-original.pdf"),
                tipo_documento="pdf_original_para_assinatura",
                objeto=objeto,
                usuario=usuario,
                imutavel=True,
            )
            documentos_criados.append(original)
            assinado = registrar_documento(
                ContentFile(resultado.pdf_assinado, name=f"{nome_base}-assinado.pdf"),
                tipo_documento="pdf_assinado_pades",
                objeto=objeto,
                usuario=usuario,
                imutavel=True,
            )
            documentos_criados.append(assinado)

            content_type = ContentType.objects.get_for_model(
                objeto,
                for_concrete_model=False,
            )
            anteriores = AssinaturaDigitalDocumento.objects.select_for_update().filter(
                content_type=content_type,
                object_id=str(objeto.pk),
                status=AssinaturaDigitalDocumento.Status.VALIDA,
            )
            documentos_anteriores = list(
                anteriores.values_list("documento_assinado_id", flat=True)
            )
            anteriores.update(status=AssinaturaDigitalDocumento.Status.SUBSTITUIDA)
            if documentos_anteriores:
                DocumentoArquivo.objects.filter(pk__in=documentos_anteriores).update(
                    status=DocumentoArquivo.Status.SUBSTITUIDO
                )

            assinatura = AssinaturaDigitalDocumento.objects.create(
                content_type=content_type,
                object_id=str(objeto.pk),
                documento_original=original,
                documento_assinado=assinado,
                revisao_referencia=revisao_referencia,
                motivo=motivo,
                signatario_nome=resultado.signatario_nome,
                certificado_numero_serie=resultado.certificado_numero_serie,
                certificado_emissor=resultado.certificado_emissor,
                certificado_fingerprint_sha256=resultado.certificado_fingerprint_sha256,
                certificado_valido_de=resultado.certificado_valido_de,
                certificado_valido_ate=resultado.certificado_valido_ate,
                assinado_em=resultado.assinado_em,
                integridade_verificada=resultado.integridade_verificada,
                autorizado_por=usuario,
            )
        return assinatura
    except Exception:
        for documento in documentos_criados:
            try:
                storage_para_backend(documento.backend_primario).delete(
                    documento.chave_armazenamento
                )
            except Exception:
                pass
        raise


def abrir_pdf_assinado(assinatura):
    documento = assinatura.documento_assinado
    return storage_para_backend(documento.backend_primario).open(
        documento.chave_armazenamento,
        "rb",
    )
