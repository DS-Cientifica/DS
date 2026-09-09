from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from .company import EMPRESA_CERTIFICADO
from .dilution_models import (
    PreparacaoPadrao,
    PreparacaoPadraoComponenteIncerteza,
    PreparacaoPadraoEquipamento,
    PreparacaoPadraoEtapa,
    PreparacaoPadraoResultado,
)


class DecimalPrecisoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.DecimalField):
                field.widget.attrs.update({"inputmode": "decimal", "class": "vTextField"})


class DatalistTextInput(forms.TextInput):
    """Combobox HTML: oferece valores cadastrados sem impedir um valor novo."""

    def __init__(self, options=(), datalist_id="opcoes-campo", attrs=None):
        self.options = tuple(dict.fromkeys(option for option in options if option))
        self.datalist_id = datalist_id
        attrs = {**(attrs or {}), "list": datalist_id}
        super().__init__(attrs)

    def render(self, name, value, attrs=None, renderer=None):
        input_html = super().render(name, value, attrs, renderer)
        options_html = format_html_join("", '<option value="{}"></option>', ((item,) for item in self.options))
        return format_html(
            '{}<datalist id="{}">{}</datalist>',
            input_html,
            self.datalist_id,
            options_html,
        )


class PreparacaoPadraoForm(DecimalPrecisoForm):
    class Meta:
        model = PreparacaoPadrao
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from gestao.models import Colaborador

        if "status" in self.fields:
            if self.instance and self.instance.pk and self.instance.status == "cancelado":
                self.fields["status"].choices = (("cancelado", "Cancelado"),)
            else:
                self.fields["status"].choices = tuple(
                    choice
                    for choice in PreparacaoPadrao.STATUS_CHOICES
                    if choice[0] != "aprovado"
                )
        if (
            "registro_retroativo" in self.fields
            and self.instance
            and self.instance.codigo_anterior
        ):
            self.fields["registro_retroativo"].disabled = True
            self.fields["registro_retroativo"].initial = True

        preparacoes_existentes = PreparacaoPadrao.objects.all()
        colaboradores = list(
            Colaborador.objects.filter(status="ativo").order_by("nome").values_list("nome", flat=True)
        )
        responsaveis_existentes = list(
            preparacoes_existentes.values("responsavel_preparo", "responsavel_revisao")
        )
        nomes = colaboradores + [
            nome
            for item in responsaveis_existentes
            for nome in (item["responsavel_preparo"], item["responsavel_revisao"])
            if nome
        ]
        configuracoes = {
            "unidade": (
                ("NTU", "FNU", "uH", "mg/L", "µg/L", "mS/cm", "µS/cm"),
                "diluicao-unidades",
            ),
            "matriz_diluente": (
                (
                    "Água isenta de turbidez",
                    "Água deionizada",
                    "Água destilada",
                    "Água ultrapura",
                ) + tuple(
                    preparacoes_existentes.exclude(matriz_diluente="").values_list(
                        "matriz_diluente", flat=True
                    ).distinct()
                ),
                "diluicao-matrizes",
            ),
            "condicao_armazenamento": (
                (
                    "Frasco fechado, protegido da luz, entre 15 °C e 25 °C",
                    "Frasco âmbar, protegido da luz, entre 15 °C e 25 °C",
                    "Refrigerado entre 2 °C e 8 °C",
                ) + tuple(
                    preparacoes_existentes.exclude(condicao_armazenamento="").values_list(
                        "condicao_armazenamento", flat=True
                    ).distinct()
                ),
                "diluicao-armazenamento",
            ),
            "responsavel_preparo": (nomes, "diluicao-responsaveis-preparo"),
            "responsavel_revisao": (nomes, "diluicao-responsaveis-revisao"),
        }
        for field_name, (options, datalist_id) in configuracoes.items():
            if field_name in self.fields:
                self.fields[field_name].widget = DatalistTextInput(
                    options=options,
                    datalist_id=datalist_id,
                    attrs={"placeholder": "Selecione ou digite para incluir"},
                )
        if "temperatura_preparacao" in self.fields:
            self.fields["temperatura_preparacao"].widget.attrs.update(
                {"step": "0.1", "placeholder": "Temperatura observada em °C"}
            )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("registro_retroativo"):
            if not (cleaned_data.get("justificativa_registro_retroativo") or "").strip():
                self.add_error(
                    "justificativa_registro_retroativo",
                    "Informe a justificativa do lançamento retroativo.",
                )
            if not cleaned_data.get("evidencia_registro_retroativo"):
                self.add_error(
                    "evidencia_registro_retroativo",
                    "Anexe o registro original que comprova a data da preparação.",
                )
        return cleaned_data


class PreparacaoPadraoEtapaForm(DecimalPrecisoForm):
    class Meta:
        model = PreparacaoPadraoEtapa
        fields = "__all__"


class PreparacaoPadraoResultadoForm(DecimalPrecisoForm):
    class Meta:
        model = PreparacaoPadraoResultado
        fields = "__all__"


class PreparacaoPadraoEquipamentoForm(DecimalPrecisoForm):
    class Meta:
        model = PreparacaoPadraoEquipamento
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "papel" in self.fields:
            self.fields["papel"].choices = [
                choice for choice in self.fields["papel"].choices
                if choice[0] in ("balanca", "termometro", "outro")
            ]


class PreparacaoPadraoComponenteForm(DecimalPrecisoForm):
    class Meta:
        model = PreparacaoPadraoComponenteIncerteza
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.automatico:
            for name, field in self.fields.items():
                if name != "id":
                    field.disabled = True


class InlineProtegidoAposAprovacao:
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status in ("aprovado", "cancelado"):
            return tuple(field.name for field in self.model._meta.fields if field.name not in ("id", "preparacao"))
        return super().get_readonly_fields(request, obj)

    def has_add_permission(self, request, obj=None):
        if obj and obj.status in ("aprovado", "cancelado"):
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status in ("aprovado", "cancelado"):
            return False
        return super().has_delete_permission(request, obj)


class EtapaDilucaoInline(InlineProtegidoAposAprovacao, admin.TabularInline):
    model = PreparacaoPadraoEtapa
    form = PreparacaoPadraoEtapaForm
    extra = 1
    autocomplete_fields = ("pipeta", "recipiente_final")
    fields = (
        "ordem",
        "descricao",
        "valor_entrada",
        "volume_aliquota",
        "volume_final",
        "unidade_volume",
        "pipeta",
        "recipiente_final",
        "valor_resultante",
    )
    readonly_fields = ("valor_resultante",)
    verbose_name = "Etapa de diluição"
    verbose_name_plural = "Etapas de diluição - a saída de uma etapa alimenta a próxima"


class ResultadoDilucaoInline(InlineProtegidoAposAprovacao, admin.TabularInline):
    model = PreparacaoPadraoResultado
    form = PreparacaoPadraoResultadoForm
    extra = 3
    autocomplete_fields = ("pipeta", "recipiente_final")
    fields = (
        "ordem",
        "valor_alvo",
        "volume_final",
        "unidade_volume",
        "volume_aliquota_planejado",
        "volume_diluente_aproximado",
        "volume_aliquota_utilizado",
        "pipeta",
        "recipiente_final",
        "valor_calculado",
        "incerteza_expandida",
        "fator_abrangencia",
        "padrao_gerado",
    )
    readonly_fields = (
        "volume_aliquota_planejado",
        "volume_diluente_aproximado",
        "valor_calculado",
        "incerteza_expandida",
        "fator_abrangencia",
        "padrao_gerado",
    )
    verbose_name = "Valor a preparar"
    verbose_name_plural = (
        "Gabarito de diluição - adicione 10, 100, 500 etc.; "
        "o sistema calcula a alíquota e o resultado de cada linha"
    )


class EquipamentoPreparacaoInline(InlineProtegidoAposAprovacao, admin.TabularInline):
    model = PreparacaoPadraoEquipamento
    form = PreparacaoPadraoEquipamentoForm
    extra = 0
    autocomplete_fields = ("padrao",)
    fields = (
        "ordem",
        "papel",
        "padrao",
        "valor_utilizado",
        "coeficiente_sensibilidade_manual",
        "incerteza_snapshot",
        "fator_k_snapshot",
        "resolucao_snapshot",
        "validade_snapshot",
    )
    readonly_fields = (
        "incerteza_snapshot",
        "fator_k_snapshot",
        "resolucao_snapshot",
        "validade_snapshot",
    )
    verbose_name = "Equipamento auxiliar"
    verbose_name_plural = (
        "Equipamentos auxiliares - balança, termômetro e outros; "
        "na diluição volumétrica a balança fica registrada, mas não entra na equação"
    )


class ComponenteIncertezaInline(InlineProtegidoAposAprovacao, admin.TabularInline):
    model = PreparacaoPadraoComponenteIncerteza
    form = PreparacaoPadraoComponenteForm
    extra = 1
    autocomplete_fields = ("fonte_padrao",)
    fields = (
        "ordem",
        "nome",
        "fonte_padrao",
        "tipo_valor",
        "valor_informado",
        "fator_abrangencia_origem",
        "divisor",
        "coeficiente_sensibilidade",
        "graus_liberdade",
        "incluir",
        "justificativa",
        "automatico",
        "incerteza_padrao",
        "contribuicao",
    )
    readonly_fields = ("automatico", "incerteza_padrao", "contribuicao")
    verbose_name = "Componente de incerteza"
    verbose_name_plural = "Orçamento de incerteza - componentes automáticas e complementares"


@admin.register(PreparacaoPadrao)
class PreparacaoPadraoAdmin(admin.ModelAdmin):
    form = PreparacaoPadraoForm
    change_form_template = "admin/calibracao/preparacaopadrao/change_form.html"
    list_display = (
        "codigo",
        "aplicacao",
        "data_preparacao",
        "quantidade_valores",
        "faixa_resultados",
        "validade",
        "status",
        "abrir_registro",
    )
    list_filter = ("aplicacao", "tipo_preparacao", "status", "data_preparacao", "validade")
    search_fields = (
        "codigo",
        "padrao_origem__codigo",
        "padrao_origem__descricao",
        "lote",
        "responsavel_preparo",
        "responsavel_revisao",
    )
    autocomplete_fields = ("padrao_origem", "procedimento")
    date_hierarchy = "data_preparacao"
    list_per_page = 50
    actions = ("recalcular_selecionadas", "enviar_para_revisao", "aprovar_selecionadas")
    inlines = (ResultadoDilucaoInline, EquipamentoPreparacaoInline)

    class Media:
        css = {"all": ("calibracao/css/dilution_live.css",)}
        js = ("calibracao/js/dilution_live.js",)
    fieldsets = (
        ("Identificação e rastreabilidade", {
            "fields": (
                "codigo",
                "aplicacao",
                "tipo_preparacao",
                "status",
                "data_preparacao",
                "validade",
                "padrao_origem",
                "procedimento",
                "lote",
            )
        }),
        ("Preparação", {
            "fields": (
                "unidade",
                "matriz_diluente",
                "temperatura_preparacao",
                "condicao_armazenamento",
                "responsavel_preparo",
                "responsavel_revisao",
                "observacoes",
            )
        }),
        ("Registro retroativo e aprovação", {
            "fields": (
                "registro_retroativo",
                "codigo_anterior",
                "revisao_de",
                "motivo_revisao",
                "justificativa_registro_retroativo",
                "evidencia_registro_retroativo",
                "registrado_retroativamente_por",
                "registrado_retroativamente_em",
                "pendencias_aprovacao_exibicao",
            )
        }),
        ("Resumo metrológico legado", {
            "classes": ("collapse",),
            "fields": (
                "valor_atribuido",
                "incerteza_padrao_combinada",
                "graus_liberdade_efetivos",
                "fator_abrangencia",
                "incerteza_expandida",
                "padrao_gerado",
                "aprovado_por",
                "aprovado_em",
            )
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        calculados = (
            "codigo",
            "valor_atribuido",
            "incerteza_padrao_combinada",
            "graus_liberdade_efetivos",
            "fator_abrangencia",
            "incerteza_expandida",
            "padrao_gerado",
            "aprovado_por",
            "aprovado_em",
            "registrado_retroativamente_por",
            "registrado_retroativamente_em",
            "codigo_anterior",
            "revisao_de",
            "pendencias_aprovacao_exibicao",
        )
        if obj is None:
            return ("status",) + calculados
        if obj and obj.status in ("aprovado", "cancelado"):
            return tuple(
                field.name
                for field in self.model._meta.fields
                if field.name not in ("id",)
            ) + ("pendencias_aprovacao_exibicao",)
        return calculados

    def save_model(self, request, obj, form, change):
        if obj.registro_retroativo and not obj.registrado_retroativamente_por_id:
            obj.registrado_retroativamente_por = request.user
            obj.registrado_retroativamente_em = timezone.now()
        super().save_model(request, obj, form, change)

    @admin.display(description="Pendências para aprovação")
    def pendencias_aprovacao_exibicao(self, obj):
        if not obj or not obj.pk:
            return "Salve a preparação para verificar as pendências."
        pendencias = obj.pendencias_aprovacao()
        if not pendencias:
            return format_html(
                '<span style="color:#198754;font-weight:600">{}</span>',
                "Sem pendências.",
            )
        return format_html_join(mark_safe("<br>"), "• {}", ((item,) for item in pendencias))

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status in ("aprovado", "cancelado"):
            return False
        return super().has_delete_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "procedimento":
            kwargs["queryset"] = db_field.remote_field.model.objects.filter(
                tipo__in=("procedimento", "instrucao", "metodo"),
                status="vigente",
            ).order_by("codigo", "titulo")
        if db_field.name == "padrao_origem":
            kwargs["queryset"] = db_field.remote_field.model.objects.filter(
                status="valido"
            ).order_by("codigo")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        preparacao = form.instance
        if preparacao.status != "aprovado":
            preparacao.recalcular()

    @admin.display(description="Valor atribuído")
    def valor_atribuido_formatado(self, obj):
        if obj.valor_atribuido is None:
            return "—"
        return f"{obj.valor_atribuido} {obj.unidade}"

    @admin.display(description="Valores")
    def quantidade_valores(self, obj):
        return obj.resultados.count()

    @admin.display(description="Faixa preparada")
    def faixa_resultados(self, obj):
        valores = list(obj.resultados.values_list("valor_calculado", flat=True))
        valores = [valor for valor in valores if valor is not None]
        if not valores:
            return "—"
        return f"{min(valores)} a {max(valores)} {obj.unidade}" if len(valores) > 1 else f"{valores[0]} {obj.unidade}"

    @admin.display(description="U")
    def incerteza_expandida_formatada(self, obj):
        if obj.incerteza_expandida is None:
            return "—"
        return f"{obj.incerteza_expandida} {obj.unidade}"

    @admin.display(description="Registro")
    def abrir_registro(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("admin:calibracao_preparacaopadrao_registro", args=(obj.pk,))
        return format_html('<a href="{}" target="_blank">Abrir registro</a>', url)

    @admin.action(description="Recalcular preparações selecionadas")
    def recalcular_selecionadas(self, request, queryset):
        total = 0
        for preparacao in queryset.exclude(status="aprovado"):
            preparacao.recalcular()
            total += 1
        self.message_user(request, f"{total} preparação(ões) recalculada(s).", messages.SUCCESS)

    @admin.action(description="Enviar preparações selecionadas para revisão")
    def enviar_para_revisao(self, request, queryset):
        total = queryset.filter(status="rascunho").update(status="em_revisao")
        self.message_user(request, f"{total} preparação(ões) enviada(s) para revisão.", messages.SUCCESS)

    @admin.action(description="Aprovar e gerar padrões preparados")
    def aprovar_selecionadas(self, request, queryset):
        aprovadas = 0
        erros = []
        for preparacao in queryset.exclude(status__in=("aprovado", "cancelado")):
            try:
                preparacao.aprovar(request.user)
                aprovadas += 1
            except ValidationError as exc:
                erros.append(f"{preparacao.codigo}: {'; '.join(exc.messages)}")
        if aprovadas:
            self.message_user(
                request,
                f"{aprovadas} preparação(ões) aprovada(s) e disponibilizada(s) como padrão.",
                messages.SUCCESS,
            )
        for erro in erros:
            self.message_user(request, erro, messages.ERROR)

    def get_urls(self):
        return [
            path(
                "padrao-dados/",
                self.admin_site.admin_view(self.padrao_dados_view),
                name="calibracao_preparacaopadrao_padrao_dados",
            ),
            path(
                "<int:object_id>/registro/",
                self.admin_site.admin_view(self.registro_view),
                name="calibracao_preparacaopadrao_registro",
            ),
            path(
                "<int:object_id>/aprovar/",
                self.admin_site.admin_view(self.aprovar_view),
                name="calibracao_preparacaopadrao_aprovar",
            ),
            path(
                "<int:object_id>/duplicar/",
                self.admin_site.admin_view(self.duplicar_view),
                name="calibracao_preparacaopadrao_duplicar",
            ),
        ] + super().get_urls()

    def duplicar_view(self, request, object_id):
        preparacao = get_object_or_404(PreparacaoPadrao, pk=object_id)
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method != "POST":
            return redirect(reverse("admin:calibracao_preparacaopadrao_change", args=(object_id,)))
        copia = preparacao.duplicar_como_rascunho()
        self.message_user(
            request,
            f"Preparação duplicada como rascunho {copia.codigo}. Revise os dados de execução.",
            messages.SUCCESS,
        )
        return redirect(reverse("admin:calibracao_preparacaopadrao_change", args=(copia.pk,)))

    def aprovar_view(self, request, object_id):
        preparacao = get_object_or_404(PreparacaoPadrao, pk=object_id)
        if not self.has_change_permission(request, preparacao):
            raise PermissionDenied
        if request.method != "POST":
            return redirect(reverse("admin:calibracao_preparacaopadrao_change", args=(object_id,)))
        try:
            preparacao.aprovar(request.user)
        except ValidationError as exc:
            for erro in exc.messages:
                self.message_user(request, erro, messages.ERROR)
        else:
            self.message_user(
                request,
                "Preparação aprovada e padrões preparados gerados com rastreabilidade.",
                messages.SUCCESS,
            )
        return redirect(reverse("admin:calibracao_preparacaopadrao_change", args=(object_id,)))

    def padrao_dados_view(self, request):
        padrao_id = request.GET.get("id")
        if not padrao_id:
            return JsonResponse({"erro": "Padrão não informado."}, status=400)
        from .models import Padrao

        padrao = get_object_or_404(Padrao, pk=padrao_id)
        return JsonResponse(
            {
                "id": str(padrao.pk),
                "codigo": padrao.codigo,
                "descricao": padrao.descricao,
                "valor_nominal": str(padrao.valor_nominal) if padrao.valor_nominal is not None else None,
                "unidade": padrao.unidade,
                "incerteza": str(padrao.incerteza) if padrao.incerteza is not None else None,
                "fator_k": str(padrao.fator_k) if padrao.fator_k is not None else None,
                "resolucao": str(padrao.resolucao) if padrao.resolucao is not None else None,
                "validade": padrao.vencimento.isoformat(),
            }
        )

    def registro_view(self, request, object_id):
        preparacao = get_object_or_404(
            PreparacaoPadrao.objects.select_related(
                "padrao_origem", "procedimento", "padrao_gerado", "aprovado_por"
            ).prefetch_related(
                "etapas__pipeta",
                "etapas__recipiente_final",
                "resultados__pipeta",
                "resultados__recipiente_final",
                "resultados__padrao_gerado",
                "equipamentos__padrao",
                "componentes__fonte_padrao",
            ),
            pk=object_id,
        )
        return render(
            request,
            "calibracao/preparacao_padrao_registro.html",
            {
                "preparacao": preparacao,
                "empresa": EMPRESA_CERTIFICADO,
                "title": f"Registro {preparacao.codigo}",
            },
        )
