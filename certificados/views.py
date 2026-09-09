from django.http import FileResponse, HttpResponseGone
from django.shortcuts import get_object_or_404, redirect, render

from documentos.services.documentos import verificar_integridade
from documentos.services.storages import storage_para_backend
from .models import CertificadoCalibracao
from .qr import gerar_qr_svg


def consultar_certificado(request, uuid_publico):
    certificado = get_object_or_404(
        CertificadoCalibracao.objects.select_related("instrumento", "cliente", "documento"),
        uuid_publico=uuid_publico,
        publicado=True,
    )
    url_consulta = request.build_absolute_uri()
    return render(
        request,
        "certificados/consulta.html",
        {
            "certificado": certificado,
            "url_consulta": url_consulta,
            "qr_svg": gerar_qr_svg(url_consulta),
        },
    )


def baixar_certificado(request, uuid_publico):
    certificado = get_object_or_404(CertificadoCalibracao.objects.select_related("documento"), uuid_publico=uuid_publico, publicado=True)
    if certificado.status == CertificadoCalibracao.Status.SUBSTITUIDO:
        return HttpResponseGone("Este certificado foi substituído e o documento anterior está bloqueado.")
    if not certificado.pode_baixar_publicamente:
        return HttpResponseGone("Este documento não está disponível para acesso público.")
    documento = certificado.documento
    integro, _ = verificar_integridade(documento)
    if not integro:
        return HttpResponseGone("O documento está temporariamente indisponível.")
    storage = storage_para_backend(documento.backend_primario)
    if documento.backend_primario == documento.Backend.R2:
        return redirect(storage.presigned_url(documento.chave_armazenamento))
    response = FileResponse(storage.open(documento.chave_armazenamento, "rb"), filename=documento.nome_original, content_type="application/pdf")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
