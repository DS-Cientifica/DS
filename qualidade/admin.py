from django.contrib import admin

from .models import Documento, DocumentoRevisao


class DocumentoRevisaoInline(admin.TabularInline):
    model = DocumentoRevisao
    extra = 0
    fields = ("revisao", "data", "alteracao", "responsavel", "status")
    readonly_fields = ()


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "titulo",
        "tipo",
        "revisao",
        "status",
        "data_ultima_revisao",
        "data_proxima_revisao",
        "aprovado_por",
    )
    list_filter = (
        "tipo",
        "status",
        "aprovado_por",
        "data_emissao",
        "data_ultima_revisao",
    )
    search_fields = ("codigo", "titulo", "responsavel", "area", "observacoes")
    ordering = ("codigo", "titulo")
    inlines = [DocumentoRevisaoInline]
    readonly_fields = ("created_at", "updated_at", "data_proxima_revisao")
    fieldsets = (
        (
            "Identificação",
            {"fields": ("codigo", "titulo", "tipo", "area", "arquivo", "arquivo_rascunho_pdf")},
        ),
        (
            "Controle documental",
            {
                "fields": (
                    "revisao",
                    "status",
                    "data_emissao",
                    "data_ultima_revisao",
                    "prazo_revisao_meses",
                    "aprovado_por",
                    "responsavel",
                )
            },
        ),
        ("Histórico e observações", {"fields": ("observacoes", "obsoleto_motivo", "created_at", "updated_at", "data_proxima_revisao")}),
    )

    def data_proxima_revisao(self, obj):
        return obj.data_proxima_revisao

    data_proxima_revisao.short_description = "Próxima revisão"

    actions = ("marcar_como_obsoleto", "marcar_como_vigente")

    @admin.action(description="Marcar documentos como obsoletos")
    def marcar_como_obsoleto(self, request, queryset):
        queryset.update(status="obsoleto")

    @admin.action(description="Marcar documentos como vigentes")
    def marcar_como_vigente(self, request, queryset):
        queryset.update(status="vigente")
