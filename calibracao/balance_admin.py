from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html

from qualidade.models import Documento

from .balance_models import (
    BalancaExcentricidadePonto,
    BalancaIncertezaPonto,
    BalancaPadraoUtilizado,
    BalancaPontoIndicacao,
    BalancaRepetibilidade,
    CalibracaoBalanca,
)
from .models import Instrumento, InstrumentoTecnico, ResponsavelCertificado
from .admin_mixins import OrdemServicoAutomaticaAdminMixin
from .services.balance_calculation import convert_mass


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
    def _calibration(obj):
        if obj is None:
            return None
        if hasattr(obj, "calibracao_id"):
            return obj.calibracao if obj.calibracao_id else None
        if hasattr(obj, "ponto_id"):
            return obj.ponto.calibracao if obj.ponto_id else None
        return None

    @classmethod
    def _locked(cls, obj):
        calibration = cls._calibration(obj)
        return bool(calibration and calibration.status == "emitida")

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
            kwargs["queryset"] = CalibracaoBalanca.objects.exclude(status="emitida")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class BalanceDecimalForm(forms.ModelForm):
    class Meta:
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.DecimalField):
                field.localize = True
                field.widget = forms.TextInput(attrs={
                    **field.widget.attrs,
                    "inputmode": "decimal",
                    "data-decimal-places": str(field.decimal_places or 9),
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


class CalibracaoBalancaForm(BalanceDecimalForm):
    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == "emitida":
            required = {
                "procedimento_documento": "Vincule o procedimento vigente antes da emissão.",
                "responsavel_tecnico_ref": "Informe o responsável técnico antes da emissão.",
                "tecnico_executante_ref": "Informe o técnico executante antes da emissão.",
                "temperatura_inicial": "Informe a temperatura inicial.",
                "temperatura_final": "Informe a temperatura final.",
                "umidade_inicial": "Informe a umidade inicial.",
                "umidade_final": "Informe a umidade final.",
            }
            for name, message in required.items():
                if cleaned.get(name) in (None, ""):
                    self.add_error(name, message)
        return cleaned


class BalancaPadraoForm(BalanceDecimalForm):
    def clean(self):
        cleaned = super().clean()
        if cleaned.get("DELETE"):
            return cleaned
        standard = cleaned.get("padrao")
        if not standard:
            return cleaned
        calibration = getattr(self.instance, "calibracao", None)
        validity = cleaned.get("validade") or standard.vencimento
        calibration_date = getattr(calibration, "data_calibracao", None)
        if validity and calibration_date and validity < calibration_date:
            self.add_error("validade", "O padrão estava vencido na data da calibração.")
        for name, label in {
            "numero_certificado": "Número do certificado",
            "laboratorio_emitente": "Laboratório emitente",
            "data_calibracao": "Data de calibração do padrão",
            "validade": "Validade do padrão",
            "valor_nominal": "Valor nominal",
            "incerteza_expandida": "Incerteza expandida",
            "fator_k": "Fator de abrangência",
        }.items():
            value = cleaned.get(name)
            if value in (None, ""):
                source_name = {
                    "validade": "vencimento",
                    "incerteza_expandida": "incerteza",
                }.get(name, name)
                value = getattr(standard, source_name, None)
            if value in (None, ""):
                self.add_error(name, f"{label} é obrigatório para a rastreabilidade do resultado.")
        return cleaned


class BalancaPadraoInline(admin.TabularInline):
    model = BalancaPadraoUtilizado
    form = BalancaPadraoForm
    extra = 1
    autocomplete_fields = ("padrao",)
    fields = (
        "ordem", "padrao", "codigo", "classe_oiml", "numero_certificado",
        "laboratorio_emitente", "data_calibracao", "validade", "valor_nominal",
        "correcao", "incerteza_expandida", "fator_k", "limite_deriva", "unidade",
        "validade_status",
    )
    readonly_fields = ("validade_status",)


class BalancaRepetibilidadeInline(admin.StackedInline):
    model = BalancaRepetibilidade
    form = BalanceDecimalForm
    extra = 1
    fields = (
        ("condicao", "ordem", "carga_teste"),
        ("leitura_1", "leitura_2", "leitura_3", "leitura_4", "leitura_5"),
        ("leitura_6", "leitura_7", "leitura_8", "leitura_9", "leitura_10"),
        ("media_formatada", "desvio_padrao_formatado", "numero_repeticoes"),
    )
    readonly_fields = ("media_formatada", "desvio_padrao_formatado", "numero_repeticoes")


class BalancaExcentricidadeInline(admin.TabularInline):
    model = BalancaExcentricidadePonto
    form = BalanceDecimalForm
    extra = 5
    fields = (
        "condicao", "ordem", "posicao", "descricao_posicao", "carga_teste",
        "indicacao", "indicacao_zero", "diferenca_centro_formatada",
    )
    readonly_fields = ("diferenca_centro_formatada",)


class BalancaIndicacaoInline(admin.StackedInline):
    model = BalancaPontoIndicacao
    form = BalanceDecimalForm
    extra = 5
    filter_horizontal = ("padroes_aplicados",)
    fields = (
        ("condicao", "ordem"),
        ("carga_nominal", "correcao_padroes", "massa_referencia_formatada"),
        ("indicacao_1", "indicacao_2", "indicacao_3", "indicacao_media_formatada"),
        ("erro_formatado", "correcao_formatada", "tolerancia", "resultado"),
        "padroes_aplicados",
        "incerteza_link",
    )
    readonly_fields = (
        "massa_referencia_formatada", "indicacao_media_formatada", "erro_formatado",
        "correcao_formatada", "resultado", "incerteza_link",
    )

    def incerteza_link(self, obj):
        if not obj or not obj.pk:
            return "Salve a calibração para abrir o orçamento de incerteza."
        uncertainty = getattr(obj, "incerteza", None)
        if uncertainty:
            url = reverse("admin:calibracao_balancaincertezaponto_change", args=[uncertainty.pk])
            return format_html('<a href="{}">Editar orçamento de incerteza</a>', url)
        return "O orçamento será criado automaticamente ao salvar."

    incerteza_link.short_description = "Incerteza"


@admin.register(CalibracaoBalanca)
class CalibracaoBalancaAdmin(
    OrdemServicoAutomaticaAdminMixin,
    EmittedCalibrationAdminMixin,
    admin.ModelAdmin,
):
    form = CalibracaoBalancaForm
    list_display = (
        "numero_certificado", "instrumento", "cliente", "data_calibracao", "status", "certificate_link"
    )
    list_filter = ("status", "local_calibracao", "tipo_instrumento", "data_calibracao")
    search_fields = (
        "numero_certificado", "ordem_servico", "instrumento__codigo",
        "instrumento__descricao", "cliente__razao_social",
    )
    autocomplete_fields = (
        "instrumento", "cliente", "procedimento_documento",
        "responsavel_tecnico_ref", "tecnico_executante_ref",
    )
    readonly_fields = ("numero_certificado", "certificate_pending_display")
    fieldsets = (
        ("Identificação", {"fields": (
            "numero_certificado", "ordem_servico", "data_calibracao", "data_emissao",
            "revisao", "status", "instrumento", "cliente", "local_calibracao",
        )}),
        ("Equipamento calibrado", {"fields": (
            "contratante", "endereco_contratante", "endereco_cliente", "equipamento_calibrado",
            "numero_identificacao", "marca", "modelo", "numero_serie", "tipo_instrumento",
            "classe_exatidao", "capacidade_minima", "capacidade_maxima", "divisao_escala",
            "intervalo_verificacao", "unidade", "dispositivo_zero",
        )}),
        ("Método e condições", {"fields": (
            "procedimento_documento", "metodo_referencia", "temperatura_inicial",
            "temperatura_final", "umidade_inicial", "umidade_final", "pressao_atmosferica",
            "nivelamento_verificado", "ajuste_efetuado", "autorizacao_ajuste",
        )}),
        ("Conformidade e responsáveis", {"fields": (
            "regra_decisao", "criterio_referencia", "responsavel_tecnico_ref",
            "tecnico_executante_ref", "observacoes_certificado", "certificate_pending_display",
        )}),
        ("Auditoria", {"classes": ("collapse",), "fields": ("snapshot_json", "pdf_arquivo")}),
    )
    inlines = (
        BalancaPadraoInline,
        BalancaRepetibilidadeInline,
        BalancaExcentricidadeInline,
        BalancaIndicacaoInline,
    )

    class Media:
        css = {"all": ("css/padrao_autofill.css",)}
        js = ("js/calibracao_ordem_servico.js", "js/padrao_autofill.js")

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj=obj, change=change, **kwargs)
        field = form.base_fields.get("instrumento")
        if field:
            sample = "00000000-0000-0000-0000-000000000000"
            url = reverse("admin:calibracao_calibracaobalanca_instrumento_dados", args=[sample])
            field.widget.attrs["data-instrumento-dados-url"] = url.replace(sample, "__instrumento__")
        return form

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        responsible = ResponsavelCertificado.objects.filter(ativo=True).order_by("nome").first()
        if responsible:
            initial.setdefault("responsavel_tecnico_ref", responsible.pk)
            initial.setdefault("tecnico_executante_ref", responsible.pk)
        return initial

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "procedimento_documento":
            kwargs["queryset"] = Documento.objects.filter(
                tipo__in=("procedimento", "instrucao", "metodo"), status="vigente"
            ).order_by("codigo", "titulo")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "instrumento/<uuid:instrumento_id>/dados/",
                self.admin_site.admin_view(self.instrument_data_view),
                name="calibracao_calibracaobalanca_instrumento_dados",
            ),
            path(
                "<uuid:pk>/certificado/",
                self.admin_site.admin_view(self.certificate_view),
                name="calibracao_calibracaobalanca_certificado",
            ),
        ]
        return custom + urls

    def instrument_data_view(self, request, instrumento_id):
        if not request.user.has_perm("calibracao.view_instrumento"):
            raise PermissionDenied
        instrument = get_object_or_404(Instrumento.objects.select_related("cliente"), pk=instrumento_id)
        try:
            technical = instrument.tecnico
        except InstrumentoTecnico.DoesNotExist:
            technical = None
        return JsonResponse({
            "cliente_id": str(instrument.cliente_id),
            "contratante": instrument.cliente.razao_social or "",
            "equipamento_calibrado": instrument.descricao or "Balança",
            "numero_identificacao": instrument.codigo or "",
            "marca": instrument.marca or "",
            "modelo": instrument.modelo or "",
            "numero_serie": instrument.numero_serie or "",
            "classe_exatidao": technical.classe if technical else "",
            "divisao_escala": str(technical.menor_resolucao) if technical and technical.menor_resolucao else "",
            "unidade": technical.unidade if technical and technical.unidade in ("mg", "g", "kg", "t") else "",
        })

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        calibration = form.instance
        for eccentricity in calibration.pontos_excentricidade.all():
            eccentricity.recalculate(save=True)
        for point in calibration.pontos_indicacao.all():
            correction = sum(
                (
                    convert_mass(standard.correcao or 0, standard.unidade, calibration.unidade)
                    for standard in point.padroes_aplicados.all()
                ),
                Decimal("0"),
            )
            point.correcao_padroes = correction
            point.save(update_fields=["correcao_padroes"])
            repeatability = calibration.repetibilidades.filter(condicao=point.condicao).order_by("ordem").first()
            uncertainty, _ = BalancaIncertezaPonto.objects.get_or_create(
                ponto=point, defaults={"repetibilidade": repeatability}
            )
            if not uncertainty.repetibilidade_id and repeatability:
                uncertainty.repetibilidade = repeatability
            uncertainty.save()
        pending = calibration.certificate_pending_items()
        if pending:
            messages.warning(request, "Pendências para emissão: " + "; ".join(pending) + ".")
            if calibration.status == "emitida":
                calibration.status = "rascunho"
                calibration.save(update_fields=["status", "updated_at"])
                messages.error(
                    request,
                    "A emissão foi bloqueada e o registro retornou a Rascunho até a correção das pendências.",
                )

    def certificate_pending_display(self, obj):
        if not obj or not obj.pk:
            return "As pendências serão avaliadas após o primeiro salvamento."
        pending = obj.certificate_pending_items()
        return "Nenhuma pendência estrutural." if not pending else "; ".join(pending)

    certificate_pending_display.short_description = "Pendências do certificado"

    def certificate_view(self, request, pk):
        from .views import certificado_balanca
        calibration = get_object_or_404(CalibracaoBalanca, pk=pk)
        if not self.has_view_permission(request, calibration):
            raise PermissionDenied
        return certificado_balanca(request, pk)

    def certificate_link(self, obj):
        return format_html(
            '<a class="button" href="{}" target="_blank">Certificado</a>',
            reverse("admin:calibracao_calibracaobalanca_certificado", args=[obj.pk]),
        )

    certificate_link.short_description = "Certificado"


@admin.register(BalancaIncertezaPonto)
class BalancaIncertezaPontoAdmin(EmittedCalibrationChildAdminMixin, admin.ModelAdmin):
    form = BalanceDecimalForm
    list_display = (
        "ponto", "incerteza_padrao_combinada_formatada", "fator_k", "incerteza_expandida_formatada"
    )
    list_select_related = ("ponto", "ponto__calibracao")
    search_fields = (
        "ponto__calibracao__numero_certificado", "ponto__calibracao__instrumento__codigo"
    )
    readonly_fields = (
        "u_resolucao_zero_formatada", "u_resolucao_carga_formatada",
        "u_repetibilidade_formatada", "u_excentricidade_formatada",
        "u_certificados_pesos_formatada", "u_deriva_pesos_formatada",
        "incerteza_padrao_combinada_formatada",
        "incerteza_padrao_combinada_completa_formatada", "percentual_variancia_desconsiderada",
        "componentes_significativos", "componentes_desconsiderados", "incerteza_expandida_formatada",
    )
    fieldsets = (
        ("Ponto e repetibilidade", {"fields": ("ponto", "repetibilidade", "usar_media_indicacoes")}),
        ("Componentes calculados", {"fields": (
            "u_resolucao_zero_formatada", "u_resolucao_carga_formatada",
            "u_repetibilidade_formatada", "u_excentricidade_formatada",
            "u_certificados_pesos_formatada", "u_deriva_pesos_formatada",
        )}),
        ("Componentes definidos pelo procedimento", {"fields": (
            "u_empuxo_ar", "u_conveccao", "u_outros", "outros_descricao",
        )}),
        ("Critério de significância", {"fields": (
            "limite_variancia_desconsiderada_percentual",
            "percentual_variancia_desconsiderada",
            "componentes_significativos",
            "componentes_desconsiderados",
        )}),
        ("Resultado", {"fields": (
            "incerteza_padrao_combinada_completa_formatada", "incerteza_padrao_combinada_formatada",
            "fator_k", "graus_liberdade", "incerteza_expandida_formatada",
        )}),
    )

    def _format_component(self, obj, field):
        if not obj or not obj.ponto_id:
            return "—"
        return obj.ponto.calibracao.formatar_resultado(getattr(obj, field), casas_adicionais=2)

    @admin.display(description="u resolução no zero")
    def u_resolucao_zero_formatada(self, obj):
        return self._format_component(obj, "u_resolucao_zero")

    @admin.display(description="u resolução sob carga")
    def u_resolucao_carga_formatada(self, obj):
        return self._format_component(obj, "u_resolucao_carga")

    @admin.display(description="u repetibilidade")
    def u_repetibilidade_formatada(self, obj):
        return self._format_component(obj, "u_repetibilidade")

    @admin.display(description="u excentricidade")
    def u_excentricidade_formatada(self, obj):
        return self._format_component(obj, "u_excentricidade")

    @admin.display(description="u certificados dos pesos")
    def u_certificados_pesos_formatada(self, obj):
        return self._format_component(obj, "u_certificados_pesos")

    @admin.display(description="u deriva dos pesos")
    def u_deriva_pesos_formatada(self, obj):
        return self._format_component(obj, "u_deriva_pesos")


@admin.register(BalancaPadraoUtilizado)
class BalancaPadraoUtilizadoAdmin(EmittedCalibrationChildAdminMixin, admin.ModelAdmin):
    list_display = ("calibracao", "ordem", "codigo", "valor_nominal", "unidade", "validade_status")
    search_fields = ("codigo", "numero_certificado", "calibracao__numero_certificado")
    autocomplete_fields = ("padrao", "calibracao")
