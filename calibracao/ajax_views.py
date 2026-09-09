from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse

from .services.ordem_servico import buscar_ordem_servico_do_instrumento


@staff_member_required
def ordem_servico_do_instrumento(request):
    instrumento_id = request.GET.get("instrumento_id")
    cliente_id = request.GET.get("cliente_id") or None
    ordem = buscar_ordem_servico_do_instrumento(instrumento_id, cliente_id)
    if not ordem:
        return JsonResponse({"encontrada": False, "numero": ""})

    return JsonResponse(
        {
            "encontrada": True,
            "numero": ordem.numero,
            "status": ordem.status,
        }
    )
