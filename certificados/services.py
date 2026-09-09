import re
import logging

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from documentos.services.documentos import registrar_documento
from documentos.services.storages import storage_para_backend

from .models import CertificadoCalibracao, PadraoUtilizado, RevisaoCertificado


logger = logging.getLogger(__name__)


def situacao_padrao_na_data(padrao, data_utilizacao):
    if padrao.status == "suspenso":
        return PadraoUtilizado.Situacao.SUSPENSO
    if not (padrao.numero_certificado or padrao.certificado):
        return PadraoUtilizado.Situacao.SEM_CERTIFICADO
    if padrao.vencimento and padrao.vencimento < data_utilizacao:
        return PadraoUtilizado.Situacao.VENCIDO
    return PadraoUtilizado.Situacao.VALIDO


def vincular_padrao(certificado, padrao, *, documento=None):
    if certificado.status not in {CertificadoCalibracao.Status.RASCUNHO, CertificadoCalibracao.Status.EM_REVISAO}:
        raise ValidationError("Padrões só podem ser alterados antes da aprovação.")
    return PadraoUtilizado.objects.create(
        certificado=certificado,
        padrao=padrao,
        documento=documento,
        data_utilizacao=certificado.data_calibracao,
        codigo=padrao.codigo,
        descricao=padrao.descricao,
        numero_certificado=padrao.numero_certificado,
        laboratorio_emitente=padrao.laboratorio_emitente,
        data_calibracao=padrao.data_calibracao,
        validade=padrao.vencimento,
        situacao_na_data=situacao_padrao_na_data(padrao, certificado.data_calibracao),
    )


def certificado_publico_da_calibracao(calibracao):
    content_type = ContentType.objects.get_for_model(calibracao, for_concrete_model=False)
    return (
        CertificadoCalibracao.objects.filter(
            calibracao_content_type=content_type,
            calibracao_object_id=str(calibracao.pk),
        )
        .order_by("-revisao", "-criado_em")
        .first()
    )


def _padroes_cadastrados_da_calibracao(calibracao):
    texto = (calibracao.padroes or "").strip()
    if not texto:
        raise ValidationError(
            "Informe os padrões utilizados na calibração antes da publicação."
        )

    codigos = [codigo.strip() for codigo in re.split(r"[,;\n]+", texto) if codigo.strip()]
    cadastrados = {
        padrao.codigo: padrao
        for padrao in calibracao.instrumento.padroes.filter(codigo__in=codigos)
    }
    nao_localizados = [codigo for codigo in codigos if codigo not in cadastrados]
    if nao_localizados:
        raise ValidationError(
            "Os seguintes padrões informados na calibração não estão vinculados ao "
            "cadastro do instrumento: " + ", ".join(nao_localizados)
        )
    return [cadastrados[codigo] for codigo in codigos]


def _validar_publicacao_calibracao(calibracao):
    if calibracao.status != "concluida":
        raise ValidationError("Somente calibrações concluídas podem ser publicadas.")
    if not (calibracao.certificado_numero or "").strip():
        raise ValidationError("Informe o número do certificado antes da publicação.")
    if not calibracao.certificado_arquivo:
        raise ValidationError("Anexe o PDF final do certificado antes da publicação.")

    padroes = _padroes_cadastrados_da_calibracao(calibracao)
    impedimentos = []
    for padrao in padroes:
        situacao = situacao_padrao_na_data(padrao, calibracao.data_calibracao)
        if situacao != PadraoUtilizado.Situacao.VALIDO:
            impedimentos.append(f"{padrao.codigo} ({PadraoUtilizado.Situacao(situacao).label})")
    if impedimentos:
        raise ValidationError(
            "Publicação bloqueada pela rastreabilidade metrológica: "
            + ", ".join(impedimentos)
        )
    return padroes


@transaction.atomic
def publicar_calibracao_existente(calibracao, *, usuario=None):
    """Publica uma cópia imutável do PDF final sem alterar o FileField legado."""
    content_type = ContentType.objects.get_for_model(calibracao, for_concrete_model=False)
    existente = (
        CertificadoCalibracao.objects.select_for_update()
        .filter(
            calibracao_content_type=content_type,
            calibracao_object_id=str(calibracao.pk),
        )
        .order_by("-revisao", "-criado_em")
        .first()
    )
    if existente:
        if not existente.publicado:
            raise ValidationError(
                "Já existe um registro em preparação para esta calibração. "
                "Conclua a revisão antes de publicar."
            )
        return existente, False

    padroes = _validar_publicacao_calibracao(calibracao)
    documento = None
    try:
        with calibracao.certificado_arquivo.open("rb") as arquivo:
            documento = registrar_documento(
                arquivo,
                tipo_documento="certificado_calibracao_publicado",
                objeto=calibracao,
                usuario=usuario,
                imutavel=True,
            )

        certificado = CertificadoCalibracao.objects.create(
            numero=calibracao.certificado_numero.strip(),
            calibracao_content_type=content_type,
            calibracao_object_id=str(calibracao.pk),
            instrumento=calibracao.instrumento,
            cliente=calibracao.instrumento.cliente,
            documento=documento,
            data_calibracao=calibracao.data_calibracao,
            proxima_calibracao=calibracao.validade,
            status=CertificadoCalibracao.Status.RASCUNHO,
            publicado=False,
            permitir_download_publico=False,
        )
        for padrao in padroes:
            vincular_padrao(certificado, padrao)

        certificado.status = CertificadoCalibracao.Status.VALIDO
        certificado.publicado = True
        certificado.permitir_download_publico = True
        certificado.aprovado_por = usuario if getattr(usuario, "is_authenticated", False) else None
        certificado.aprovado_em = timezone.now()
        certificado.save(
            update_fields=(
                "status", "publicado", "permitir_download_publico",
                "aprovado_por", "aprovado_em", "atualizado_em",
            )
        )
        RevisaoCertificado.objects.create(
            certificado=certificado,
            acao="publicado",
            justificativa="Publicação controlada a partir da calibração concluída.",
            usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        )
        return certificado, True
    except Exception:
        # O storage não participa da transação do banco. Compense a gravação física
        # antes que o atomic externo reverta DocumentoArquivo e seus vínculos.
        if documento is not None:
            try:
                storage_para_backend(documento.backend_primario).delete(
                    documento.chave_armazenamento
                )
            except Exception:
                logger.exception(
                    "Falha ao remover arquivo órfão após erro na publicação do certificado %s.",
                    calibracao.pk,
                )
        raise


@transaction.atomic
def substituir_certificado(anterior, substituto, *, usuario=None, justificativa):
    anterior = CertificadoCalibracao.objects.select_for_update().get(pk=anterior.pk)
    substituto = CertificadoCalibracao.objects.select_for_update().get(pk=substituto.pk)
    if anterior.pk == substituto.pk:
        raise ValidationError("Selecione certificados diferentes.")
    if anterior.status == CertificadoCalibracao.Status.SUBSTITUIDO:
        raise ValidationError("O certificado anterior já foi substituído.")
    if substituto.status not in {CertificadoCalibracao.Status.APROVADO, CertificadoCalibracao.Status.VALIDO}:
        raise ValidationError("O certificado substituto precisa estar aprovado ou válido.")
    if not justificativa.strip():
        raise ValidationError("Informe a justificativa da substituição.")
    substituto.certificado_anterior = anterior
    substituto.save(update_fields=("certificado_anterior", "atualizado_em"))
    anterior.status = CertificadoCalibracao.Status.SUBSTITUIDO
    anterior.permitir_download_publico = False
    anterior.motivo_status = justificativa.strip()
    anterior.save(update_fields=("status", "permitir_download_publico", "motivo_status", "atualizado_em"))
    RevisaoCertificado.objects.create(certificado=anterior, acao="substituido", justificativa=justificativa.strip(), usuario=usuario)
    return anterior, substituto
