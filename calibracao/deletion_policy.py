from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.db.models.deletion import ProtectedError


def motivos_protecao_exclusao(calibracao):
    if calibracao.pk is None:
        return ()

    from certificados.models import CertificadoCalibracao
    from documentos.models import DocumentoArquivo

    from .models import NumeroCertificadoEmitido

    using = calibracao._state.db or "default"
    app_label = calibracao._meta.app_label
    model_name = calibracao._meta.model_name
    object_id = str(calibracao.pk)
    motivos = []

    numero_certificado = str(
        getattr(calibracao, "certificado_numero", "")
        or getattr(calibracao, "numero_certificado", "")
        or ""
    ).strip()
    if numero_certificado:
        motivos.append("número de certificado atribuído")

    if getattr(calibracao, "certificado_arquivo", None):
        motivos.append("arquivo de certificado associado")

    if NumeroCertificadoEmitido.objects.using(using).filter(
        app_label=app_label,
        modelo=model_name,
        objeto_id=object_id,
    ).exists():
        motivos.append("reserva de número de certificado registrada")

    content_type = ContentType.objects.db_manager(using).get_for_model(
        calibracao,
        for_concrete_model=False,
    )
    certificados = CertificadoCalibracao.objects.using(using).filter(
        calibracao_content_type=content_type,
        calibracao_object_id=object_id,
    )
    if certificados.exists():
        motivos.append("certificado controlado gerado")
    if certificados.filter(publicado=True).exists():
        motivos.append("publicação registrada")
    if certificados.filter(Q(revisao__gt=0) | Q(historico__isnull=False)).exists():
        motivos.append("revisão de certificado registrada")

    documentos_oficiais = DocumentoArquivo.objects.using(using).filter(
        content_type=content_type,
        object_id=object_id,
    ).filter(
        Q(imutavel=True)
        | Q(tipo_documento__icontains="certificado")
        | Q(tipo_documento__icontains="resultado")
    )
    if documentos_oficiais.exists():
        motivos.append("documento oficial associado")

    return tuple(dict.fromkeys(motivos))


def impedir_exclusao_calibracao_oficial(sender, instance, **kwargs):
    motivos = motivos_protecao_exclusao(instance)
    if motivos:
        raise ProtectedError(
            "A calibração não pode ser excluída porque possui resultado oficial: "
            + ", ".join(motivos)
            + ". Preserve o registro e utilize um fluxo controlado de cancelamento.",
            {instance},
        )
