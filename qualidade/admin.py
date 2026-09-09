from django.contrib import admin

from .models import Documento, DocumentoAnexo, DocumentoRevisao


class DocumentoRevisaoInline(admin.TabularInline):
    model = DocumentoRevisao
    extra = 0
    fields = ("revisao", "data", "alteracao", "responsavel", "status")
    readonly_fields = ()


class DocumentoAnexoInline(admin.TabularInline):
    model = DocumentoAnexo
    extra = 1
    fields = ("tipo", "titulo", "arquivo", "data_documento", "descricao", "created_at")
    readonly_fields = ("created_at",)
    verbose_name = "Anexo complementar"
    verbose_name_plural = "Fotos, vídeos e outros documentos"


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
    inlines = [DocumentoAnexoInline, DocumentoRevisaoInline]
    readonly_fields = ("created_at", "updated_at", "data_proxima_revisao")
    fieldsets = (
        (
            "Identificação",
            {
                "fields": ("codigo", "titulo", "tipo", "area", "arquivo", "arquivo_rascunho_pdf"),
                "description": (
                    "Os dois arquivos principais permanecem disponíveis. Para fotos, vídeos, "
                    "listas de presença e outros documentos, use a seção de anexos abaixo."
                ),
            },
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
