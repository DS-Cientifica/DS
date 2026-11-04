import re

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from documentos.services.assinaturas import (
    assinatura_atual_para_pdf,
    registrar_assinatura_pdf_a1,
    ultima_assinatura_do_objeto,
)
from documentos.services.documentos import verificar_integridade

from .models import (
    CertificadoCalibracao,
    EtiquetaCalibracaoQR,
    PadraoUtilizado,
    RevisaoCertificado,
)

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


def _vincular_etiqueta_reservada(certificado, calibracao, *, usuario=None):
    etiqueta = (
        EtiquetaCalibracaoQR.objects.select_for_update()
        .filter(codigo=certificado.numero)
        .first()
    )
    if not etiqueta:
        return None
    content_type = ContentType.objects.get_for_model(calibracao, for_concrete_model=False)
    if (
        etiqueta.status != EtiquetaCalibracaoQR.Status.RESERVADA
        or etiqueta.calibracao_content_type_id != content_type.pk
        or etiqueta.calibracao_object_id != str(calibracao.pk)
    ):
        raise ValidationError(
            "A etiqueta com este número não está reservada para esta calibração."
        )
    etiqueta.certificado = certificado
    etiqueta.status = EtiquetaCalibracaoQR.Status.VINCULADA
    etiqueta.vinculada_por = usuario if getattr(usuario, "is_authenticated", False) else None
    etiqueta.vinculada_em = timezone.now()
    etiqueta.full_clean()
    etiqueta.save(
        update_fields=(
            "certificado",
            "status",
            "vinculada_por",
            "vinculada_em",
            "atualizado_em",
        )
    )
    return etiqueta


def _pdf_final_da_calibracao(calibracao):
    if not calibracao.certificado_arquivo:
        raise ValidationError("Anexe o PDF final do certificado antes da assinatura.")
    with calibracao.certificado_arquivo.open("rb") as arquivo:
        pdf = arquivo.read()
    if not pdf.startswith(b"%PDF"):
        raise ValidationError("O arquivo final do certificado não é um PDF válido.")
    return pdf


def assinatura_atual_da_calibracao(calibracao):
    if not calibracao or not calibracao.pk or not calibracao.certificado_arquivo:
        return None
    try:
        pdf = _pdf_final_da_calibracao(calibracao)
    except (OSError, ValidationError):
        return None
    return assinatura_atual_para_pdf(calibracao, pdf)


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
    if calibracao.origem_certificado != calibracao.OrigemCertificado.EMITIDO_DS:
        raise ValidationError(
            "A assinatura e a publicação por QR são permitidas somente para "
            "certificados classificados como emitidos pela DS Científica."
        )
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


def assinar_calibracao_a1(calibracao, *, certificado_a1, senha, usuario):
    """Assina o PDF final antes da publicação, preservando o arquivo legado."""
    _validar_publicacao_calibracao(calibracao)
    existente = certificado_publico_da_calibracao(calibracao)
    if existente and existente.publicado:
        raise ValidationError(
            "Este certificado já foi publicado. Use o fluxo controlado de substituição "
            "para emitir uma nova revisão."
        )
    pdf = _pdf_final_da_calibracao(calibracao)
    numero = (calibracao.certificado_numero or "certificado").strip()
    nome_arquivo = re.sub(r"[^A-Za-z0-9._-]+", "-", numero).strip(".-")
    return registrar_assinatura_pdf_a1(
        objeto=calibracao,
        pdf=pdf,
        certificado_a1=certificado_a1,
        senha=senha,
        usuario=usuario,
        nome_arquivo=f"{nome_arquivo or 'certificado'}-rev00.pdf",
        revisao_referencia="00",
        motivo=f"Assinatura digital do certificado de calibração {numero}",
    )


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
    pdf = _pdf_final_da_calibracao(calibracao)
    assinatura = assinatura_atual_para_pdf(calibracao, pdf)
    if not assinatura:
        if ultima_assinatura_do_objeto(calibracao):
            raise ValidationError(
                "O PDF foi alterado depois da assinatura digital. Assine novamente antes de publicar."
            )
        raise ValidationError(
            "Assine digitalmente o certificado com o A1 antes da publicação."
        )
    integro, _motivo_integridade = verificar_integridade(assinatura.documento_assinado)
    if not integro:
        raise ValidationError(
            "O PDF assinado não passou na verificação de integridade e não pode ser publicado."
        )

    documento = assinatura.documento_assinado
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
    _vincular_etiqueta_reservada(certificado, calibracao, usuario=usuario)
    RevisaoCertificado.objects.create(
        certificado=certificado,
        acao="publicado",
        justificativa=(
            "Publicação controlada do PDF assinado digitalmente a partir da "
            "calibração concluída."
        ),
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
    )
    return certificado, True


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
