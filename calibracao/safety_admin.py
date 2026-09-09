from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils.html import format_html

from qualidade.models import Documento

from .safety_models import (
    CalibracaoDispositivoSegurancaPressao,
    DispositivoSegurancaIncertezaPonto,
    DispositivoSegurancaPadraoUtilizado,
    DispositivoSegurancaPonto,
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
            kwargs["queryset"] = CalibracaoDispositivoSegurancaPressao.objects.exclude(
                status="emitida"
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class SafetyDecimalForm(forms.ModelForm):
    class Meta:
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.DecimalField):
                field.localize = True
                field.widget = forms.TextInput(attrs={
                    **field.widget.attrs, "inputmode": "decimal", "data-decimal-places": "9"
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


class CalibracaoDispositivoSegurancaForm(SafetyDecimalForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "procedimento_documento" in self.fields:
            self.fields["procedimento_documento"].queryset = Documento.objects.filter(
                tipo__in=("procedimento", "instrucao", "metodo"), status="vigente"
            ).order_by("codigo", "titulo")


class PadraoUtilizadoInline(admin.TabularInline):
    model = DispositivoSegurancaPadraoUtilizado
    form = SafetyDecimalForm
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
    model = DispositivoSegurancaPonto
    form = SafetyDecimalForm
    extra = 2
    readonly_fields = (
        "media_atuacao", "media_rearme", "erro", "correcao", "repetitividade",
        "desvio_padrao", "histerese", "tolerancia_resolvida", "resultado",
    )
    fields = (
        "ordem", "condicao", "pressao_referencia", "atuacao_1", "atuacao_2", "atuacao_3",
        "rearme_1", "rearme_2", "rearme_3", "media_atuacao", "media_rearme",
        "erro", "correcao", "repetitividade", "desvio_padrao", "histerese",
        "criterio_tipo", "criterio_valor", "tolerancia_resolvida", "resultado", "observacoes",
    )


class IncertezaInline(admin.TabularInline):
    model = DispositivoSegurancaIncertezaPonto
    form = SafetyDecimalForm
    extra = 1
    readonly_fields = (
        "u_repetitividade", "u_resolucao_dispositivo", "u_resolucao_padrao",
        "u_certificado_padrao", "u_deriva_padrao", "incerteza_padrao_combinada",
        "incerteza_expandida",
    )
    fields = (
        "ordem", "condicao", "resolucao_dispositivo", "resolucao_padrao",
        "incerteza_certificado_padrao", "fator_k_certificado_padrao", "limite_deriva_padrao",
        "u_repetitividade", "u_resolucao_dispositivo", "u_resolucao_padrao",
        "u_certificado_padrao", "u_deriva_padrao", "u_outros", "outros_descricao",
        "incerteza_padrao_combinada", "fator_k", "graus_liberdade", "incerteza_expandida",
    )


@admin.register(CalibracaoDispositivoSegurancaPressao)
class CalibracaoDispositivoSegurancaAdmin(
    OrdemServicoAutomaticaAdminMixin,
    EmittedCalibrationAdminMixin,
    admin.ModelAdmin,
):
    form = CalibracaoDispositivoSegurancaForm
    list_display = (
        "numero_certificado", "tipo_dispositivo", "instrumento", "cliente",
        "data_calibracao", "status", "resultado_final", "certificado_link",
    )
    list_filter = ("tipo_dispositivo", "tipo_documento", "status", "resultado_final", "data_calibracao")
    search_fields = (
        "numero_certificado", "ordem_servico", "instrumento__codigo", "instrumento__tag",
        "cliente__razao_social", "tag", "numero_serie",
    )
    autocomplete_fields = (
        "instrumento", "cliente", "procedimento_documento", "responsavel_tecnico", "tecnico_executante",
    )
    readonly_fields = ("resultado_inicial", "resultado_final", "pendencias_emissao_admin", "certificado_link")
    inlines = (PadraoUtilizadoInline, PontoInline, IncertezaInline)

    class Media:
        css = {"all": ("css/padrao_autofill.css",)}
        js = ("js/calibracao_ordem_servico.js", "js/padrao_autofill.js")
    save_on_top = True
    fieldsets = (
        ("Identificação e controle", {"fields": (
            "tipo_dispositivo", "tipo_documento", "status", "numero_certificado", "ordem_servico",
            "data_calibracao", "data_emissao", "proxima_calibracao", "revisao", "local_calibracao",
            "pendencias_emissao_admin", "certificado_link",
        )}),
        ("Cliente e dispositivo", {"fields": (
            "instrumento", "cliente", "contratante", "endereco_cliente", "tag", "equipamento_protegido",
            "fluido_servico", "fabricante", "modelo", "numero_serie", "tamanho_nominal", "tipo_conexao",
            "pressao_ajuste_declarada", "pmta", "unidade",
        )}),
        ("Execução do serviço", {"fields": (
            "fluido_teste", "ensaio_com_ajuste", "ensaio_a_quente", "manutencao_realizada",
            "exame_visual_inicial", "defeitos_constatados", "condicao_final",
        )}),
        ("Método e referências", {"fields": (
            "procedimento_documento", "procedimento_numero", "procedimento_revisao", "referencias_normativas",
        )}),
        ("Condições ambientais", {"fields": (
            "temperatura_inicial", "temperatura_final", "umidade_inicial", "umidade_final",
        )}),
        ("Critério e regra de decisão", {"fields": (
            "criterio_tipo", "criterio_valor", "criterio_origem", "criterio_referencia", "regra_decisao",
            "resultado_inicial", "resultado_final",
        )}),
        ("Responsáveis e observações", {"fields": (
            "tecnico_executante", "responsavel_tecnico", "observacoes_certificado",
        )}),
    )

    @admin.display(description="Pendências para emissão")
    def pendencias_emissao_admin(self, obj):
        if not obj or not obj.pk:
            return "Salve o registro para avaliar as pendências relacionadas."
        pending = obj.pendencias_emissao()
        if not pending:
            return format_html('<span style="color:#157347;font-weight:700">Sem pendências.</span>')
        return format_html(
            '<span style="color:#b42318;font-weight:700">{}</span>', " • ".join(pending)
        )

    @admin.display(description="Certificado")
    def certificado_link(self, obj):
        if not obj or not obj.pk:
            return "—"
        return format_html(
            '<a class="button" href="{}" target="_blank" rel="noopener">Visualizar / imprimir</a>',
            reverse("pdf_calibracao_dispositivo_seguranca", args=(obj.pk,)),
        )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.recalcular_resultados(save=True)
        pending = form.instance.pendencias_emissao()
        if pending:
            messages.warning(request, "Pendências para emissão: " + "; ".join(pending))
            if form.instance.status == "emitida":
                form.instance.status = "concluida"
                form.instance.save(update_fields=("status", "updated_at"))
                messages.error(
                    request,
                    "A emissão foi bloqueada e o registro permaneceu como Concluída até a correção das pendências.",
                )


@admin.register(DispositivoSegurancaPadraoUtilizado)
class DispositivoSegurancaPadraoAdmin(EmittedCalibrationChildAdminMixin, admin.ModelAdmin):
    list_display = ("calibracao", "ordem", "codigo", "numero_certificado", "situacao_na_data")
    search_fields = ("codigo", "numero_certificado", "calibracao__numero_certificado")
    autocomplete_fields = ("calibracao", "padrao")


@admin.register(DispositivoSegurancaPonto)
class DispositivoSegurancaPontoAdmin(EmittedCalibrationChildAdminMixin, admin.ModelAdmin):
    list_display = (
        "calibracao", "condicao", "ordem", "pressao_referencia", "media_atuacao",
        "erro", "correcao", "histerese", "resultado",
    )
    list_filter = ("condicao", "resultado")
    search_fields = ("calibracao__numero_certificado", "calibracao__instrumento__codigo")
    autocomplete_fields = ("calibracao",)


@admin.register(DispositivoSegurancaIncertezaPonto)
class DispositivoSegurancaIncertezaAdmin(EmittedCalibrationChildAdminMixin, admin.ModelAdmin):
    list_display = (
        "calibracao", "condicao", "ordem", "incerteza_padrao_combinada", "fator_k", "incerteza_expandida",
    )
    search_fields = ("calibracao__numero_certificado", "calibracao__instrumento__codigo")
    autocomplete_fields = ("calibracao",)
