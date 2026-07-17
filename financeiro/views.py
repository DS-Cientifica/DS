from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .helpers import EMPRESA_COMPRADORA, contato_principal_cliente, endereco_cliente, formatar_moeda
from .models import PedidoCompra, PedidoCompraItem


def _pedido_contexto(pedido):
    fornecedor = pedido.fornecedor
    contato = contato_principal_cliente(fornecedor)

    itens = []
    for numero, item in enumerate(pedido.itens.all(), start=1):
        itens.append(
            {
                "numero": numero,
                "obj": item,
                "valor_unitario": formatar_moeda(item.valor_unitario),
                "valor_total": formatar_moeda(item.valor_total),
            }
        )

    return {
        "empresa": EMPRESA_COMPRADORA,
        "pedido": pedido,
        "fornecedor": fornecedor,
        "contato": contato,
        "endereco_fornecedor": endereco_cliente(fornecedor),
        "itens": itens,
        "subtotal": formatar_moeda(pedido.subtotal),
        "desconto_total": formatar_moeda(pedido.desconto),
        "frete": formatar_moeda(pedido.frete),
        "outros_custos": formatar_moeda(pedido.outros_custos),
        "total": formatar_moeda(pedido.total),
        "anexo_nome": pedido.anexo.name.split("/")[-1] if pedido.anexo else "",
    }


@login_required
def pedido_compra_pdf(request, pk):
    pedido = get_object_or_404(
        PedidoCompra.objects.select_related(
            "fornecedor",
            "responsavel_compra",
        ).prefetch_related(
            "itens",
            "fornecedor__contatos",
        ),
        pk=pk,
    )

    return render(
        request,
        "financeiro/pedido_compra_pdf.html",
        _pedido_contexto(pedido),
    )


@login_required
def pedido_compra_duplicar(request, pk):
    pedido = get_object_or_404(
        PedidoCompra.objects.prefetch_related("itens"),
        pk=pk,
    )

    novo = PedidoCompra.objects.create(
        fornecedor=pedido.fornecedor,
        responsavel_compra=request.user,
        prazo_entrega=pedido.prazo_entrega,
        condicao_pagamento=pedido.condicao_pagamento,
        observacoes=pedido.observacoes,
        anexo=pedido.anexo,
        incluir_nome_anexo_pdf=pedido.incluir_nome_anexo_pdf,
        frete=pedido.frete,
        outros_custos=pedido.outros_custos,
    )

    for item in pedido.itens.all():
        PedidoCompraItem.objects.create(
            pedido=novo,
            produto=item.produto,
            codigo=item.codigo,
            descricao=item.descricao,
            quantidade=item.quantidade,
            unidade=item.unidade,
            valor_unitario=item.valor_unitario,
            desconto=item.desconto,
        )

    return redirect(reverse("admin:financeiro_pedidocompra_change", args=[novo.pk]))
