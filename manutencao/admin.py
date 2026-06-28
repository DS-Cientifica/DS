from django import forms
from django.contrib import admin
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from calibracao.models import ResponsavelCertificado

from .models import Manutencao, ManutencaoEvidencia


class ManutencaoEvidenciaInline(admin.TabularInline):
    model = ManutencaoEvidencia
    extra = 1


class ManutencaoAdminForm(forms.ModelForm):
    class Meta:
        model = Manutencao
        fields = "__all__"
        widgets = {
            "intervencoes": forms.Textarea(attrs={"rows": 4}),
            "materiais": forms.Textarea(attrs={"rows": 4}),
            "verificacoes": forms.Textarea(attrs={"rows": 4}),
            "rastreabilidade": forms.Textarea(attrs={"rows": 4}),
            "resultados": forms.Textarea(attrs={"rows": 4}),
        }


@admin.register(Manutencao)
class ManutencaoAdmin(admin.ModelAdmin):
    form = ManutencaoAdminForm
    list_display = (
        "numero_relatorio",
        "cliente",
        "instrumento",
        "tipo_manutencao",
        "data_servico",
        "status",
        "pdf_manutencao",
    )
    list_filter = ("tipo_manutencao", "status", "data_servico")
    search_fields = (
        "numero_relatorio",
        "ordem_servico",
        "cliente__razao_social",
        "instrumento__codigo",
        "instrumento__descricao",
        "responsavel_tecnico",
        "responsavel_cliente_ref__nome",
    )
    autocomplete_fields = ("cliente", "instrumento", "responsavel_cliente_ref", "responsavel_tecnico_ref")
    readonly_fields = ("numero_relatorio", "pdf_manutencao")
    inlines = (ManutencaoEvidenciaInline,)
    fieldsets = (
        ("Identificação", {
            "fields": (
                "numero_relatorio",
                "cliente",
                "responsavel_cliente_ref",
                "instrumento",
                "responsavel_tecnico_ref",
                "ordem_servico",
                "tipo_manutencao",
                "pdf_manutencao",
            )
        }),
        ("Datas e status", {
            "fields": (
                "data_recepcao",
                "data_servico",
                "data_saida",
                "proxima_manutencao",
                "status",
            )
        }),
        ("Execução", {
            "fields": (
                "condicao_recebida",
                "condicao_saida",
                "diagnostico",
                "parecer_tecnico",
                "criterio_aceitacao",
                "responsavel_tecnico",
            )
        }),
        ("Controle", {
            "fields": (
                "intervencoes",
                "materiais",
                "verificacoes",
                "rastreabilidade",
                "resultados",
                "aprovado_por",
                "aprovado_cargo",
                "aprovado_em",
                "observacoes",
            )
        }),
    )

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault("data_servico", timezone.localdate())
        initial.setdefault("status", Manutencao.Status.CONFORME)
        if not initial.get("responsavel_tecnico_ref"):
            responsavel = ResponsavelCertificado.objects.filter(ativo=True).order_by("nome").first()
            if responsavel:
                initial.setdefault("responsavel_tecnico_ref", responsavel.pk)
        return initial

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:pk>/pdf/",
                self.admin_site.admin_view(self.pdf_view),
                name="manutencao_manutencao_pdf",
            ),
        ]
        return custom_urls + urls

    def pdf_view(self, request, pk):
        from .views import pdf_manutencao

        return pdf_manutencao(request, pk)

    def pdf_manutencao(self, obj):
        if not obj.pk:
            return "-"
        return format_html(
            "<a class='button' href='{}' target='_blank'>Gerar PDF</a>",
            reverse("admin:manutencao_manutencao_pdf", args=[obj.pk]),
        )

    pdf_manutencao.short_description = "Impressão"
