from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from .models import (
    Proposta,
    ItemProposta,
    ProdutoServico,
    ProdutoAnexo,
    PropostaAnexo,
    ComposicaoPreco,
    DadosTecnicos,
    CRMRegistro,
    CRMInteracao,
    CRMTicket,
)


# =========================
# ANEXOS PRODUTO
# =========================

class ProdutoAnexoInline(admin.TabularInline):
    model = ProdutoAnexo
    extra = 1


# =========================
# ANEXOS PROPOSTA
# =========================

class PropostaAnexoInline(admin.TabularInline):
    model = PropostaAnexo
    extra = 1


# =========================
# ITENS PROPOSTA
# =========================

class ItemPropostaInline(admin.TabularInline):
    model = ItemProposta
    extra = 1
    autocomplete_fields = ("produto",)


# =========================
# PROPOSTA
# =========================

@admin.register(Proposta)
class PropostaAdmin(admin.ModelAdmin):

    list_display = (
        "codigo",
        "cliente",
        "responsavel",
        "status",
        "total",
        "gerar_pdf",
    )

    search_fields = (
        "codigo",
        "cliente__razao_social",
    )

    list_filter = (
        "status",
        "local_execucao",
        "frete",
    )

    readonly_fields = (
        "codigo",
        "total",
        "metodo",
        "padroes_utilizados",
        "data_emissao",
    )

    autocomplete_fields = ("cliente", "responsavel")

    inlines = [
        ItemPropostaInline,
        PropostaAnexoInline,
    ]

    fieldsets = (
        ("Dados Gerais", {
            "fields": (
                "codigo",
                "cliente",
                "responsavel",
                "status",
                "data_emissao",
                "validade",
            )
        }),

        ("Execução do Serviço", {
            "fields": (
                "local_execucao",
                "frete",
            )
        }),

        ("Financeiro", {
            "fields": (
                "prazo_pagamento",
                "total",
            )
        }),

        ("Metodologia (Automática)", {
            "description": "Preenchido automaticamente com base nos itens",
            "fields": (
                "metodo",
                "padroes_utilizados",
            )
        }),

        ("Observações", {
            "fields": (
                "observacoes",
            )
        }),
    )

    def gerar_pdf(self, obj):
        try:
            url = reverse("pdf_proposta", args=[obj.id])
            return format_html(
                "<a class='button' href='{}' target='_blank'>PDF</a>",
                url
            )
        except:
            return "-"

    gerar_pdf.short_description = "PDF"


# =========================
# PRODUTO / SERVIÇO
# =========================

class ComposicaoPrecoInline(admin.StackedInline):
    model = ComposicaoPreco
    extra = 0


class DadosTecnicosInline(admin.StackedInline):
    model = DadosTecnicos
    extra = 0


@admin.register(ProdutoServico)
class ProdutoServicoAdmin(admin.ModelAdmin):

    list_display = (
        "codigo",
        "nome",
        "tipo",
        "preco_venda",
        "ativo",
    )

    list_filter = ("tipo", "ativo")

    search_fields = ("codigo", "nome")

    readonly_fields = ("codigo", "preco_venda")

    inlines = [
        ComposicaoPrecoInline,
        DadosTecnicosInline,
        ProdutoAnexoInline,
    ]


# =========================
# CRM INTERAÇÕES
# =========================

class CRMInteracaoInline(admin.TabularInline):
    model = CRMInteracao
    extra = 1


# =========================
# CRM REGISTRO
# =========================

@admin.register(CRMRegistro)
class CRMRegistroAdmin(admin.ModelAdmin):

    list_display = (
        "cliente",
        "titulo",
        "etapa_funil",
        "valor_estimado",
        "probabilidade",
    )

    list_filter = (
        "etapa_funil",
    )

    search_fields = (
        "cliente__razao_social",
        "titulo",
    )

    autocomplete_fields = ("cliente", "proposta")

    inlines = [CRMInteracaoInline]


# =========================
# CRM TICKET
# =========================

@admin.register(CRMTicket)
class CRMTicketAdmin(admin.ModelAdmin):

    list_display = (
        "cliente",
        "titulo",
        "status",
        "prioridade",
    )

    list_filter = (
        "status",
        "prioridade",
    )

    search_fields = (
        "cliente__razao_social",
        "titulo",
    )

    autocomplete_fields = ("cliente",)
