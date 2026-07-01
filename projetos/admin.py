from django.contrib import admin
from django.utils.html import format_html

from .models import (
    CampanhaMarketing,
    MidiaMarketing,
    Projeto,
    ProjetoArquivo,
    ProjetoCusto,
    ProjetoTarefa,
    ProjetoTeste,
)


class HiddenFromMenuAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        return {}


class ProjetoTarefaInline(admin.TabularInline):
    model = ProjetoTarefa
    extra = 0
    fields = ("ordem", "titulo", "responsavel", "prazo", "status")


class ProjetoCustoInline(admin.TabularInline):
    model = ProjetoCusto
    extra = 0
    fields = ("descricao", "custo_componentes", "horas_tecnicas", "valor_hora_tecnica", "preco_estimado_venda", "viabilidade")


class ProjetoTesteInline(admin.TabularInline):
    model = ProjetoTeste
    extra = 0
    fields = ("tipo_teste", "data_teste", "padrao", "resultado")
    autocomplete_fields = ("padrao", "documento_tecnico")


class ProjetoArquivoInline(admin.TabularInline):
    model = ProjetoArquivo
    extra = 0
    fields = ("titulo", "tipo_arquivo", "arquivo", "responsavel")


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    change_form_template = "admin/projetos/projeto/change_form.html"
    list_display = (
        "codigo",
        "nome",
        "tipo",
        "area",
        "status_badge",
        "prioridade_badge",
        "cliente",
        "responsavel",
        "previsao_conclusao",
    )
    list_filter = ("tipo", "area", "status", "prioridade", "responsavel", "cliente")
    search_fields = ("codigo", "nome", "cliente__codigo", "cliente__razao_social", "objetivo", "justificativa")
    autocomplete_fields = ("cliente", "responsavel", "produto_servico_gerado")
    readonly_fields = ("codigo",)
    ordering = ("-created_at", "nome")
    inlines = [ProjetoTarefaInline, ProjetoCustoInline, ProjetoTesteInline, ProjetoArquivoInline]

    fieldsets = (
        ("Identificacao", {"fields": ("codigo", "nome", "tipo", "area", "status", "prioridade")}),
        ("Responsabilidade", {"fields": ("responsavel", "cliente", "produto_servico_gerado")}),
        ("Escopo", {"fields": ("objetivo", "justificativa", "resultado_esperado")}),
        ("Cronograma e custo", {"fields": (("data_inicio", "previsao_conclusao"), ("orcamento_previsto", "custo_real"))}),
    )

    def status_badge(self, obj):
        cores = {
            "ideia": "#64748b",
            "em_analise": "#1d4ed8",
            "aprovado_desenvolvimento": "#0f766e",
            "em_desenvolvimento": "#2563eb",
            "aguardando_compra": "#b45309",
            "em_teste": "#7c3aed",
            "em_validacao": "#0f766e",
            "aprovado": "#15803d",
            "reprovado": "#b91c1c",
            "cancelado": "#991b1b",
            "liberado_comercialmente": "#166534",
        }
        return format_html(
            "<span style='background:{};color:#fff;padding:4px 8px;border-radius:999px;font-weight:700;'>{}</span>",
            cores.get(obj.status, "#475569"),
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def prioridade_badge(self, obj):
        cores = {
            "baixa": ("#e2e8f0", "#334155"),
            "media": ("#dbeafe", "#1d4ed8"),
            "alta": ("#fef3c7", "#92400e"),
            "urgente": ("#fee2e2", "#991b1b"),
        }
        fundo, texto = cores.get(obj.prioridade, ("#e2e8f0", "#334155"))
        return format_html(
            "<span style='background:{};color:{};padding:4px 8px;border-radius:999px;font-weight:700;'>{}</span>",
            fundo,
            texto,
            obj.get_prioridade_display(),
        )

    prioridade_badge.short_description = "Prioridade"


@admin.register(ProjetoTarefa)
class ProjetoTarefaAdmin(HiddenFromMenuAdmin):
    list_display = ("projeto", "ordem", "titulo", "responsavel", "prazo", "status")
    list_filter = ("status", "responsavel", "projeto")
    search_fields = ("projeto__codigo", "projeto__nome", "titulo", "descricao")
    autocomplete_fields = ("projeto", "responsavel")
    ordering = ("projeto__codigo", "ordem", "prazo")


@admin.register(ProjetoTeste)
class ProjetoTesteAdmin(HiddenFromMenuAdmin):
    list_display = ("projeto", "tipo_teste", "data_teste", "padrao", "resultado")
    list_filter = ("resultado", "data_teste")
    search_fields = ("projeto__codigo", "projeto__nome", "tipo_teste", "observacao_tecnica")
    autocomplete_fields = ("projeto", "padrao", "documento_tecnico")
    ordering = ("-data_teste",)


@admin.register(ProjetoCusto)
class ProjetoCustoAdmin(HiddenFromMenuAdmin):
    list_display = ("projeto", "descricao", "custo_componentes", "custo_desenvolvimento", "custo_total", "preco_estimado_venda", "viabilidade")
    list_filter = ("viabilidade", "projeto")
    search_fields = ("projeto__codigo", "projeto__nome", "descricao")
    autocomplete_fields = ("projeto",)
    ordering = ("projeto__codigo", "-created_at")


@admin.register(ProjetoArquivo)
class ProjetoArquivoAdmin(HiddenFromMenuAdmin):
    list_display = ("projeto", "titulo", "tipo_arquivo", "responsavel", "created_at")
    list_filter = ("tipo_arquivo", "responsavel")
    search_fields = ("projeto__codigo", "projeto__nome", "titulo", "tags")
    autocomplete_fields = ("projeto", "responsavel")
    ordering = ("-created_at",)


class MidiaMarketingInline(admin.TabularInline):
    model = MidiaMarketing
    extra = 0
    fields = ("titulo", "tipo", "categoria", "canal_sugerido", "arquivo")


@admin.register(CampanhaMarketing)
class CampanhaMarketingAdmin(admin.ModelAdmin):
    change_form_template = "admin/projetos/campanhamarketing/change_form.html"
    list_display = ("codigo", "nome", "tipo", "status", "projeto", "produto_servico", "responsavel", "data_inicio", "data_final")
    list_filter = ("tipo", "status", "responsavel")
    search_fields = ("codigo", "nome", "objetivo", "publico_alvo", "projeto__codigo", "projeto__nome")
    autocomplete_fields = ("produto_servico", "projeto", "responsavel")
    readonly_fields = ("codigo",)
    inlines = [MidiaMarketingInline]
    ordering = ("-created_at", "nome")

    fieldsets = (
        ("Identificacao", {"fields": ("codigo", "nome", "tipo", "status")}),
        ("Vinculos", {"fields": ("projeto", "produto_servico", "responsavel")}),
        ("Planejamento", {"fields": ("objetivo", "publico_alvo", ("data_inicio", "data_final"), "orcamento", "observacoes")}),
    )


@admin.register(MidiaMarketing)
class MidiaMarketingAdmin(HiddenFromMenuAdmin):
    list_display = ("titulo", "tipo", "categoria", "canal_sugerido", "campanha", "projeto", "uso_autorizado", "created_at")
    list_filter = ("tipo", "categoria", "canal_sugerido", "uso_autorizado")
    search_fields = ("titulo", "tags", "campanha__codigo", "campanha__nome", "projeto__codigo", "projeto__nome")
    autocomplete_fields = ("campanha", "projeto", "responsavel")
    ordering = ("-created_at", "titulo")
