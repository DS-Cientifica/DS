from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404

from .models import Manutencao
from .pdf import gerar_pdf_manutencao


@login_required
def pdf_manutencao(request, pk):
    manutencao = get_object_or_404(
        Manutencao.objects.select_related(
            "cliente",
            "instrumento",
            "responsavel_cliente_ref",
            "responsavel_tecnico_ref",
        ).prefetch_related("evidencias"),
        pk=pk,
    )
    buffer = gerar_pdf_manutencao(manutencao)
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"manutencao_{manutencao.numero_relatorio}.pdf",
    )
