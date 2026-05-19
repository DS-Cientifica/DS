from django.shortcuts import render

# Create your views here.
from django.http import FileResponse
from django.shortcuts import get_object_or_404

from .models import Calibracao
from .pdf import gerar_pdf_calibracao


def pdf_calibracao(request, calibracao_id):
    calibracao = get_object_or_404(Calibracao, id=calibracao_id)

    buffer = gerar_pdf_calibracao(calibracao)

    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"calibracao_{calibracao.instrumento.codigo}.pdf"
    )

