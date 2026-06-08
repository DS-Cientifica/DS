from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html

from comercial.models import Proposta

from .helpers import EMPRESA_COMPRADORA, contato_principal_cliente, endereco_cliente
from .models import (
    CategoriaFinanceira,
    ContaPagar,
    ContaReceber,
    Imposto,
    PedidoCompra,
    PedidoCompraItem,
)


@admin.register(CategoriaFinanceira)
class CategoriaFinanceiraAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome")
    readonly_fields = ("codigo",)
    search_fields = ("codigo", "nome")


@admin.register(ContaPagar)
class ContaPagarAdmin(admin.ModelAdmin):
    list_display = (
        "descricao",
        "fornecedor",
        "valor",
        "vencimento",
        "status",
    )
    list_filter = ("status", "vencimento", "categoria")
    search_fields = ("descricao", "fornecedor")
    date_hierarchy = "vencimento"
    ordering = ("vencimento",)


@admin.register(ContaReceber)
class ContaReceberAdmin(admin.ModelAdmin):
    list_display = (
        "proposta",
        "cliente",
        "descricao",
        "valor",
        "vencimento",
        "status",
    )
    list_filter = ("status", "vencimento")
    search_fields = (
        "proposta__codigo",
        "cliente__razao_social",
        "cliente__cnpj",
        "descricao",
    )
    autocomplete_fields = ("proposta", "cliente")
    date_hierarchy = "vencimento"
    ordering = ("vencimento",)

    class Media:
        js = ("js/conta_receber_proposta.js",)

    fieldsets = (
        (
            "Origem",
            {
                "description": "Ao selecionar uma proposta aprovada, cliente, descrição e valor são preenchidos automaticamente.",
                "fields": (
                    "proposta",
                    "cliente",
                ),
            },
        ),
        (
            "Financeiro",
            {
                "fields": (
                    "descricao",
                    "valor",
                    "vencimento",
                    "status",
                    "data_recebimento",
                )
            },
        ),
        (
            "Comprovante",
            {
                "fields": ("comprovante",),
            },
        ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "proposta":
            kwargs["queryset"] = Proposta.objects.filter(status="aprovado").order_by("-data_emissao")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "proposta/<uuid:proposta_id>/dados/",
                self.admin_site.admin_view(self.proposta_dados),
                name="financeiro_contareceber_proposta_dados",
            ),
        ]
        return custom_urls + urls

    def proposta_dados(self, request, proposta_id):
        proposta = get_object_or_404(
            Proposta.objects.select_related("cliente"),
            pk=proposta_id,
            status="aprovado",
        )

        return JsonResponse(
            {
                "cliente_id": str(proposta.cliente_id),
                "cliente_label": str(proposta.cliente),
                "descricao": f"Proposta {proposta.codigo}",
                "valor": f"{proposta.total:.2f}".replace(".", ","),
            }
        )


class PedidoCompraItemInline(admin.TabularInline):
    model = PedidoCompraItem
    extra = 1
    autocomplete_fields = ("produto",)


@admin.register(PedidoCompra)
class PedidoCompraAdmin(admin.ModelAdmin):
    change_form_template = "admin/financeiro/pedidocompra/change_form.html"

    list_display = (
        "numero_pedido",
        "fornecedor",
        "data_emissao",
        "prazo_entrega",
        "condicao_pagamento",
        "total",
        "gerar_pdf",
    )
    list_filter = ("data_emissao", "prazo_entrega", "fornecedor")
    search_fields = ("numero_pedido", "fornecedor__razao_social", "fornecedor__cnpj", "condicao_pagamento")
    date_hierarchy = "data_emissao"
    autocomplete_fields = ("fornecedor", "responsavel_compra")
    readonly_fields = (
        "numero_pedido",
        "data_emissao",
        "subtotal",
        "desconto",
        "total",
        "comprador_empresa",
        "comprador_cnpj",
        "comprador_endereco",
        "comprador_cidade",
        "comprador_estado",
        "comprador_telefone",
        "comprador_email",
        "fornecedor_razao_social",
        "fornecedor_nome_fantasia",
        "fornecedor_cnpj",
        "fornecedor_ie",
        "fornecedor_contato",
        "fornecedor_telefone",
        "fornecedor_email",
        "fornecedor_endereco",
    )

    fieldsets = (
        (
            "Dados do Comprador",
            {
                "fields": (
                    "comprador_empresa",
                    "comprador_cnpj",
                    "comprador_endereco",
                    "comprador_cidade",
                    "comprador_estado",
                    "comprador_telefone",
                    "comprador_email",
                )
            },
        ),
        (
            "Fornecedor",
            {
                "fields": (
                    "fornecedor",
                    "fornecedor_razao_social",
                    "fornecedor_nome_fantasia",
                    "fornecedor_cnpj",
                    "fornecedor_ie",
                    "fornecedor_contato",
                    "fornecedor_telefone",
                    "fornecedor_email",
                    "fornecedor_endereco",
                )
            },
        ),
        (
            "Dados do Pedido",
            {
                "fields": (
                    "numero_pedido",
                    "data_emissao",
                    "responsavel_compra",
                    "prazo_entrega",
                    "condicao_pagamento",
                    "frete",
                    "outros_custos",
                    "observacoes",
                )
            },
        ),
        (
            "Totais",
            {
                "fields": (
                    "subtotal",
                    "desconto",
                    "total",
                )
            },
        ),
    )

    inlines = [PedidoCompraItemInline]

    class Media:
        js = ("js/pedido_compra.js",)

    def comprador_empresa(self, obj):
        return EMPRESA_COMPRADORA["empresa"]

    comprador_empresa.short_description = "Empresa"

    def comprador_cnpj(self, obj):
        return EMPRESA_COMPRADORA["cnpj"]

    comprador_cnpj.short_description = "CNPJ"

    def comprador_endereco(self, obj):
        return EMPRESA_COMPRADORA["endereco"]

    comprador_endereco.short_description = "Endereço"

    def comprador_cidade(self, obj):
        return EMPRESA_COMPRADORA["cidade"]

    comprador_cidade.short_description = "Cidade"

    def comprador_estado(self, obj):
        return EMPRESA_COMPRADORA["estado"]

    comprador_estado.short_description = "Estado"

    def comprador_telefone(self, obj):
        return EMPRESA_COMPRADORA["telefone"]

    comprador_telefone.short_description = "Telefone"

    def comprador_email(self, obj):
        return EMPRESA_COMPRADORA["email"]

    comprador_email.short_description = "E-mail"

    def fornecedor_nome_fantasia(self, obj):
        if not obj.fornecedor_id:
            return "-"
        return getattr(obj.fornecedor, "nome_empresa", "-")

    fornecedor_nome_fantasia.short_description = "Nome fantasia"

    def fornecedor_razao_social(self, obj):
        if not obj.fornecedor_id:
            return "-"
        return getattr(obj.fornecedor, "razao_social", "-")

    fornecedor_razao_social.short_description = "Razão social"

    def fornecedor_cnpj(self, obj):
        if not obj.fornecedor_id:
            return "-"
        return getattr(obj.fornecedor, "cnpj", "-")

    fornecedor_cnpj.short_description = "CNPJ"

    def fornecedor_ie(self, obj):
        if not obj.fornecedor_id:
            return "-"
        return getattr(obj.fornecedor, "ie", "-")

    fornecedor_ie.short_description = "Inscrição estadual"

    def fornecedor_contato(self, obj):
        if not obj.fornecedor_id:
            return "-"
        contato = contato_principal_cliente(obj.fornecedor)
        return contato.nome if contato else "-"

    fornecedor_contato.short_description = "Contato"

    def fornecedor_telefone(self, obj):
        if not obj.fornecedor_id:
            return "-"
        contato = contato_principal_cliente(obj.fornecedor)
        if contato and contato.telefone:
            return contato.telefone
        return getattr(obj.fornecedor, "telefone", "-")

    fornecedor_telefone.short_description = "Telefone"

    def fornecedor_email(self, obj):
        if not obj.fornecedor_id:
            return "-"
        contato = contato_principal_cliente(obj.fornecedor)
        if contato and contato.email:
            return contato.email
        return getattr(obj.fornecedor, "email", "-")

    fornecedor_email.short_description = "E-mail"

    def fornecedor_endereco(self, obj):
        return endereco_cliente(obj.fornecedor) if obj.fornecedor_id else "-"

    fornecedor_endereco.short_description = "Endereço"

    def save_model(self, request, obj, form, change):
        if not obj.responsavel_compra_id:
            obj.responsavel_compra = request.user
        super().save_model(request, obj, form, change)

    def gerar_pdf(self, obj):
        return format_html(
            "<a class='button' href='{}' target='_blank'>Gerar PDF</a>",
            reverse("financeiro:pedido_compra_pdf", args=[obj.id]),
        )

    gerar_pdf.short_description = "PDF"

    def duplicar_pedido(self, request, pk):
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

        return redirect(f"/admin/financeiro/pedidocompra/{novo.pk}/change/")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "pedido-compra/<uuid:pk>/duplicar/",
                self.admin_site.admin_view(self.duplicar_pedido),
                name="financeiro_pedidocompra_duplicar",
            ),
        ]
        return custom_urls + urls


@admin.register(Imposto)
class ImpostoAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "competencia",
        "valor",
        "vencimento",
        "pago",
    )
    list_filter = ("pago", "competencia")
    date_hierarchy = "vencimento"
