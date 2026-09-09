from django.contrib.auth.decorators import login_required, permission_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect

from .models import DocumentoArquivo
from .services.storages import storage_para_backend


@login_required
@permission_required("documentos.view_documentoarquivo", raise_exception=True)
def download_documento(request, pk):
    documento = get_object_or_404(DocumentoArquivo, pk=pk)
    storage = storage_para_backend(documento.backend_primario)
    if documento.backend_primario == DocumentoArquivo.Backend.R2:
        return redirect(storage.presigned_url(documento.chave_armazenamento))
    resposta = FileResponse(
        storage.open(documento.chave_armazenamento, "rb"),
        as_attachment=request.GET.get("inline") != "1",
        filename=documento.nome_original,
        content_type=documento.mime_type,
    )
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta
