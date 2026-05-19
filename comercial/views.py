from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from .models import Proposta


def pdf_proposta(request, pk):
    proposta = get_object_or_404(Proposta, pk=pk)

    return HttpResponse(
        f"PDF da Proposta: {proposta.codigo}",
        content_type="text/plain"
    )
