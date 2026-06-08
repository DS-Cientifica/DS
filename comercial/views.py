from decimal import Decimal

from django.shortcuts import get_object_or_404, render

from .models import Proposta


EMPRESA_PROPOSTA = {
    "nome": "DS Científica",
    "site": "www.dscientifica.com.br",
    "telefone": "(11) 98859-9577",
    "cnpj": "63.669.660/0001-80",
    "cidade": "Jundiaí-SP",
    "endereço": "Avenida Reynlado de Porcari, 2788 - Jardim Tereza Cristina",
    "email": "contato@dscientifica.com.br"
   
}


def _formatar_moeda(valor):
    valor = Decimal(valor or 0)
    texto = f"{valor:,.2f}"
    return f"R$ {texto}".replace(",", "X").replace(".", ",").replace("X", ".")


def _endereco_cliente(cliente):
    partes = [
        cliente.endereco,
        cliente.numero,
        cliente.bairro,
        cliente.cidade,
        cliente.uf,
        cliente.cep,
    ]
    return " - ".join(str(parte).strip() for parte in partes if parte)


def _contato_principal(proposta):
    if proposta.responsavel_id:
        return proposta.responsavel

    return (
        proposta.cliente.contatos.filter(principal=True).first()
        or proposta.cliente.contatos.first()
    )


def pdf_proposta(request, pk):
    proposta = get_object_or_404(
        Proposta.objects.select_related("cliente", "responsavel").prefetch_related(
            "itens__produto",
            "cliente__contatos",
        ),
        pk=pk,
    )

    itens = []
    subtotal = Decimal("0")
    desconto_total = Decimal("0")

    for numero, item in enumerate(proposta.itens.all(), start=1):
        quantidade = Decimal(item.quantidade or 0)
        valor_unitario = Decimal(item.valor_unitario or 0)
        desconto = Decimal(item.desconto or 0)
        valor_bruto = quantidade * valor_unitario

        subtotal += valor_bruto
        desconto_total += desconto

        itens.append(
            {
                "numero": numero,
                "obj": item,
                "valor_unitario": _formatar_moeda(valor_unitario),
                "valor_total": _formatar_moeda(item.valor_total),
            }
        )

    contexto = {
        "empresa": EMPRESA_PROPOSTA,
        "proposta": proposta,
        "cliente": proposta.cliente,
        "contato": _contato_principal(proposta),
        "endereco_cliente": _endereco_cliente(proposta.cliente),
        "itens": itens,
        "subtotal": _formatar_moeda(subtotal),
        "desconto_total": _formatar_moeda(desconto_total),
        "total": _formatar_moeda(proposta.total),
        "local_execucao": proposta.get_local_execucao_display(),
        "frete": proposta.get_frete_display(),
        "status": proposta.get_status_display(),
    }

    return render(
        request,
        "comercial/proposta_pdf.html",
        contexto,
    )
