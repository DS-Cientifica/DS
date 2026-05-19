from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path

from comercial.models import Proposta
from .models import (
    CategoriaFinanceira,
    ContaPagar,
    ContaReceber,
    Imposto
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
        ("Origem", {
            "description": "Ao selecionar uma proposta aprovada, cliente, descrição e valor são preenchidos automaticamente.",
            "fields": (
                "proposta",
                "cliente",
            )
        }),
        ("Financeiro", {
            "fields": (
                "descricao",
                "valor",
                "vencimento",
                "status",
                "data_recebimento",
            )
        }),
        ("Comprovante", {
            "fields": (
                "comprovante",
            )
        }),
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
