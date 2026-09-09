from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils.html import format_html

from qualidade.models import Documento

from .sphyg_models import (
    CalibracaoEsfigmomanometro,
    EsfigmomanometroEnsaioVazamento,
    EsfigmomanometroIncertezaPonto,
    EsfigmomanometroPadraoUtilizado,
    EsfigmomanometroPonto,
)
from .admin_mixins import OrdemServicoAutomaticaAdminMixin


class EmittedCalibrationAdminMixin:
    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.status == "emitida":
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.status == "emitida":
            return False
        return super().has_delete_permission(request, obj)


class EmittedCalibrationChildAdminMixin:
    @staticmethod
    def _locked(obj):
        return bool(obj and obj.calibracao_id and obj.calibracao.status == "emitida")

    def has_change_permission(self, request, obj=None):
        if self._locked(obj):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if self._locked(obj):
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if self._locked(obj):
            raise PermissionDenied("Calibração emitida exige revisão controlada.")
        return super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "calibracao":
            kwargs["queryset"] = CalibracaoEsfigmomanometro.objects.exclude(status="emitida")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class SphygDecimalForm(forms.ModelForm):
    class Meta:
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.DecimalField):
                field.localize = True
                field.widget = forms.TextInput(attrs={
                    **field.widget.attrs, "inputmode": "decimal", "data-decimal-places": "6"
                })

    def clean(self):
        cleaned = super().clean()
        for name, field in self.fields.items():
            value = cleaned.get(name)
            if isinstance(field, forms.DecimalField) and value not in (None, ""):
                try:
                    cleaned[name] = Decimal(str(value))
                except (InvalidOperation, TypeError, ValueError):
                    pass
        return cleaned


class CalibracaoEsfigmomanometroForm(SphygDecimalForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "procedimento_documento" in self.fields:
            self.fields["procedimento_documento"].queryset = Documento.objects.filter(
                tipo__in=("procedimento", "instrucao", "metodo"), status="vigente"
            ).order_by("codigo", "titulo")

    def clean(self):
        cleaned = super().clean()
        context = cleaned.get("contexto_criterio")
        decision_rule = cleaned.get("regra_decisao")
        if decision_rule != "sem_declaracao" and context == "sem_criterio":
            self.add_error("contexto_criterio", "Selecione o critério antes de declarar conformidade.")
        if context == "personalizado" and cleaned.get("tolerancia_personalizada") is None:
            self.add_error("tolerancia_personalizada", "Informe a tolerância personalizada.")
        return cleaned


class PadraoInline(admin.TabularInline):
    model = EsfigmomanometroPadraoUtilizado
    form = SphygDecimalForm
    extra = 1
    autocomplete_fields = ("padrao",)
    readonly_fields = (
        "codigo", "descricao", "numero_certificado", "laboratorio_emitente",
        "data_calibracao", "validade", "resolucao", "incerteza_expandida",
        "fator_k", "graus_liberdade", "unidade", "situacao_na_data",
    )
    fields = (
        "ordem", "padrao", "codigo", "descricao", "numero_certificado",
        "laboratorio_emitente", "data_calibracao", "validade", "resolucao",
        "incerteza_expandida", "fator_k", "graus_liberdade", "unidade", "situacao_na_data",
    )


class PontoInline(admin.TabularInline):
    model = EsfigmomanometroPonto
    form = SphygDecimalForm
    extra = 5
    readonly_fields = (
        "media_crescente_fmt", "media_decrescente_fmt", "erro_crescente_fmt",
        "erro_decrescente_fmt", "correcao_crescente_fmt", "correcao_decrescente_fmt",
        "histerese_fmt", "repetitividade_fmt", "tolerancia_fmt", "resultado",
    )
    fields = (
        "ordem", "pressao_referencia", "crescente_1", "crescente_2", "crescente_3",
        "decrescente_1", "decrescente_2", "decrescente_3", "media_crescente_fmt",
        "media_decrescente_fmt", "erro_crescente_fmt", "erro_decrescente_fmt",
        "correcao_crescente_fmt", "correcao_decrescente_fmt", "histerese_fmt",
        "repetitividade_fmt", "tolerancia_fmt", "resultado",
        "observacoes",
    )

    def _fmt(self, obj, value):
        return obj.calibracao.formatar_por_resolucao(value) if obj and obj.pk else "—"

    @admin.display(description="Média crescente")
    def media_crescente_fmt(self, obj): return self._fmt(obj, obj.media_crescente)
    @admin.display(description="Média decrescente")
    def media_decrescente_fmt(self, obj): return self._fmt(obj, obj.media_decrescente)
    @admin.display(description="Erro crescente")
    def erro_crescente_fmt(self, obj): return self._fmt(obj, obj.erro_crescente)
    @admin.display(description="Erro decrescente")
    def erro_decrescente_fmt(self, obj): return self._fmt(obj, obj.erro_decrescente)
    @admin.display(description="Correção crescente")
    def correcao_crescente_fmt(self, obj): return self._fmt(obj, obj.correcao_crescente)
    @admin.display(description="Correção decrescente")
    def correcao_decrescente_fmt(self, obj): return self._fmt(obj, obj.correcao_decrescente)
    @admin.display(description="Histerese")
    def histerese_fmt(self, obj): return self._fmt(obj, obj.histerese)
    @admin.display(description="Repetitividade")
    def repetitividade_fmt(self, obj): return self._fmt(obj, obj.repetitividade)
    @admin.display(description="Tolerância")
    def tolerancia_fmt(self, obj): return self._fmt(obj, obj.tolerancia)


class IncertezaInline(admin.TabularInline):
    model = EsfigmomanometroIncertezaPonto
    form = SphygDecimalForm
    extra = 1
    readonly_fields = (
        "u_repetitividade_fmt", "u_resolucao_instrumento_fmt", "u_resolucao_padrao_fmt",
        "u_certificado_padrao_fmt", "u_deriva_padrao_fmt", "incerteza_padrao_combinada_fmt",
        "incerteza_expandida_fmt", "componentes_incluidos",
    )
    fields = (
        "ordem", "componentes_incluidos", "resolucao_instrumento",
        "incerteza_certificado_padrao", "fator_k_certificado_padrao",
        "incluir_resolucao_padrao", "resolucao_padrao",
        "incluir_deriva_padrao", "limite_deriva_padrao",
        "u_repetitividade_fmt", "u_resolucao_instrumento_fmt", "u_resolucao_padrao_fmt",
        "u_certificado_padrao_fmt", "u_deriva_padrao_fmt", "u_outros", "outros_descricao",
        "incerteza_padrao_combinada_fmt", "fator_k", "graus_liberdade", "incerteza_expandida_fmt",
    )

    def _fmt(self, obj, value):
        return obj.calibracao.formatar_por_resolucao(value) if obj and obj.pk else "—"

    @admin.display(description="u repetitividade")
    def u_repetitividade_fmt(self, obj): return self._fmt(obj, obj.u_repetitividade)
    @admin.display(description="u resolução instrumento")
    def u_resolucao_instrumento_fmt(self, obj): return self._fmt(obj, obj.u_resolucao_instrumento)
    @admin.display(description="u resolução padrão")
    def u_resolucao_padrao_fmt(self, obj): return self._fmt(obj, obj.u_resolucao_padrao)
    @admin.display(description="u certificado padrão")
    def u_certificado_padrao_fmt(self, obj): return self._fmt(obj, obj.u_certificado_padrao)
    @admin.display(description="u deriva padrão")
    def u_deriva_padrao_fmt(self, obj): return self._fmt(obj, obj.u_deriva_padrao)
    @admin.display(description="u combinada")
    def incerteza_padrao_combinada_fmt(self, obj): return self._fmt(obj, obj.incerteza_padrao_combinada)
    @admin.display(description="U expandida")
    def incerteza_expandida_fmt(self, obj): return self._fmt(obj, obj.incerteza_expandida)


class VazamentoInline(admin.TabularInline):
    model = EsfigmomanometroEnsaioVazamento
    form = SphygDecimalForm
    extra = 1
    readonly_fields = ("taxa_vazamento", "limite_resolvido", "resultado")
    fields = (
        "ordem", "pressao_inicial", "pressao_final", "duracao_minutos",
        "taxa_vazamento", "limite_personalizado", "limite_resolvido", "resultado", "observacoes",
    )


@admin.register(CalibracaoEsfigmomanometro)
class CalibracaoEsfigmomanometroAdmin(
    OrdemServicoAutomaticaAdminMixin,
    EmittedCalibrationAdminMixin,
    admin.ModelAdmin,
):
    form = CalibracaoEsfigmomanometroForm
    list_display = (
        "numero_certificado", "tecnologia", "instrumento", "cliente", "data_calibracao",
        "status", "resultado_final", "certificado_link",
    )
    list_filter = ("tecnologia", "aplicacao", "status", "resultado_final", "data_calibracao")
    search_fields = (
        "numero_certificado", "ordem_servico", "instrumento__codigo", "instrumento__tag",
        "cliente__razao_social", "tag", "numero_serie",
    )
    autocomplete_fields = (
        "instrumento", "cliente", "procedimento_documento", "responsavel_tecnico", "tecnico_executante",
    )
    readonly_fields = (
        "resultado_final", "tolerancia_resolvida_admin", "pendencias_emissao_admin",
        "alerta_metrologia_legal", "certificado_link",
    )
    inlines = (PadraoInline, PontoInline, IncertezaInline, VazamentoInline)

    class Media:
        css = {"all": ("css/padrao_autofill.css",)}
        js = ("js/calibracao_ordem_servico.js", "js/padrao_autofill.js")
    save_on_top = True
    fieldsets = (
        ("Identificação e controle", {"fields": (
            "tecnologia", "aplicacao", "tipo_servico", "status", "numero_certificado",
            "ordem_servico", "data_calibracao", "data_emissao", "proxima_calibracao",
            "revisao", "local_calibracao", "alerta_metrologia_legal",
            "pendencias_emissao_admin", "certificado_link",
        )}),
        ("Cliente e instrumento", {"fields": (
            "instrumento", "cliente", "contratante", "endereco_cliente", "tag", "fabricante",
            "modelo", "numero_serie", "ano_fabricacao", "faixa_medicao", "resolucao", "unidade",
        )}),
        ("Braçadeira e manguito", {"fields": (
            "identificacao_brachadeira", "circunferencia_minima_cm", "circunferencia_maxima_cm",
            "marcacao_arteria_conforme", "integridade_brachadeira_manguito",
        )}),
        ("Controle metrológico legal", {"fields": (
            "portaria_aprovacao_modelo", "marca_aprovacao_modelo", "identificacao_marca_verificacao",
            "data_ultima_verificacao_legal", "data_proxima_verificacao_legal",
        )}),
        ("Configuração digital", {"fields": (
            "modo_manometro", "adaptador_conexao", "fonte_alimentacao",
        )}),
        ("Método e ambiente", {"fields": (
            "procedimento_documento", "procedimento_numero", "procedimento_revisao", "referencias",
            "temperatura_inicial", "temperatura_final", "umidade_inicial", "umidade_final",
            "justificativa_condicoes",
        )}),
        ("Critério e regra de decisão", {"fields": (
            "contexto_criterio", "tolerancia_personalizada", "tolerancia_resolvida_admin",
            "criterio_origem", "criterio_referencia", "regra_decisao", "resultado_final",
        )}),
        ("Ensaios funcionais", {"fields": (
            "exame_geral", "ajuste_zero", "interrupcao_imediata", "ensaio_vazamento_aplicavel",
            "justificativa_vazamento_nao_aplicavel", "observacoes_exame",
        )}),
        ("Responsáveis e observações", {"fields": (
            "tecnico_executante", "responsavel_tecnico", "observacoes_certificado",
        )}),
    )

    @admin.display(description="Alerta de metrologia legal")
    def alerta_metrologia_legal(self, obj):
        return format_html(
            '<div style="padding:8px;border:1px solid #d59a00;background:#fff8df;color:#6b4d00">'
            '<strong>Calibração não substitui verificação legal.</strong> A verificação anual e a verificação '
            'após reparo devem ser realizadas perante a RBMLQ-I. Não use este certificado como marca ou '
            'certificado de verificação do Inmetro.</div>'
        )

    @admin.display(description="Tolerância resolvida")
    def tolerancia_resolvida_admin(self, obj):
        if not obj or obj.tolerancia_resolvida is None:
            return "—"
        return f"± {obj.tolerancia_resolvida} {obj.unidade}"

    @admin.display(description="Pendências para emissão")
    def pendencias_emissao_admin(self, obj):
        if not obj or not obj.pk:
            return "Salve o registro para avaliar as pendências relacionadas."
        pending = obj.pendencias_emissao()
        if not pending:
            return format_html('<span style="color:#157347;font-weight:700">Sem pendências.</span>')
        return format_html('<span style="color:#b42318;font-weight:700">{}</span>', " • ".join(pending))

    @admin.display(description="Certificado")
    def certificado_link(self, obj):
        if not obj or not obj.pk:
            return "—"
        return format_html(
            '<a class="button" href="{}" target="_blank" rel="noopener">Visualizar / imprimir</a>',
            reverse("pdf_calibracao_esfigmomanometro", args=(obj.pk,)),
        )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.recalcular_resultado(save=True)
        pending = form.instance.pendencias_emissao()
        if pending:
            messages.warning(request, "Pendências para emissão: " + "; ".join(pending))
            if form.instance.status == "emitida":
                form.instance.status = "concluida"
                form.instance.save(update_fields=("status", "updated_at"))
                messages.error(request, "A emissão foi bloqueada; o registro permaneceu como Concluída.")


@admin.register(EsfigmomanometroPadraoUtilizado)
class EsfigmomanometroPadraoAdmin(EmittedCalibrationChildAdminMixin, admin.ModelAdmin):
    list_display = ("calibracao", "ordem", "codigo", "numero_certificado", "situacao_na_data")
    search_fields = ("codigo", "numero_certificado", "calibracao__numero_certificado")
    autocomplete_fields = ("calibracao", "padrao")


@admin.register(EsfigmomanometroPonto)
class EsfigmomanometroPontoAdmin(EmittedCalibrationChildAdminMixin, admin.ModelAdmin):
    list_display = (
        "calibracao", "ordem", "pressao_referencia", "erro_crescente", "erro_decrescente",
        "histerese", "resultado",
    )
    list_filter = ("resultado",)
    search_fields = ("calibracao__numero_certificado", "calibracao__instrumento__codigo")
    autocomplete_fields = ("calibracao",)


@admin.register(EsfigmomanometroIncertezaPonto)
class EsfigmomanometroIncertezaAdmin(EmittedCalibrationChildAdminMixin, admin.ModelAdmin):
    list_display = ("calibracao", "ordem", "incerteza_padrao_combinada", "fator_k", "incerteza_expandida")
    search_fields = ("calibracao__numero_certificado", "calibracao__instrumento__codigo")
    autocomplete_fields = ("calibracao",)


@admin.register(EsfigmomanometroEnsaioVazamento)
class EsfigmomanometroVazamentoAdmin(EmittedCalibrationChildAdminMixin, admin.ModelAdmin):
    list_display = (
        "calibracao", "ordem", "taxa_vazamento", "limite_resolvido", "resultado",
    )
    search_fields = ("calibracao__numero_certificado", "calibracao__instrumento__codigo")
    autocomplete_fields = ("calibracao",)
