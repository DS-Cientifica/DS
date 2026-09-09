from django.contrib import admin

from .models import DocumentoArquivo, DocumentoVinculo, SincronizacaoDocumento


class SincronizacaoDocumentoInline(admin.TabularInline):
    model = SincronizacaoDocumento
    extra = 0
    can_delete = False
    readonly_fields = (
        "destino",
        "status",
        "tentativas",
        "ultimo_erro",
        "etag_remoto",
        "criado_em",
        "atualizado_em",
        "sincronizado_em",
    )

    def has_add_permission(self, request, obj=None):
        return False


class DocumentoVinculoInline(admin.TabularInline):
    model = DocumentoVinculo
    extra = 0
    can_delete = False
    readonly_fields = ("content_type", "object_id", "campo_origem", "criado_em")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DocumentoArquivo)
class DocumentoArquivoAdmin(admin.ModelAdmin):
    list_display = (
        "nome_original",
        "tipo_documento",
        "backend_primario",
        "status",
        "imutavel",
        "criado_em",
    )
    list_filter = ("tipo_documento", "backend_primario", "status", "imutavel")
    search_fields = ("nome_original", "chave_armazenamento", "sha256")
    readonly_fields = (
        "id",
        "nome_original",
        "tipo_documento",
        "chave_armazenamento",
        "backend_primario",
        "sha256",
        "tamanho",
        "mime_type",
        "imutavel",
        "status",
        "content_type",
        "object_id",
        "documento_anterior",
        "criado_por",
        "criado_em",
        "atualizado_em",
        "verificado_em",
    )
    inlines = (DocumentoVinculoInline, SincronizacaoDocumentoInline)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(SincronizacaoDocumento)
class SincronizacaoDocumentoAdmin(admin.ModelAdmin):
    list_display = ("documento", "destino", "status", "tentativas", "sincronizado_em")
    list_filter = ("destino", "status")
    search_fields = ("documento__nome_original", "documento__sha256")
    readonly_fields = (
        "documento",
        "destino",
        "status",
        "tentativas",
        "ultimo_erro",
        "etag_remoto",
        "criado_em",
        "atualizado_em",
        "sincronizado_em",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_model_perms(self, request):
        return {}


@admin.register(DocumentoVinculo)
class DocumentoVinculoAdmin(admin.ModelAdmin):
    list_display = ("documento", "content_type", "object_id", "campo_origem", "criado_em")
    list_filter = ("content_type", "campo_origem")
    search_fields = ("documento__nome_original", "object_id")
    readonly_fields = ("documento", "content_type", "object_id", "campo_origem", "criado_em")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_model_perms(self, request):
        return {}
