from django.contrib import admin

from .models import CargoFuncao, Colaborador, ColaboradorAnexo, CompetenciaTecnica, Treinamento


class ColaboradorAnexoInline(admin.TabularInline):
    model = ColaboradorAnexo
    extra = 0
    fields = ("titulo", "tipo", "arquivo", "data_documento", "descricao")


@admin.register(CargoFuncao)
class CargoFuncaoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "ativo")
    list_filter = ("ativo",)
    search_fields = ("codigo", "nome", "descricao")
    ordering = ("nome",)


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
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
    autocomplete_fields = ("cargo",)
    readonly_fields = ("codigo",)
    ordering = ("nome",)
    inlines = [ColaboradorAnexoInline]
    fieldsets = (
        ("Identifica\u00e7\u00e3o", {"fields": ("codigo", "nome", "tipo", "cargo", "status")}),
        ("Contato", {"fields": ("telefone", "email", "cidade_base")}),
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


@admin.register(CompetenciaTecnica)
class CompetenciaTecnicaAdmin(admin.ModelAdmin):
    list_display = (
        "colaborador",
        "grandeza",
        "nivel",
        "autorizado_executar",
        "necessita_supervisao",
        "validade_habilitacao",
    )
    list_filter = ("nivel", "autorizado_executar", "necessita_supervisao")
    search_fields = ("colaborador__nome", "grandeza", "observacoes")
    autocomplete_fields = ("colaborador", "documento_vinculado")
    ordering = ("colaborador__nome", "grandeza")


@admin.register(Treinamento)
class TreinamentoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "colaborador", "treinamento", "tipo", "data", "validade", "status")
    list_filter = ("tipo", "status", "data", "validade")
    search_fields = ("codigo", "colaborador__nome", "treinamento", "instrutor", "observacoes")
    autocomplete_fields = ("colaborador",)
    readonly_fields = ("codigo",)
    ordering = ("-data", "treinamento")
