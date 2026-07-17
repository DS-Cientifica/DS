from django.contrib import admin
from django import forms

from .models import CargoFuncao, Colaborador, ColaboradorAnexo, CompetenciaTecnica, DocumentoEmpresa, Treinamento


class ColaboradorAnexoInline(admin.TabularInline):
    model = ColaboradorAnexo
    extra = 0
    fields = ("titulo", "tipo", "arquivo", "data_documento", "descricao")


class CompetenciaTecnicaInline(admin.TabularInline):
    model = CompetenciaTecnica
    extra = 0
    fields = (
        "grandeza",
        "nivel",
        "autorizado_executar",
        "necessita_supervisao",
        "data_habilitacao",
        "validade_habilitacao",
        "documento_vinculado",
        "observacoes",
    )
    autocomplete_fields = ("documento_vinculado",)


class ColaboradorAdminForm(forms.ModelForm):
    class Meta:
        model = Colaborador
        fields = "__all__"
        labels = {
            "cargo": "Cargo/Função",
        }


@admin.register(CargoFuncao)
class CargoFuncaoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "ativo")
    list_filter = ("ativo",)
    search_fields = ("codigo", "nome", "descricao")
    ordering = ("nome",)

    def get_model_perms(self, request):
        return {}


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    form = ColaboradorAdminForm
    list_display = (
        "codigo",
        "nome",
        "tipo",
        "cargo",
        "status",
        "cidade_base",
        "valor_hora_interna",
        "valor_hora_venda",
        "disponivel_campo",
    )
    list_filter = ("tipo", "status", "disponivel_campo", "cargo")
    search_fields = ("codigo", "nome", "telefone", "email", "cidade_base", "observacoes")
    readonly_fields = ("codigo",)
    ordering = ("nome",)
    inlines = [CompetenciaTecnicaInline, ColaboradorAnexoInline]
    fieldsets = (
        ("Identifica\u00e7\u00e3o e vínculo", {"fields": ("codigo", "nome", "tipo", "cargo", "status")}),
        ("Contato", {"fields": ("telefone", "email", "cidade_base")}),
        ("Competências e evidências", {"fields": ()}),
        (
            "Custos e disponibilidade",
            {
                "fields": (
                    ("valor_hora_interna", "valor_hora_venda"),
                    "custo_diaria",
                    "disponivel_campo",
                )
            },
        ),
        ("Observa\u00e7\u00f5es", {"fields": ("observacoes",)}),
    )


@admin.register(Treinamento)
class TreinamentoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "colaborador", "treinamento", "tipo", "data", "validade", "status")
    list_filter = ("tipo", "status", "data", "validade")
    search_fields = ("codigo", "colaborador__nome", "treinamento", "instrutor", "observacoes")
    autocomplete_fields = ("colaborador",)
    readonly_fields = ("codigo",)
    ordering = ("-data", "treinamento")


@admin.register(DocumentoEmpresa)
class DocumentoEmpresaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "titulo", "tipo", "numero_identificacao", "validade", "status", "ativo")
    list_filter = ("tipo", "status", "ativo", "validade")
    search_fields = ("codigo", "titulo", "numero_identificacao", "orgao_emissor", "observacoes")
    readonly_fields = ("codigo", "created_at", "updated_at")
    ordering = ("titulo",)
    fieldsets = (
        ("Identificação", {"fields": ("codigo", "titulo", "tipo", "ativo")}),
        (
            "Dados do documento",
            {"fields": ("numero_identificacao", "orgao_emissor", ("data_emissao", "validade"), "status")},
        ),
        ("Arquivo", {"fields": ("arquivo",)}),
        ("Observações", {"fields": ("observacoes",)}),
        ("Controle", {"fields": ("created_at", "updated_at")}),
    )
