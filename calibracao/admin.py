from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from .models import (
    Instrumento,
    InstrumentoTecnico,
    OrdemServico,
    Padrao,
    Periodicidade,
    Calibracao,
    CalibracaoAnexo
)


# =========================
# INLINES
# =========================

class PeriodicidadeInline(admin.TabularInline):
    model = Periodicidade
    extra = 1


class InstrumentoTecnicoInline(admin.StackedInline):
    model = InstrumentoTecnico
    extra = 0


# =========================
# INSTRUMENTO
# =========================

@admin.register(Instrumento)
class InstrumentoAdmin(admin.ModelAdmin):

    list_display = (
        "codigo",
        "descricao",
        "marca",
        "modelo",
        "numero_serie",
        "cliente",
        "status",
        "ver_certificados_padroes",
    )

    list_filter = (
        "status",
        "cliente",
    )

    search_fields = (
        "codigo",
        "descricao",
        "marca",
        "modelo",
        "numero_serie",
        "cliente__razao_social",
    )

    autocomplete_fields = (
        "cliente",
        "padroes",
    )

    readonly_fields = (
        "ver_certificados_padroes",
        )

    ordering = ("descricao",)

    fieldsets = (
        ("Identificação", {
            "fields": (
                "codigo",
                "descricao",
                "cliente",
                "status",
            )
        }),

        ("Dados Técnicos", {
            "fields": (
                "marca",
                "modelo",
                "numero_serie",
            )
        }),

        ("Localização", {
            "fields": (
                "local_instalacao",
            )
        }),

        ("Metrologia", {
            "fields": (
                "metodo_calibracao",
                "padroes",
                "ver_certificados_padroes",
            )
        }),

        ("Controle", {
            "fields": (
                "proxima_calibracao",
                "ativo",
                "nome_anexo",
                "anexo",
            )
        }),
    )

    inlines = [
        InstrumentoTecnicoInline,
        PeriodicidadeInline,
    ]

    def ver_certificados_padroes(self, obj):
        links = []
        for p in obj.padroes.all():
            if p.certificado:
                links.append(f"<a href='{p.certificado.url}' target='_blank'>{p.codigo}</a>")
        return format_html("<br>".join(links)) if links else "—"

    ver_certificados_padroes.short_description = "Certificados dos Padrões"


# =========================
# CALIBRAÇÃO
# =========================
class CalibracaoAnexoInline(admin.TabularInline):
    model = CalibracaoAnexo
    extra = 1

@admin.register(Calibracao)
class CalibracaoAdmin(admin.ModelAdmin):

    list_display = (
        "instrumento",
        "data_calibracao",
        "validade",
        "certificado_numero",
        "resultado",
        "local_calibracao",
        "empresa_emissora",
        "ver_anexo",
    )

    list_filter = (
        "resultado",
        "empresa_emissora",
        "status",
        "local_calibracao",
    )

    search_fields = (
        "instrumento__codigo",
        "instrumento__descricao",
        "certificado_numero",
    )

    autocomplete_fields = ("instrumento",)

    readonly_fields = (
        "validade",
        "created_at",
        "marca",
        "modelo",
        "numero_serie",
        "local_instalacao",
        "ver_certificados_padroes",
        "ver_metodo",
    )

    fieldsets = (
        ("Instrumento", {
            "fields": ("instrumento",)
        }),

        ("Dados do Equipamento", {
            "fields": (
                "marca",
                "modelo",
                "numero_serie",
                "local_instalacao",
            )
        }),

        ("Dados da Calibração", {
            "fields": (
                "data_calibracao",
                "validade",
                "status",
                "resultado",
                "local_calibracao",
            )
        }),

        ("Condições Ambientais", {
            "fields": (
                "temperatura",
                "umidade",
            )
        }),

        ("Metodologia", {
            "fields": (
                "metodo",
                "padroes",
                "ver_metodo",
                "ver_certificados_padroes",
            )
        }),

        ("Execução", {
            "fields": (
                "equipamentos_auxiliares",
            )
        }),

        ("Certificado", {
            "fields": (
                "certificado_numero",
                "certificado_arquivo",
                "empresa_emissora",
            )
        }),

        ("Observações", {
            "fields": ("observacoes",)
        }),
    )

    def marca(self, obj):
        return getattr(obj.instrumento, "marca", "")

    def modelo(self, obj):
        return getattr(obj.instrumento, "modelo", "")

    def numero_serie(self, obj):
        return getattr(obj.instrumento, "numero_serie", "")

    def local_instalacao(self, obj):
        return getattr(obj.instrumento, "local_instalacao", "")

    def ver_metodo(self, obj):
        if obj.instrumento and obj.instrumento.metodo_calibracao:
            return obj.instrumento.metodo_calibracao.titulo
        return "—"

    def ver_certificados_padroes(self, obj):
        if obj.instrumento:
            links = []
            for p in obj.instrumento.padroes.all():
                if p.certificado:
                    links.append(f"<a href='{p.certificado.url}' target='_blank'>{p.codigo}</a>")
            return format_html("<br>".join(links)) if links else "—"
        return "—"
    
    def ver_metodo(self, obj):

        if obj.instrumento and obj.instrumento.metodo_calibracao:

            metodo = obj.instrumento.metodo_calibracao

            if metodo.arquivo:

                return format_html(
                    '<a href="{}" target="_blank">{} - {}</a>',
                    metodo.arquivo.url,
                    metodo.codigo,
                    metodo.titulo
                )

        return "—"

    ver_metodo.short_description = "Ver método"

    def ver_anexo(self, obj):
        if obj.certificado_arquivo:
            return format_html(
                "<a href='{}' target='_blank'>Abrir</a>",
                obj.certificado_arquivo.url
            )
        return "—"

    ver_anexo.short_description = "Certificado"
    inlines = [CalibracaoAnexoInline]

# =========================
# ORDEM DE SERVIÇO
# =========================

@admin.register(OrdemServico)
class OrdemServicoAdmin(admin.ModelAdmin):

    list_display = (
        "numero",
        "cliente",
        "proposta",
        "status",
        "data_abertura",
        "data_conclusao",
        "total_equipamentos",
        "ver_anexo",
    )

    list_filter = (
        "status",
        "data_abertura",
        "data_conclusao",
    )

    search_fields = (
        "numero",
        "cliente__razao_social",
        "cliente__cnpj",
        "proposta__codigo",
        "instrumentos__codigo",
        "instrumentos__descricao",
    )

    autocomplete_fields = (
        "cliente",
        "proposta",
        "instrumentos",
    )

    filter_horizontal = ("instrumentos",)

    readonly_fields = (
        "data_abertura",
        "ver_anexo",
    )

    fieldsets = (
        ("Dados da Ordem de Serviço", {
            "fields": (
                "numero",
                "proposta",
                "cliente",
                "status",
                "data_abertura",
                "data_conclusao",
            )
        }),
        ("Equipamentos", {
            "description": "Selecione apenas os equipamentos relacionados a esta OS.",
            "fields": (
                "instrumentos",
            )
        }),
        ("Anexo", {
            "fields": (
                "anexo",
                "ver_anexo",
            )
        }),
    )

    def ver_anexo(self, obj):
        if obj.anexo:
            return format_html(
                "<a href='{}' target='_blank'>Abrir</a>",
                obj.anexo.url
            )
        return "—"

    ver_anexo.short_description = "Anexo"

    def total_equipamentos(self, obj):
        return obj.instrumentos.count()

    total_equipamentos.short_description = "Equipamentos"


# =========================
# PADRÃO
# =========================

@admin.register(Padrao)
class PadraoAdmin(admin.ModelAdmin):

    list_display = (
        "codigo",
        "descricao",
        "status",
        "vencimento",
        "ver_certificado",
    )

    search_fields = (
        "codigo",
        "descricao",
    )

    list_filter = (
        "status",
    )

    ordering = ("codigo",)

    def ver_certificado(self, obj):
        if obj.certificado:
            return format_html(
                "<a href='{}' target='_blank'>Abrir</a>",
                obj.certificado.url
            )
        return "—"

    ver_certificado.short_description = "Certificado"
