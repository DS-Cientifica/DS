from django.contrib import admin
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import CertificadoCalibracao, PadraoUtilizado, RevisaoCertificado
from .qr import gerar_qr_svg


class PadraoUtilizadoInline(admin.TabularInline):
    model = PadraoUtilizado
    extra = 0
    can_delete = False
    readonly_fields = (
        "padrao", "documento", "data_utilizacao", "codigo", "descricao",
        "numero_certificado", "laboratorio_emitente", "data_calibracao",
        "validade", "situacao_na_data", "registrado_em",
    )

    def has_add_permission(self, request, obj=None):
        return False


class RevisaoCertificadoInline(admin.TabularInline):
    model = RevisaoCertificado
    extra = 0
    can_delete = False
    readonly_fields = ("acao", "justificativa", "usuario", "criado_em")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CertificadoCalibracao)
class CertificadoCalibracaoAdmin(admin.ModelAdmin):
    list_display = (
        "numero", "cliente_exibicao", "instrumento_exibicao", "arquivo_exibicao",
        "revisao", "status", "publicado", "permitir_download_publico",
        "data_calibracao", "acoes_publicas",
    )
    list_filter = ("status", "publicado", "permitir_download_publico")
    search_fields = (
        "numero", "codigo_curto", "uuid_publico",
        "cliente__codigo", "cliente__razao_social", "cliente__nome_empresa",
        "instrumento__codigo", "instrumento__descricao", "instrumento__numero_serie",
        "documento__nome_original",
    )
    list_select_related = ("cliente", "instrumento", "documento")
    readonly_fields = (
        "uuid_publico", "codigo_curto", "links_publicos", "criado_em", "atualizado_em",
    )
    inlines = (PadraoUtilizadoInline, RevisaoCertificadoInline)

    @admin.display(description="Cliente", ordering="cliente__razao_social")
    def cliente_exibicao(self, obj):
        return f"{obj.cliente.codigo} - {obj.cliente.razao_social}"

    @admin.display(description="Equipamento", ordering="instrumento__codigo")
    def instrumento_exibicao(self, obj):
        return f"{obj.instrumento.codigo} - {obj.instrumento.descricao}"

    @admin.display(description="Arquivo")
    def arquivo_exibicao(self, obj):
        return obj.documento.nome_original if obj.documento_id else "—"

    def has_add_permission(self, request, obj=None):
        # A publicação deve passar por publicar_calibracao_existente(), que valida
        # conclusão, PDF final, padrões e registra a trilha de auditoria.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        return [
            path(
                "<uuid:pk>/etiqueta/",
                self.admin_site.admin_view(self.etiqueta_view),
                name="certificados_certificadocalibracao_etiqueta",
            ),
        ] + super().get_urls()

    def _url_consulta(self, request, obj):
        caminho = reverse("certificados:consulta", args=[obj.uuid_publico])
        return request.build_absolute_uri(caminho)

    def etiqueta_view(self, request, pk):
        certificado = get_object_or_404(CertificadoCalibracao, pk=pk)
        if not self.has_view_permission(request, certificado):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        url_consulta = self._url_consulta(request, certificado)
        return render(
            request,
            "admin/certificados/certificadocalibracao/etiqueta.html",
            {
                **self.admin_site.each_context(request),
                "certificado": certificado,
                "url_consulta": url_consulta,
                "qr_svg": gerar_qr_svg(url_consulta, tamanho=220),
                "title": f"QR Code - {certificado.numero}",
            },
        )

    @admin.display(description="Consulta e QR Code")
    def acoes_publicas(self, obj):
        if not obj.publicado:
            return "Ainda não publicado"
        consulta = reverse("certificados:consulta", args=[obj.uuid_publico])
        etiqueta = reverse("admin:certificados_certificadocalibracao_etiqueta", args=[obj.pk])
        return format_html(
            '<a href="{}" target="_blank">Consultar</a> | '
            '<a href="{}" target="_blank">Imprimir QR</a>',
            consulta,
            etiqueta,
        )

    @admin.display(description="Consulta pública")
    def links_publicos(self, obj):
        if not obj or not obj.publicado:
            return "Disponível após a publicação."
        return self.acoes_publicas(obj)

    def get_readonly_fields(self, request, obj=None):
        campos = list(super().get_readonly_fields(request, obj))
        campos.extend(
            field.name
            for field in self.model._meta.fields
            if field.name not in campos
        )
        return tuple(campos)


@admin.register(PadraoUtilizado)
class PadraoUtilizadoAdmin(admin.ModelAdmin):
    list_display = ("certificado", "codigo", "numero_certificado", "validade", "situacao_na_data")
    list_filter = ("situacao_na_data",)
    search_fields = ("certificado__numero", "codigo", "descricao", "numero_certificado")
    readonly_fields = [field.name for field in PadraoUtilizado._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_model_perms(self, request):
        return {}


@admin.register(RevisaoCertificado)
class RevisaoCertificadoAdmin(admin.ModelAdmin):
    list_display = ("certificado", "acao", "usuario", "criado_em")
    search_fields = ("certificado__numero", "acao", "justificativa")
    readonly_fields = [field.name for field in RevisaoCertificado._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_model_perms(self, request):
        return {}
