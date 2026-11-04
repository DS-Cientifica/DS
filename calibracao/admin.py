from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.urls import path, reverse
from openpyxl import Workbook, load_workbook

from clientes.models import Cliente
from qualidade.models import Documento

from .models import (
    Instrumento,
    InstrumentoTecnico,
    OrdemServico,
    Padrao,
    Periodicidade,
    Calibracao,
    CalibracaoAnexo,
    CalibracaoTurbidez,
    TurbidezPadraoUtilizado,
    TurbidezVerificacaoPonto,
    TurbidezCalibracaoPonto,
    TurbidezIncertezaPonto,
    ResponsavelCertificado,
    CalibracaoColorimetro,
    ColorimetroPadraoUtilizado,
    ColorimetroVerificacaoPonto,
    ColorimetroCalibracaoPonto,
    ColorimetroIncertezaPonto,
    CalibracaoPressao,
    PressaoPadraoUtilizado,
    PressaoCalibracaoPonto,
    PressaoIncertezaPonto,
    CalibracaoCondutividade,
)
from .admin_mixins import OrdemServicoAutomaticaAdminMixin
from .deletion_policy import motivos_protecao_exclusao
from .ph_models import (
    CalibracaoPH,
    CalibracaoPHPadraoUtilizado,
    CalibracaoPHPonto,
    CalibracaoPHIncertezaPonto,
    _join_address,
)
from . import balance_admin
from . import safety_admin
from . import sphyg_admin
from . import dilution_admin


def _decimal_places_for_form(field):
    decimal_places = getattr(field, "decimal_places", None)
    if decimal_places is None:
        return 3
    return min(int(decimal_places), 3)


def _quantize_decimal_form_value(value, decimal_places=3):
    if value in (None, ""):
        return value
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value
    quantizer = Decimal("1").scaleb(-decimal_places)
    return decimal_value.quantize(quantizer)


class ThreeDecimalAdminForm(forms.ModelForm):
    class Meta:
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field, forms.DecimalField):
                attrs = dict(getattr(field.widget, "attrs", {}))
                field.widget = forms.TextInput(attrs=attrs)
                decimal_places = _decimal_places_for_form(field)
                field.localize = True
                field.widget.is_localized = True
                field.widget.attrs["inputmode"] = "decimal"
                field.widget.attrs["data-decimal-places"] = str(decimal_places)
                if name in self.initial:
                    self.initial[name] = _quantize_decimal_form_value(self.initial[name], decimal_places)

    def clean(self):
        cleaned_data = super().clean()
        for name, field in self.fields.items():
            if isinstance(field, forms.DecimalField) and cleaned_data.get(name) not in (None, ""):
                cleaned_data[name] = _quantize_decimal_form_value(
                    cleaned_data[name],
                    _decimal_places_for_form(field),
                )
        return cleaned_data


def build_three_decimal_form(model):
    meta = type("Meta", (), {"model": model, "fields": "__all__"})
    return type(f"{model.__name__}ThreeDecimalAdminForm", (ThreeDecimalAdminForm,), {"Meta": meta})


class OrdemServicoNumeroFilter(admin.SimpleListFilter):
    title = "Ordem de servico"
    parameter_name = "ordem_servico_numero"

    def lookups(self, request, model_admin):
        numeros = (
            OrdemServico.objects.exclude(numero="")
            .order_by("-data_abertura")
            .values_list("numero", flat=True)
        )
        return [(numero, numero) for numero in numeros]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(ordem_servico=self.value())
        return queryset


CalibracaoAdminForm = build_three_decimal_form(Calibracao)


class AssinaturaCertificadoA1Form(forms.Form):
    certificado_a1 = forms.FileField(
        label="Certificado digital A1",
        help_text="Selecione o arquivo .pfx ou .p12. O arquivo não será armazenado.",
        widget=forms.ClearableFileInput(attrs={"accept": ".pfx,.p12"}),
    )
    senha = forms.CharField(
        label="Senha do certificado",
        strip=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password"},
        ),
        help_text="A senha será usada somente nesta operação e não será gravada.",
    )
    confirmacao = forms.BooleanField(
        label=(
            "Confirmo que revisei o certificado final, os resultados, a incerteza, "
            "a rastreabilidade e autorizo a assinatura digital desta emissão."
        )
    )

    def clean_certificado_a1(self):
        arquivo = self.cleaned_data["certificado_a1"]
        if not arquivo.name.lower().endswith((".pfx", ".p12")):
            raise forms.ValidationError("Envie um certificado A1 no formato .pfx ou .p12.")
        if arquivo.size > 10 * 1024 * 1024:
            raise forms.ValidationError("O certificado A1 deve ter no máximo 10 MB.")
        return arquivo
CalibracaoTurbidezAdminForm = build_three_decimal_form(CalibracaoTurbidez)
TurbidezPadraoAdminForm = build_three_decimal_form(TurbidezPadraoUtilizado)
TurbidezVerificacaoAdminForm = build_three_decimal_form(TurbidezVerificacaoPonto)
TurbidezCalibracaoAdminForm = build_three_decimal_form(TurbidezCalibracaoPonto)
TurbidezIncertezaAdminForm = build_three_decimal_form(TurbidezIncertezaPonto)
CalibracaoColorimetroBaseAdminForm = build_three_decimal_form(CalibracaoColorimetro)
ColorimetroPadraoAdminForm = build_three_decimal_form(ColorimetroPadraoUtilizado)
ColorimetroVerificacaoAdminForm = build_three_decimal_form(ColorimetroVerificacaoPonto)
ColorimetroCalibracaoAdminForm = build_three_decimal_form(ColorimetroCalibracaoPonto)
ColorimetroIncertezaAdminForm = build_three_decimal_form(ColorimetroIncertezaPonto)
CalibracaoPressaoAdminForm = build_three_decimal_form(CalibracaoPressao)
PressaoPadraoAdminForm = build_three_decimal_form(PressaoPadraoUtilizado)
PressaoCalibracaoAdminForm = build_three_decimal_form(PressaoCalibracaoPonto)
PressaoIncertezaAdminForm = build_three_decimal_form(PressaoIncertezaPonto)
CalibracaoPHAdminForm = build_three_decimal_form(CalibracaoPH)
PHPadraoAdminForm = build_three_decimal_form(CalibracaoPHPadraoUtilizado)
PHPontoAdminForm = build_three_decimal_form(CalibracaoPHPonto)
PHIncertezaAdminForm = build_three_decimal_form(CalibracaoPHIncertezaPonto)
CalibracaoCondutividadeAdminForm = build_three_decimal_form(CalibracaoCondutividade)


class CalibracaoColorimetroAdminForm(CalibracaoColorimetroBaseAdminForm):
    class Meta(CalibracaoColorimetroBaseAdminForm.Meta):
        model = CalibracaoColorimetro
        fields = "__all__"


# =========================
# INLINES
# =========================

class PeriodicidadeInline(admin.TabularInline):
    model = Periodicidade
    extra = 1


class InstrumentoTecnicoInline(admin.StackedInline):
    model = InstrumentoTecnico
    extra = 0
    fields = (
        "faixa_medicao",
        "capacidade_total",
        "menor_resolucao",
        "unidade",
        "classe",
        "observacoes",
    )


class InstrumentoAdminForm(forms.ModelForm):
    class Meta:
        model = Instrumento
        fields = "__all__"
        labels = {
            "descricao": "Nome do serviço",
        }
        help_texts = {
            "descricao": "Ex.: Medidor de espessura, medidor de pH, condutividade, manômetro.",
        }

    class Media:
        js = ("js/admin_instrumento_duplicate_alert.js",)


class DuplicarInstrumentoForm(forms.Form):
    codigo = forms.CharField(
        label="Novo código interno",
        max_length=50,
        help_text="Identificador único do cadastro no AXION.",
    )
    tag = forms.CharField(
        label="Nova TAG do cliente",
        max_length=100,
        help_text="Identificador operacional do ativo nas instalações do cliente.",
    )
    numero_serie = forms.CharField(
        label="Número de série do novo instrumento",
        max_length=100,
        required=False,
        help_text="Informe o número gravado pelo fabricante. Ele não é copiado do instrumento original.",
    )
    confirmar_sem_numero_serie = forms.BooleanField(
        label="Confirmo que o novo instrumento não possui número de série identificável",
        required=False,
    )
    local_instalacao = forms.CharField(
        label="Local de instalação",
        max_length=200,
        required=False,
        help_text="Revise este campo, pois o novo ativo pode estar instalado em outro ponto.",
    )

    def __init__(self, *args, instrumento_origem, **kwargs):
        self.instrumento_origem = instrumento_origem
        super().__init__(*args, **kwargs)
        self.fields["local_instalacao"].initial = instrumento_origem.local_instalacao

    def clean_codigo(self):
        codigo = (self.cleaned_data.get("codigo") or "").strip()
        if Instrumento.objects.filter(codigo__iexact=codigo).exists():
            raise forms.ValidationError("Já existe um instrumento com este código.")
        if codigo.casefold() == (self.instrumento_origem.codigo or "").strip().casefold():
            raise forms.ValidationError("O novo código deve ser diferente do instrumento de origem.")
        return codigo

    def clean_tag(self):
        tag = (self.cleaned_data.get("tag") or "").strip()
        if Instrumento.objects.filter(
            cliente=self.instrumento_origem.cliente,
            tag__iexact=tag,
        ).exists():
            raise forms.ValidationError("Esta TAG já está cadastrada para o mesmo cliente.")
        if tag.casefold() == (self.instrumento_origem.tag or "").strip().casefold():
            raise forms.ValidationError("A nova TAG deve ser diferente do instrumento de origem.")
        return tag

    def clean(self):
        cleaned_data = super().clean()
        numero_serie = (cleaned_data.get("numero_serie") or "").strip()
        sem_numero_serie = cleaned_data.get("confirmar_sem_numero_serie")

        if numero_serie and sem_numero_serie:
            self.add_error(
                "confirmar_sem_numero_serie",
                "Desmarque esta opção porque um número de série foi informado.",
            )
        elif not numero_serie and not sem_numero_serie:
            self.add_error(
                "numero_serie",
                "Informe o número de série ou confirme explicitamente que ele não é identificável.",
            )

        origem_serie = (self.instrumento_origem.numero_serie or "").strip()
        if numero_serie and origem_serie and numero_serie.casefold() == origem_serie.casefold():
            self.add_error(
                "numero_serie",
                "O número de série deve identificar o novo instrumento e não pode repetir o da origem.",
            )
        if numero_serie and Instrumento.objects.filter(
            cliente=self.instrumento_origem.cliente,
            numero_serie__iexact=numero_serie,
        ).exists():
            self.add_error(
                "numero_serie",
                "Já existe um instrumento deste cliente com este número de série.",
            )

        cleaned_data["numero_serie"] = numero_serie
        cleaned_data["local_instalacao"] = (cleaned_data.get("local_instalacao") or "").strip()
        return cleaned_data


class CalibracaoImportForm(forms.Form):
    arquivo = forms.FileField(
        label="Planilha Excel",
        help_text="Envie um arquivo .xlsx seguindo o modelo oficial de importacao de calibracoes.",
    )


CALIBRACAO_IMPORT_TIPOS = {
    "pressao",
    "colorimetro",
    "ph",
    "turbidez",
    "condutividade",
}

CALIBRACAO_IMPORT_REQUIRED_SHEETS = (
    "CALIBRACOES",
    "PADROES_UTILIZADOS",
)

CALIBRACAO_IMPORT_SHEETS = {
    "CALIBRACOES": (
        [
            "tipo_calibracao",
            "certificado_numero",
            "cliente_codigo",
            "cliente_cnpj",
            "cliente_razao_social",
            "instrumento_codigo",
            "instrumento_tag",
            "instrumento_numero_serie",
            "data_calibracao",
            "data_emissao",
            "local_calibracao",
            "temperatura_inicial",
            "temperatura_final",
            "umidade_inicial",
            "umidade_final",
            "resultado_final_status",
            "observacoes",
        ],
        [
            "colorimetro",
            "BBOSCH-052629-COR-01",
            "CL-0002",
            "",
            "",
            "COR-052629",
            "",
            "202103B",
            "2026-07-18",
            "2026-07-18",
            "DS Cientifica",
            22,
            22,
            55,
            55,
            "aprovado",
            "Exemplo de preenchimento.",
        ],
    ),
    "PADROES_UTILIZADOS": (
        [
            "certificado_numero",
            "padrao_codigo",
            "descricao_padrao",
            "numero_certificado_padrao",
            "laboratorio_emitente",
            "data_validade",
            "resolucao",
            "incerteza",
            "fator_k",
            "graus_liberdade",
            "unidade",
            "valor_nominal",
        ],
        [
            "BBOSCH-052629-COR-01",
            "DSP-024",
            "Solucao Padrao de Cor",
            "p.01.0205.042.30.75",
            "Dinamica Quimica",
            "2027-06-15",
            "",
            1.015,
            2,
            "infinito",
            "Cor",
            100,
        ],
    ),
    "PRESSAO_LEITURAS": (
        [
            "certificado_numero",
            "ordem",
            "padrao",
            "crescente_1",
            "crescente_2",
            "decrescente_1",
            "decrescente_2",
            "ema",
            "criterio_tipo",
            "criterio_valor",
        ],
        ["PRE-0001", 1, 1.0, 1.0, 1.0, 1.0, 1.0, 0.05, "numerico", 0.05],
    ),
    "COLORIMETRO_LEITURAS": (
        [
            "certificado_numero",
            "ordem",
            "valor_referencia",
            "leitura_1",
            "leitura_2",
            "leitura_3",
            "criterio_tipo",
            "criterio_valor",
            "criterio_origem",
        ],
        ["BBOSCH-052629-COR-01", 1, 100, 99, 99, 99, "porcentagem", 5, "Fabricante"],
    ),
    "PH_LEITURAS": (
        [
            "certificado_numero",
            "ordem",
            "valor_referencia",
            "leitura_1",
            "leitura_2",
            "leitura_3",
            "temperatura",
            "criterio_tipo",
            "criterio_valor",
        ],
        ["PH-0001", 1, 7.0, 7.01, 7.00, 7.02, 25, "numerico", 0.05],
    ),
    "TURBIDEZ_LEITURAS": (
        [
            "certificado_numero",
            "ordem",
            "valor_referencia",
            "leitura_1",
            "leitura_2",
            "leitura_3",
            "criterio_tipo",
            "criterio_valor",
        ],
        ["TUR-0001", 1, 10, 10.1, 10.0, 10.2, "porcentagem", 10],
    ),
    "CONDUTIVIDADE_LEITURAS": (
        [
            "certificado_numero",
            "ordem",
            "valor_referencia",
            "leitura_1",
            "leitura_2",
            "leitura_3",
            "temperatura",
            "criterio_tipo",
            "criterio_valor",
        ],
        ["COND-0001", 1, 1413, 1410, 1412, 1411, 25, "porcentagem", 2],
    ),
    "INCERTEZAS": (
        [
            "certificado_numero",
            "ordem",
            "componente",
            "valor",
            "distribuicao",
            "divisor",
            "graus_liberdade",
            "observacao",
        ],
        ["BBOSCH-052629-COR-01", 1, "Padrao", 1.015, "normal", 2, "infinito", ""],
    ),
}


class InstrumentoImportForm(forms.Form):
    arquivo = forms.FileField(
        label="Planilha Excel",
        help_text="Envie um arquivo .xlsx seguindo o modelo disponibilizado.",
    )


# =========================
# RESPONSÁVEIS
# =========================

@admin.register(ResponsavelCertificado)
class ResponsavelCertificadoAdmin(admin.ModelAdmin):
    list_display = ("nome", "cargo", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome", "cargo")
    ordering = ("nome",)


# =========================
# INSTRUMENTO
# =========================

@admin.register(Instrumento)
class InstrumentoAdmin(admin.ModelAdmin):
    form = InstrumentoAdminForm
    change_list_template = "admin/calibracao/instrumento/change_list.html"
    change_form_template = "admin/calibracao/instrumento/change_form.html"

    list_display = (
        "codigo",
        "descricao",
        "marca",
        "modelo",
        "numero_serie",
        "tag",
        "cliente",
        "status",
        "ver_certificados_padroes",
        "acao_copiar",
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
        "tag",
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
                "tag",
            )
        }),

        ("Localização", {
            "fields": (
                "local_instalacao",
            )
        }),

        ("Referências técnicas", {
            "fields": (
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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<uuid:object_id>/duplicar/",
                self.admin_site.admin_view(self.duplicar_instrumento_view),
                name="calibracao_instrumento_duplicar",
            ),
            path(
                "importar-excel/",
                self.admin_site.admin_view(self.importar_excel_view),
                name="calibracao_instrumento_importar_excel",
            ),
            path(
                "modelo-importacao/",
                self.admin_site.admin_view(self.download_modelo_importacao_view),
                name="calibracao_instrumento_modelo_importacao",
            ),
            path(
                "exportar-excel/",
                self.admin_site.admin_view(self.exportar_excel_view),
                name="calibracao_instrumento_exportar_excel",
            ),
            path(
                "check-duplicate/",
                self.admin_site.admin_view(self.check_duplicate_view),
                name="calibracao_instrumento_check_duplicate",
            )
        ]
        return custom_urls + urls

    @admin.display(description="Copiar")
    def acao_copiar(self, obj):
        return format_html(
            '<a class="button" href="{}">Copiar</a>',
            reverse("admin:calibracao_instrumento_duplicar", args=[obj.pk]),
        )

    def duplicar_instrumento_view(self, request, object_id):
        instrumento_origem = get_object_or_404(
            Instrumento.objects.select_related("cliente", "metodo_calibracao").prefetch_related(
                "padroes",
                "periodicidades",
            ),
            pk=object_id,
        )
        if not self.has_view_or_change_permission(request, instrumento_origem):
            raise PermissionDenied
        if not self.has_add_permission(request):
            raise PermissionDenied

        form = DuplicarInstrumentoForm(
            request.POST or None,
            instrumento_origem=instrumento_origem,
        )
        if request.method == "POST" and form.is_valid():
            with transaction.atomic():
                novo_instrumento = Instrumento(
                    codigo=form.cleaned_data["codigo"],
                    descricao=instrumento_origem.descricao,
                    marca=instrumento_origem.marca,
                    modelo=instrumento_origem.modelo,
                    local_instalacao=form.cleaned_data["local_instalacao"],
                    numero_serie=form.cleaned_data["numero_serie"] or None,
                    tag=form.cleaned_data["tag"],
                    cliente=instrumento_origem.cliente,
                    status="ativo",
                    proxima_calibracao=None,
                    ativo=True,
                    nome_anexo="",
                    anexo=None,
                    metodo_calibracao=instrumento_origem.metodo_calibracao,
                )
                novo_instrumento.full_clean(exclude=("padroes",))
                novo_instrumento.save()
                novo_instrumento.padroes.set(instrumento_origem.padroes.all())

                try:
                    dados_tecnicos = instrumento_origem.tecnico
                except InstrumentoTecnico.DoesNotExist:
                    dados_tecnicos = None
                if dados_tecnicos:
                    InstrumentoTecnico.objects.create(
                        instrumento=novo_instrumento,
                        faixa_medicao=dados_tecnicos.faixa_medicao,
                        capacidade_total=dados_tecnicos.capacidade_total,
                        menor_resolucao=dados_tecnicos.menor_resolucao,
                        unidade=dados_tecnicos.unidade,
                        classe=dados_tecnicos.classe,
                        observacoes=dados_tecnicos.observacoes,
                    )

                Periodicidade.objects.bulk_create(
                    [
                        Periodicidade(
                            instrumento=novo_instrumento,
                            tipo=periodicidade.tipo,
                            intervalo_meses=periodicidade.intervalo_meses,
                        )
                        for periodicidade in instrumento_origem.periodicidades.all()
                    ]
                )

            self.message_user(
                request,
                (
                    f'Instrumento "{instrumento_origem.codigo}" copiado como '
                    f'"{novo_instrumento.codigo}". Revise os dados antes do uso operacional.'
                ),
                level=messages.SUCCESS,
            )
            return redirect(
                reverse("admin:calibracao_instrumento_change", args=[novo_instrumento.pk])
            )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Copiar instrumento",
            "instrumento_origem": instrumento_origem,
            "form": form,
            "media": self.media + form.media,
        }
        return render(
            request,
            "admin/calibracao/instrumento/duplicar_instrumento.html",
            context,
        )

    def check_duplicate_view(self, request):
        cliente_id = request.GET.get("cliente_id")
        numero_serie = (request.GET.get("numero_serie") or "").strip()
        codigo = ""
        tag = (request.GET.get("tag") or "").strip()
        object_id = request.GET.get("object_id")

        if not cliente_id:
            return JsonResponse({"duplicate": False})

        if numero_serie and tag:
            qs_serie = Instrumento.objects.filter(
                cliente_id=cliente_id,
                numero_serie__iexact=numero_serie,
                tag__iexact=tag,
            )
            if object_id:
                qs_serie = qs_serie.exclude(pk=object_id)
            if qs_serie.exists():
                return JsonResponse(
                    {
                        "duplicate": True,
                        "message": "Já existe instrumento cadastrado para este cliente com o mesmo número de série e a mesma TAG.",
                    }
                )

        if codigo:
            qs_codigo = Instrumento.objects.filter(codigo__iexact=codigo)
            if object_id:
                qs_codigo = qs_codigo.exclude(pk=object_id)
            if qs_codigo.exists():
                return JsonResponse(
                    {
                        "duplicate": True,
                        "message": "Já existe instrumento cadastrado com a mesma TAG/código.",
                    }
                )

        return JsonResponse({"duplicate": False})

    def importar_excel_view(self, request):
        if not self.has_add_permission(request):
            return redirect("admin:calibracao_instrumento_changelist")

        form = InstrumentoImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            try:
                resultado = self._processar_planilha_importacao(form.cleaned_data["arquivo"])
            except ValueError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
            else:
                if resultado["criados"]:
                    self.message_user(
                        request,
                        f'{resultado["criados"]} instrumento(s) importado(s) com sucesso.',
                        level=messages.SUCCESS,
                    )
                if resultado["ignorados"]:
                    self.message_user(
                        request,
                        f'{resultado["ignorados"]} linha(s) ignorada(s) por estarem vazias.',
                        level=messages.WARNING,
                    )
                if resultado.get("sem_tag"):
                    self.message_user(
                        request,
                        f'{resultado["sem_tag"]} linha(s) importada(s) sem TAG. Isso e permitido, mas reduz a rastreabilidade operacional.',
                        level=messages.WARNING,
                    )
                if resultado["erros"]:
                    resumo = " | ".join(resultado["erros"][:10])
                    if len(resultado["erros"]) > 10:
                        resumo += f' | ... e mais {len(resultado["erros"]) - 10} erro(s).'
                    self.message_user(request, resumo, level=messages.ERROR)
                if not any(resultado.values()):
                    self.message_user(
                        request,
                        "Nenhuma linha válida foi encontrada na planilha.",
                        level=messages.WARNING,
                    )
                return redirect("admin:calibracao_instrumento_changelist")

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar instrumentos por Excel",
            "subtitle": "Cadastro em lote de instrumentos",
            "form": form,
            "download_model_url": reverse("admin:calibracao_instrumento_modelo_importacao"),
        }
        return render(request, "admin/calibracao/instrumento/importar_excel.html", context)

    def download_modelo_importacao_view(self, request):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Instrumentos"
        headers = [
            "cliente_codigo",
            "cliente_cnpj",
            "cliente_razao_social",
            "codigo",
            "nome_servico",
            "marca",
            "modelo",
            "numero_serie",
            "tag",
            "local_instalacao",
            "status",
            "proxima_calibracao",
            "ativo",
            "faixa_medicao",
            "capacidade_total",
            "menor_resolucao",
            "unidade",
            "classe",
            "observacoes",
        ]
        worksheet.append(headers)
        worksheet.append(
            [
                "CL-0001",
                "",
                "",
                "EQ-0001",
                "Manômetro analógico",
                "Wika",
                "232.50",
                "SN-12345",
                "PT-101",
                "Linha 1",
                "ativo",
                "2026-12-31",
                "sim",
                "0 a 10 bar",
                "10 bar",
                "0.1000",
                "bar",
                "A",
                "Cadastro inicial via importação",
            ]
        )
        for column_cells in worksheet.columns:
            max_length = max(len(str(cell.value or "")) for cell in column_cells)
            worksheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 15), 28)

        output = BytesIO()
        workbook.save(output)
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="modelo_importacao_instrumentos.xlsx"'
        return response

    def exportar_excel_view(self, request):
        changelist = self.get_changelist_instance(request)
        queryset = changelist.get_queryset(request).select_related("cliente").prefetch_related("padroes")

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Instrumentos"
        headers = [
            "cliente_codigo",
            "cliente_razao_social",
            "cliente_cnpj",
            "codigo",
            "nome_servico",
            "marca",
            "modelo",
            "numero_serie",
            "tag",
            "local_instalacao",
            "status",
            "proxima_calibracao",
            "ativo",
            "faixa_medicao",
            "capacidade_total",
            "menor_resolucao",
            "unidade",
            "classe",
            "observacoes",
            "padroes",
        ]
        worksheet.append(headers)

        for instrumento in queryset:
            try:
                tecnico = instrumento.tecnico
            except InstrumentoTecnico.DoesNotExist:
                tecnico = None

            worksheet.append(
                [
                    getattr(instrumento.cliente, "codigo", ""),
                    getattr(instrumento.cliente, "razao_social", ""),
                    getattr(instrumento.cliente, "cnpj", ""),
                    instrumento.codigo,
                    instrumento.descricao,
                    instrumento.marca,
                    instrumento.modelo,
                    instrumento.numero_serie,
                    instrumento.tag,
                    instrumento.local_instalacao,
                    instrumento.status,
                    instrumento.proxima_calibracao.isoformat() if instrumento.proxima_calibracao else "",
                    "sim" if instrumento.ativo else "nao",
                    getattr(tecnico, "faixa_medicao", "") if tecnico else "",
                    getattr(tecnico, "capacidade_total", "") if tecnico else "",
                    str(getattr(tecnico, "menor_resolucao", "") or "") if tecnico else "",
                    getattr(tecnico, "unidade", "") if tecnico else "",
                    getattr(tecnico, "classe", "") if tecnico else "",
                    getattr(tecnico, "observacoes", "") if tecnico else "",
                    ", ".join(instrumento.padroes.values_list("codigo", flat=True)),
                ]
            )

        for column_cells in worksheet.columns:
            max_length = max(len(str(cell.value or "")) for cell in column_cells)
            worksheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 15), 32)

        output = BytesIO()
        workbook.save(output)
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="instrumentos_exportados.xlsx"'
        return response

    def _processar_planilha_importacao(self, arquivo):
        nome = (getattr(arquivo, "name", "") or "").lower()
        if not nome.endswith(".xlsx"):
            raise ValueError("Formato inválido. Envie uma planilha .xlsx.")

        try:
            workbook = load_workbook(arquivo, data_only=True)
        except Exception as exc:
            raise ValueError(f"Não foi possível ler a planilha enviada: {exc}") from exc

        worksheet = workbook.active
        linhas = list(worksheet.iter_rows(values_only=True))
        if not linhas:
            raise ValueError("A planilha está vazia.")

        headers = [self._normalizar_cabecalho_excel(valor) for valor in linhas[0]]
        if "codigo" not in headers:
            raise ValueError(
                "A planilha não contém a coluna obrigatória: codigo."
            )
        if "descricao" not in headers and "nome_servico" not in headers:
            raise ValueError(
                "A planilha deve conter a coluna obrigatória 'nome_servico' ou 'descricao'."
            )

        criados = 0
        ignorados = 0
        sem_tag = 0
        erros = []
        for indice, valores in enumerate(linhas[1:], start=2):
            registro = {
                headers[posicao]: valores[posicao] if posicao < len(valores) else None
                for posicao in range(len(headers))
                if headers[posicao]
            }
            if self._linha_excel_vazia(registro):
                ignorados += 1
                continue
            if not self._texto_excel(registro.get("tag")):
                sem_tag += 1
            try:
                with transaction.atomic():
                    self._criar_instrumento_importado(registro)
                criados += 1
            except Exception as exc:
                erros.append(f"Linha {indice}: {exc}")

        return {"criados": criados, "ignorados": ignorados, "sem_tag": sem_tag, "erros": erros}

    def _criar_instrumento_importado(self, registro):
        cliente = self._resolver_cliente_importacao(registro)
        codigo = self._texto_excel(registro.get("codigo"))
        descricao = self._texto_excel(registro.get("nome_servico")) or self._texto_excel(registro.get("descricao"))
        numero_serie = self._texto_excel(registro.get("numero_serie"))
        tag = self._texto_excel(registro.get("tag"))

        if not codigo:
            raise ValueError("campo 'codigo' é obrigatório.")
        if not descricao:
            raise ValueError("campo 'nome_servico' é obrigatório.")
        if not cliente:
            raise ValueError(
                "cliente não encontrado. Informe 'cliente_codigo', 'cliente_cnpj' ou 'cliente_razao_social'."
            )
        if Instrumento.objects.filter(codigo__iexact=codigo).exists():
            raise ValueError(f"já existe instrumento cadastrado com o código '{codigo}'.")
        if tag and Instrumento.objects.filter(
            cliente=cliente,
            tag__iexact=tag,
        ).exists():
            raise ValueError(
                "já existe instrumento para este cliente com o mesmo número de série e a mesma TAG."
            )

        instrumento = Instrumento(
            cliente=cliente,
            codigo=codigo,
            descricao=descricao,
            marca=self._texto_excel(registro.get("marca")),
            modelo=self._texto_excel(registro.get("modelo")),
            numero_serie=numero_serie or None,
            tag=tag,
            local_instalacao=self._texto_excel(registro.get("local_instalacao")),
            status=self._normalizar_status_importacao(registro.get("status")),
            proxima_calibracao=self._normalizar_data_excel(registro.get("proxima_calibracao")),
            ativo=self._normalizar_booleano_excel(registro.get("ativo"), default=True),
        )
        instrumento.full_clean()
        instrumento.save()

        tecnico_campos = {
            "faixa_medicao": self._texto_excel(registro.get("faixa_medicao")),
            "capacidade_total": self._texto_excel(registro.get("capacidade_total")),
            "menor_resolucao": self._normalizar_decimal_excel(registro.get("menor_resolucao")),
            "unidade": self._texto_excel(registro.get("unidade")),
            "classe": self._texto_excel(registro.get("classe")),
            "observacoes": self._texto_excel(registro.get("observacoes")),
        }
        if any(valor not in (None, "") for valor in tecnico_campos.values()):
            InstrumentoTecnico.objects.update_or_create(
                instrumento=instrumento,
                defaults=tecnico_campos,
            )

    def _resolver_cliente_importacao(self, registro):
        cliente_codigo = self._texto_excel(registro.get("cliente_codigo"))
        cliente_cnpj = self._texto_excel(registro.get("cliente_cnpj"))
        cliente_razao = self._texto_excel(registro.get("cliente_razao_social"))

        if cliente_codigo:
            cliente = Cliente.objects.filter(codigo__iexact=cliente_codigo).first()
            if cliente:
                return cliente
        if cliente_cnpj:
            cliente = Cliente.objects.filter(cnpj__iexact=cliente_cnpj).first()
            if cliente:
                return cliente
        if cliente_razao:
            cliente = Cliente.objects.filter(razao_social__iexact=cliente_razao).first()
            if cliente:
                return cliente
        return None

    @staticmethod
    def _texto_excel(valor):
        if valor is None:
            return ""
        if isinstance(valor, str):
            return valor.strip()
        return str(valor).strip()

    @staticmethod
    def _normalizar_cabecalho_excel(valor):
        texto = InstrumentoAdmin._texto_excel(valor).lower()
        substituicoes = {
            "á": "a",
            "à": "a",
            "ã": "a",
            "â": "a",
            "é": "e",
            "ê": "e",
            "í": "i",
            "ó": "o",
            "ô": "o",
            "õ": "o",
            "ú": "u",
            "ç": "c",
        }
        for origem, destino in substituicoes.items():
            texto = texto.replace(origem, destino)
        return texto.replace(" ", "_")

    @staticmethod
    def _linha_excel_vazia(registro):
        return not any(valor not in (None, "") for valor in registro.values())

    @staticmethod
    def _normalizar_status_importacao(valor):
        texto = InstrumentoAdmin._texto_excel(valor).lower()
        if texto in {"", "ativo"}:
            return "ativo"
        if texto == "inativo":
            return "inativo"
        if texto in {"manutencao", "manutenção", "em manutencao", "em manutenção"}:
            return "manutencao"
        raise ValueError(f"status inválido: '{valor}'. Use ativo, inativo ou manutencao.")

    @staticmethod
    def _normalizar_booleano_excel(valor, default=True):
        texto = InstrumentoAdmin._texto_excel(valor).lower()
        if texto == "":
            return default
        if texto in {"1", "sim", "s", "true", "verdadeiro", "ativo"}:
            return True
        if texto in {"0", "nao", "não", "n", "false", "falso", "inativo"}:
            return False
        raise ValueError(f"valor booleano inválido: '{valor}'. Use sim/não.")

    @staticmethod
    def _normalizar_data_excel(valor):
        if valor in (None, ""):
            return None
        if isinstance(valor, datetime):
            return valor.date()
        if hasattr(valor, "year") and hasattr(valor, "month") and hasattr(valor, "day"):
            return valor
        texto = InstrumentoAdmin._texto_excel(valor)
        for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(texto, formato).date()
            except ValueError:
                continue
        raise ValueError(f"data inválida: '{valor}'. Use YYYY-MM-DD ou DD/MM/AAAA.")

    @staticmethod
    def _normalizar_decimal_excel(valor):
        if valor in (None, ""):
            return None
        if isinstance(valor, Decimal):
            return valor
        try:
            return Decimal(str(valor).replace(",", "."))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"valor decimal inválido: '{valor}'.") from exc

    def ver_certificados_padroes(self, obj):
        links = [
            (p.certificado.url, p.codigo)
            for p in obj.padroes.all()
            if p.certificado
        ]
        if not links:
            return "?"
        return format_html_join(
            mark_safe("<br>"),
            '<a href="{}" target="_blank">{}</a>',
            links,
        )

    ver_certificados_padroes.short_description = "Certificados dos Padrões"


# =========================
# CALIBRAÇÃO
# =========================
class CalibracaoAnexoInline(admin.TabularInline):
    model = CalibracaoAnexo
    extra = 1


class TurbidezPadraoInline(admin.TabularInline):
    model = TurbidezPadraoUtilizado
    form = TurbidezPadraoAdminForm
    extra = 1
    autocomplete_fields = ("padrao",)
    fields = (
        "tipo",
        "ordem",
        "padrao",
        "resultado_preparacao",
        "codigo",
        "descricao",
        "numero_certificado",
        "laboratorio_emitente",
        "data_calibracao",
        "validade",
        "resolucao",
        "incerteza",
        "fator_k",
        "graus_liberdade",
        "unidade",
        "valor_nominal",
    )
    readonly_fields = ("resultado_preparacao",)
    verbose_name = "Padrão"
    verbose_name_plural = "Padrão mãe e padrões secundários preparados por diluição"


class TurbidezVerificacaoInline(admin.TabularInline):
    model = TurbidezVerificacaoPonto
    form = TurbidezVerificacaoAdminForm
    extra = 5
    fields = ("ordem", "valor_padrao", "leitura", "erro", "criterio", "resultado")
    readonly_fields = ("erro",)
    verbose_name = "Ponto de verificação"
    verbose_name_plural = "Verificação"


class TurbidezCalibracaoInline(admin.TabularInline):
    model = TurbidezCalibracaoPonto
    form = TurbidezCalibracaoAdminForm
    extra = 9
    fields = (
        "ordem",
        "valor_referencia",
        "leitura_1",
        "leitura_2",
        "leitura_3",
        "media",
        "erro",
        "ema",
        "criterio",
    )
    readonly_fields = ("media", "erro", "ema")
    verbose_name = "Ponto de calibração"
    verbose_name_plural = "Calibração"


class TurbidezIncertezaInline(admin.TabularInline):
    model = TurbidezIncertezaPonto
    form = TurbidezIncertezaAdminForm
    extra = 9
    fields = (
        "ordem",
        "repetibilidade",
        "resolucao_instrumento",
        "incerteza_padrao",
        "resolucao_padrao",
        "incerteza_curva",
        "incerteza_turbidimetro",
        "fator_k",
        "graus_liberdade",
        "incerteza_padrao_combinada",
        "incerteza_expandida",
    )
    readonly_fields = ("incerteza_padrao_combinada", "incerteza_expandida")
    verbose_name = "Ponto de incerteza"
    verbose_name_plural = "Incerteza"

    def get_readonly_fields(self, request, obj=None):
        campos_calculados = ("incerteza_padrao_combinada", "incerteza_expandida")
        if obj and not request.user.is_superuser:
            return (
                "ordem",
                "repetibilidade",
                "resolucao_instrumento",
                "incerteza_padrao",
                "resolucao_padrao",
                "incerteza_curva",
                "incerteza_turbidimetro",
                "fator_k",
                "graus_liberdade",
                *campos_calculados,
            )
        return campos_calculados


class ColorimetroPadraoInline(admin.TabularInline):
    model = ColorimetroPadraoUtilizado
    form = ColorimetroPadraoAdminForm
    extra = 1
    autocomplete_fields = ("padrao",)
    fields = (
        "tipo",
        "ordem",
        "padrao",
        "codigo",
        "descricao",
        "numero_certificado",
        "laboratorio_emitente",
        "data_calibracao",
        "validade",
        "resolucao",
        "incerteza",
        "fator_k",
        "graus_liberdade",
        "unidade",
        "valor_nominal",
    )
    verbose_name = "Padrão"
    verbose_name_plural = "Padrões"


class ColorimetroVerificacaoInline(admin.TabularInline):
    model = ColorimetroVerificacaoPonto
    form = ColorimetroVerificacaoAdminForm
    extra = 5
    fields = ("ordem", "valor_padrao", "leitura", "erro", "criterio", "criterio_tipo", "criterio_origem", "resultado")
    readonly_fields = ("erro",)
    verbose_name = "Ponto de verificação"
    verbose_name_plural = "Verificação"


class ColorimetroCalibracaoInline(admin.TabularInline):
    model = ColorimetroCalibracaoPonto
    form = ColorimetroCalibracaoAdminForm
    extra = 9
    fields = (
        "ordem",
        "valor_referencia",
        "leitura_1",
        "leitura_2",
        "leitura_3",
        "media",
        "erro",
        "ema",
        "criterio",
        "criterio_tipo",
        "criterio_origem",
    )
    readonly_fields = ("media", "erro", "ema")
    verbose_name = "Ponto de calibração"
    verbose_name_plural = "Calibração"


class ColorimetroIncertezaInline(admin.TabularInline):
    model = ColorimetroIncertezaPonto
    form = ColorimetroIncertezaAdminForm
    extra = 9
    fields = (
        "ordem",
        "repetibilidade",
        "resolucao_instrumento",
        "incerteza_padrao",
        "resolucao_padrao",
        "incerteza_curva",
        "fator_k",
        "graus_liberdade",
        "incerteza_padrao_combinada",
        "incerteza_expandida",
    )
    readonly_fields = ("incerteza_padrao_combinada", "incerteza_expandida")
    verbose_name = "Ponto de incerteza"
    verbose_name_plural = "Incerteza"


class PressaoPadraoInlineForm(ThreeDecimalAdminForm):
    class Meta:
        model = PressaoPadraoUtilizado
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("DELETE"):
            return cleaned_data

        padrao = cleaned_data.get("padrao")

        possui_dados = any(
            cleaned_data.get(campo) not in (None, "")
            for campo in (
                "padrao",
                "codigo",
                "descricao",
                "numero_certificado",
                "laboratorio_emitente",
                "data_calibracao",
                "validade",
                "incerteza",
                "resolucao",
            )
        )
        if not possui_dados:
            return cleaned_data

        campos_criticos = {
            "codigo": "Identificação do padrão",
            "descricao": "Descrição do padrão",
            "numero_certificado": "Número do certificado",
            "laboratorio_emitente": "Laboratório",
            "data_calibracao": "Data da calibração",
            "validade": "Data da validade",
        }
        for campo, rotulo in campos_criticos.items():
            valor = cleaned_data.get(campo)
            if valor in (None, "") and padrao is not None:
                if campo == "validade":
                    valor = getattr(padrao, "vencimento", None)
                else:
                    valor = getattr(padrao, campo, None)
            if valor in (None, ""):
                self.add_error(campo, f"{rotulo} é obrigatória para rastreabilidade metrológica.")

        return cleaned_data


class PressaoPadraoInline(admin.TabularInline):
    model = PressaoPadraoUtilizado
    form = PressaoPadraoInlineForm
    extra = 3
    fields = (
        "tipo",
        "ordem",
        "padrao",
        "codigo",
        "descricao",
        "tipo_padrao",
        "numero_certificado",
        "laboratorio_emitente",
        "data_calibracao",
        "validade",
        "resolucao",
        "incerteza",
        "unidade",
        "status_validade",
    )
    autocomplete_fields = ("padrao",)
    readonly_fields = ("status_validade",)
    verbose_name = "Padrão utilizado"
    verbose_name_plural = "Padrões"


class PressaoCalibracaoInlineForm(ThreeDecimalAdminForm):
    class Meta:
        model = PressaoCalibracaoPonto
        fields = "__all__"
        labels = {
            "valor_referencia": "Padrão em",
            "valor_referencia_convertido": "Padrão convertido",
            "leitura_1": "Crescente 1ª série",
            "leitura_2": "Crescente 2ª série",
            "leitura_3": "Decrescente 1ª série",
            "leitura_4": "Decrescente 2ª série",
            "media": "Média",
            "desvio_padrao": "Desvio padrão",
            "erro": "Erro do instrumento",
            "erro_percentual": "Erro (%)",
            "ema": "EMA",
            "criterio": "Critério de aceitação",
            "criterio_origem": "Origem da tolerância",
            "criterio_referencia": "Referência do critério",
            "resultado": "Resultado",
        }

    def clean(self):
        cleaned_data = super().clean()
        if self.instance and self.instance.pk and not cleaned_data.get("DELETE"):
            for campo in ("leitura_1", "leitura_2", "leitura_3", "leitura_4"):
                if cleaned_data.get(campo) is None and getattr(self.instance, campo) is not None:
                    cleaned_data[campo] = getattr(self.instance, campo)
        return cleaned_data


class CalibracaoPressaoAdminForm(ThreeDecimalAdminForm):
    class Meta:
        model = CalibracaoPressao
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        campos_criticos = {
            "temperatura_inicial": "Temperatura inicial",
            "temperatura_final": "Temperatura final",
            "umidade_inicial": "Umidade inicial",
            "umidade_final": "Umidade final",
        }
        for campo, rotulo in campos_criticos.items():
            if cleaned_data.get(campo) in (None, ""):
                self.add_error(campo, f"{rotulo} é obrigatória para emissão do certificado.")

        if not cleaned_data.get("procedimento_documento") and not (cleaned_data.get("procedimento_numero") or "").strip():
            self.add_error(
                "procedimento_documento",
                "Informe o procedimento aplicável para emissão do certificado.",
            )

        return cleaned_data


class PressaoCalibracaoInline(admin.TabularInline):
    model = PressaoCalibracaoPonto
    form = PressaoCalibracaoInlineForm
    extra = 10
    fields = (
        "ordem",
        "valor_referencia",
        "valor_referencia_convertido",
        "leitura_1",
        "leitura_2",
        "leitura_3",
        "leitura_4",
        "media",
        "desvio_padrao",
        "erro",
        "erro_percentual",
        "ema",
        "criterio",
        "criterio_origem",
        "criterio_referencia",
        "resultado",
    )
    readonly_fields = (
        "valor_referencia_convertido",
        "media",
        "desvio_padrao",
        "erro",
        "erro_percentual",
        "ema",
    )
    verbose_name = "Ponto de calibração"
    verbose_name_plural = "Calibração"


class PressaoIncertezaInline(admin.TabularInline):
    model = PressaoIncertezaPonto
    form = PressaoIncertezaAdminForm
    extra = 10
    fields = (
        "ordem",
        "repetibilidade",
        "resolucao_instrumento",
        "resolucao_padrao",
        "incerteza_padrao",
        "incerteza_curva",
        "fator_k",
        "graus_liberdade",
        "incerteza_padrao_combinada",
        "incerteza_expandida",
    )
    readonly_fields = ("incerteza_padrao_combinada", "incerteza_expandida")
    verbose_name = "Ponto de incerteza"
    verbose_name_plural = "Incerteza"


class CalibracaoEmpresaFilter(admin.SimpleListFilter):
    title = "empresa"
    parameter_name = "empresa"

    def lookups(self, request, model_admin):
        clientes = (
            Cliente.objects.filter(instrumentos__calibracoes__isnull=False)
            .distinct()
            .order_by("codigo", "razao_social")
        )
        return [(cliente.pk, str(cliente)) for cliente in clientes]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(instrumento__cliente_id=self.value())
        return queryset


class CalibracaoEquipamentoFilter(admin.SimpleListFilter):
    title = "equipamento"
    parameter_name = "equipamento"

    def lookups(self, request, model_admin):
        instrumentos = (
            Instrumento.objects.filter(calibracoes__isnull=False)
            .distinct()
            .order_by("codigo", "descricao")
        )
        return [(instrumento.pk, str(instrumento)) for instrumento in instrumentos]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(instrumento_id=self.value())
        return queryset


@admin.register(Calibracao)
class CalibracaoAdmin(OrdemServicoAutomaticaAdminMixin, admin.ModelAdmin):
    form = CalibracaoAdminForm
    change_list_template = "admin/calibracao/calibracao/change_list.html"
    change_form_template = "admin/calibracao/calibracao/change_form.html"

    list_display = (
        "instrumento",
        "ordem_servico",
        "data_calibracao",
        "validade",
        "certificado_numero",
        "resultado",
        "local_calibracao",
        "empresa_emissora",
        "origem_certificado",
        "ver_anexo",
    )

    list_filter = (
        CalibracaoEmpresaFilter,
        "data_calibracao",
        CalibracaoEquipamentoFilter,
        "resultado",
        "empresa_emissora",
        "origem_certificado",
        "status",
        "local_calibracao",
    )

    search_fields = (
        "instrumento__cliente__codigo",
        "instrumento__cliente__razao_social",
        "instrumento__cliente__cnpj",
        "instrumento__codigo",
        "instrumento__descricao",
        "ordem_servico",
        "certificado_numero",
    )

    autocomplete_fields = ("instrumento",)
    list_select_related = ("instrumento", "instrumento__cliente")
    date_hierarchy = "data_calibracao"

    def save_model(self, request, obj, form, change):
        if change and form.changed_data:
            from certificados.services import certificado_publico_da_calibracao
            from documentos.services.assinaturas import substituir_assinaturas_do_objeto

            # Depois da publicação, o documento assinado é um snapshot imutável.
            # Alterações na origem não podem reclassificar silenciosamente o PDF público.
            if not certificado_publico_da_calibracao(obj):
                substituir_assinaturas_do_objeto(obj)
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        if obj is None:
            return True
        return not motivos_protecao_exclusao(obj)

    @staticmethod
    def _mensagem_protecao_exclusao(obj):
        motivos = motivos_protecao_exclusao(obj)
        return (
            f"A calibração {obj} não pode ser excluída porque possui resultado "
            f"oficial: {', '.join(motivos)}. Preserve o registro e utilize um "
            "fluxo controlado de cancelamento."
        )

    def delete_view(self, request, object_id, extra_context=None):
        obj = self.get_object(request, object_id)
        if obj is not None and motivos_protecao_exclusao(obj):
            if not super().has_delete_permission(request, obj):
                raise PermissionDenied
            self.message_user(
                request,
                self._mensagem_protecao_exclusao(obj),
                level=messages.ERROR,
            )
            return redirect(
                reverse(
                    f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
                    args=(obj.pk,),
                )
            )
        return super().delete_view(request, object_id, extra_context)

    def _delete_legacy_turbidimetro_relations(self, calibracao_id):
        legacy_tables = (
            "calibracao_turbidimetroverificacaoponto",
            "calibracao_turbidimetrocalibracaoponto",
            "calibracao_calibracaoturbidimetro",
        )
        existing_tables = set(connection.introspection.table_names())
        with connection.cursor() as cursor:
            for table_name in legacy_tables:
                if table_name not in existing_tables:
                    continue
                cursor.execute(
                    f"DELETE FROM {table_name} WHERE calibracao_id = %s",
                    [calibracao_id],
                )

    def delete_model(self, request, obj):
        if motivos_protecao_exclusao(obj):
            raise PermissionDenied(self._mensagem_protecao_exclusao(obj))
        with transaction.atomic():
            self._delete_legacy_turbidimetro_relations(obj.pk)
            obj.delete()

    def delete_queryset(self, request, queryset):
        objetos = list(queryset)
        protegidos = [obj for obj in objetos if motivos_protecao_exclusao(obj)]
        if protegidos:
            identificadores = ", ".join(str(obj) for obj in protegidos[:5])
            complemento = "" if len(protegidos) <= 5 else f" e mais {len(protegidos) - 5}"
            self.message_user(
                request,
                "Nenhuma calibração foi excluída. A seleção contém registros "
                f"protegidos por resultado oficial: {identificadores}{complemento}.",
                level=messages.ERROR,
            )
            return
        with transaction.atomic():
            for obj in objetos:
                self._delete_legacy_turbidimetro_relations(obj.pk)
                obj.delete()

    def changelist_view(self, request, extra_context=None):
        from certificados.models import CertificadoCalibracao
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Q

        extra_context = extra_context or {}
        empresa_atual = request.GET.get("empresa", "")
        equipamentos = Instrumento.objects.filter(calibracoes__isnull=False).distinct()
        if empresa_atual:
            equipamentos = equipamentos.filter(cliente_id=empresa_atual)

        content_type_calibracao_geral = ContentType.objects.get_for_model(
            Calibracao, for_concrete_model=False
        )
        certificados_especializados_qs = (
            CertificadoCalibracao.objects
            .select_related("cliente", "instrumento", "documento", "calibracao_content_type")
            .filter(calibracao_content_type__app_label="calibracao")
            .exclude(calibracao_content_type=content_type_calibracao_geral)
        )
        consulta = request.GET.get("q", "").strip()
        if consulta:
            certificados_especializados_qs = certificados_especializados_qs.filter(
                Q(numero__icontains=consulta)
                | Q(cliente__codigo__icontains=consulta)
                | Q(cliente__razao_social__icontains=consulta)
                | Q(cliente__nome_empresa__icontains=consulta)
                | Q(instrumento__codigo__icontains=consulta)
                | Q(instrumento__descricao__icontains=consulta)
                | Q(instrumento__numero_serie__icontains=consulta)
                | Q(documento__nome_original__icontains=consulta)
            )
        if empresa_atual:
            certificados_especializados_qs = certificados_especializados_qs.filter(
                cliente_id=empresa_atual
            )
        equipamento_atual = request.GET.get("equipamento", "")
        if equipamento_atual:
            certificados_especializados_qs = certificados_especializados_qs.filter(
                instrumento_id=equipamento_atual
            )
        data_atual = request.GET.get("data_calibracao__exact", "")
        if data_atual:
            certificados_especializados_qs = certificados_especializados_qs.filter(
                data_calibracao=data_atual
            )

        certificados_especializados = []
        for certificado in certificados_especializados_qs.order_by(
            "-data_calibracao", "numero"
        ):
            try:
                calibracao_origem = certificado.calibracao
            except (ValidationError, ValueError):
                calibracao_origem = None
            if calibracao_origem is None:
                continue
            origem_url = reverse(
                "admin:"
                f"{certificado.calibracao_content_type.app_label}_"
                f"{certificado.calibracao_content_type.model}_change",
                args=[certificado.calibracao_object_id],
            )
            certificados_especializados.append({
                "certificado": certificado,
                "tipo": calibracao_origem._meta.verbose_name,
                "origem_url": origem_url,
                "cadastro_url": reverse(
                    "admin:certificados_certificadocalibracao_change",
                    args=[certificado.pk],
                ),
                "download_url": (
                    reverse("documentos:download", args=[certificado.documento_id])
                    if certificado.documento_id
                    and request.user.has_perm("documentos.view_documentoarquivo")
                    else ""
                ),
            })

        extra_context.update({
            "filtro_empresa_atual": empresa_atual,
            "filtro_data_calibracao_atual": request.GET.get("data_calibracao__exact", ""),
            "filtro_equipamento_atual": request.GET.get("equipamento", ""),
            "certificados_especializados": certificados_especializados,
            "quantidade_certificados_especializados": len(certificados_especializados),
            "empresas_certificado_rapido": (
                Cliente.objects.filter(instrumentos__calibracoes__isnull=False)
                .distinct()
                .order_by("codigo", "razao_social")
            ),
            "equipamentos_certificado_rapido": equipamentos.order_by("codigo", "descricao"),
        })
        response = super().changelist_view(request, extra_context=extra_context)
        if hasattr(response, "context_data") and response.context_data and "cl" in response.context_data:
            changelist = response.context_data["cl"]
            response.context_data["quantidade_filtrada_certificados"] = changelist.result_count
        return response

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "importar-excel/",
                self.admin_site.admin_view(self.importar_excel_view),
                name="calibracao_calibracao_importar_excel",
            ),
            path(
                "modelo-importacao/",
                self.admin_site.admin_view(self.download_modelo_importacao_view),
                name="calibracao_calibracao_modelo_importacao",
            ),
            path(
                "<int:pk>/publicar-certificado/",
                self.admin_site.admin_view(self.publicar_certificado_view),
                name="calibracao_calibracao_publicar_certificado",
            ),
            path(
                "<int:pk>/assinar-certificado/",
                self.admin_site.admin_view(self.assinar_certificado_view),
                name="calibracao_calibracao_assinar_certificado",
            ),
            path(
                "<int:pk>/download-certificado-assinado/",
                self.admin_site.admin_view(self.download_certificado_assinado_view),
                name="calibracao_calibracao_download_certificado_assinado",
            ),
        ]
        return custom_urls + urls

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            from certificados.services import (
                assinatura_atual_da_calibracao,
                certificado_publico_da_calibracao,
            )

            calibracao = self.get_object(request, object_id)
            if calibracao:
                certificado_publico = certificado_publico_da_calibracao(calibracao)
                assinatura_digital = assinatura_atual_da_calibracao(calibracao)
                extra_context["certificado_publico"] = certificado_publico
                extra_context["assinatura_digital"] = assinatura_digital
                pode_controlar = (
                    self.has_change_permission(request, calibracao)
                    and request.user.has_perm("certificados.add_certificadocalibracao")
                )
                extra_context["pode_assinar_certificado"] = bool(
                    pode_controlar
                    and not certificado_publico
                    and calibracao.status == "concluida"
                    and calibracao.certificado_arquivo
                    and calibracao.origem_certificado
                    == Calibracao.OrigemCertificado.EMITIDO_DS
                )
                extra_context["pode_publicar_certificado"] = (
                    pode_controlar
                    and not certificado_publico
                    and bool(assinatura_digital)
                    and calibracao.origem_certificado
                    == Calibracao.OrigemCertificado.EMITIDO_DS
                )
        return super().changeform_view(request, object_id, form_url, extra_context)

    def assinar_certificado_view(self, request, pk):
        calibracao = get_object_or_404(Calibracao, pk=pk)
        if not self.has_change_permission(request, calibracao) or not request.user.has_perm(
            "certificados.add_certificadocalibracao"
        ):
            raise PermissionDenied

        form = AssinaturaCertificadoA1Form(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            from certificados.services import assinar_calibracao_a1

            try:
                assinar_calibracao_a1(
                    calibracao,
                    certificado_a1=form.cleaned_data["certificado_a1"].read(),
                    senha=form.cleaned_data["senha"],
                    usuario=request.user,
                )
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                self.message_user(
                    request,
                    "Certificado assinado com a integridade criptográfica verificada. "
                    "Revise o PDF assinado antes da publicação.",
                    messages.SUCCESS,
                )
                return redirect("admin:calibracao_calibracao_change", pk)

        return render(
            request,
            "admin/calibracao/calibracao/assinar_certificado.html",
            {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "original": calibracao,
                "title": f"Assinar certificado {calibracao.certificado_numero}",
                "form": form,
                "change_url": reverse("admin:calibracao_calibracao_change", args=[pk]),
            },
        )

    def download_certificado_assinado_view(self, request, pk):
        calibracao = get_object_or_404(Calibracao, pk=pk)
        if not self.has_view_permission(request, calibracao):
            raise PermissionDenied

        from certificados.services import assinatura_atual_da_calibracao
        from documentos.services.assinaturas import abrir_pdf_assinado
        from documentos.services.documentos import verificar_integridade

        assinatura = assinatura_atual_da_calibracao(calibracao)
        if not assinatura:
            self.message_user(
                request,
                "Não existe assinatura válida para o PDF atual. Assine novamente.",
                messages.ERROR,
            )
            return redirect("admin:calibracao_calibracao_change", pk)
        integro, _motivo = verificar_integridade(assinatura.documento_assinado)
        if not integro:
            self.message_user(
                request,
                "O PDF assinado não passou na verificação de integridade e foi bloqueado.",
                messages.ERROR,
            )
            return redirect("admin:calibracao_calibracao_change", pk)
        numero = re.sub(
            r"[^A-Za-z0-9._-]+",
            "-",
            calibracao.certificado_numero or "certificado",
        ).strip(".-")
        return FileResponse(
            abrir_pdf_assinado(assinatura),
            as_attachment=True,
            filename=f"{numero or 'certificado'}-assinado.pdf",
        )

    def publicar_certificado_view(self, request, pk):
        calibracao = get_object_or_404(Calibracao, pk=pk)
        if request.method != "POST":
            self.message_user(request, "A publicação deve ser confirmada pelo botão da calibração.", messages.ERROR)
            return redirect("admin:calibracao_calibracao_change", pk)
        if not self.has_change_permission(request, calibracao) or not request.user.has_perm(
            "certificados.add_certificadocalibracao"
        ):
            self.message_user(request, "Você não possui permissão para publicar certificados.", messages.ERROR)
            return redirect("admin:calibracao_calibracao_change", pk)

        from certificados.services import publicar_calibracao_existente

        try:
            certificado, criado = publicar_calibracao_existente(calibracao, usuario=request.user)
        except ValidationError as exc:
            self.message_user(request, " ".join(exc.messages), messages.ERROR)
        else:
            consulta_url = reverse("certificados:consulta", args=[certificado.uuid_publico])
            if criado:
                mensagem = format_html(
                    'Certificado publicado com cópia imutável. <a href="{}" target="_blank">Abrir consulta pública</a>.',
                    consulta_url,
                )
                self.message_user(request, mensagem, messages.SUCCESS)
            else:
                mensagem = format_html(
                    'Esta calibração já possui publicação. <a href="{}" target="_blank">Abrir consulta pública</a>.',
                    consulta_url,
                )
                self.message_user(request, mensagem, messages.INFO)
        return redirect("admin:calibracao_calibracao_change", pk)

    def importar_excel_view(self, request):
        if not self.has_add_permission(request):
            self.message_user(request, "Voce nao tem permissao para importar calibracoes.", messages.ERROR)
            return redirect("admin:calibracao_calibracao_changelist")

        resultado = None
        if request.method == "POST":
            form = CalibracaoImportForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    resultado = self._validar_planilha_calibracoes(form.cleaned_data["arquivo"])
                except ValueError as exc:
                    self.message_user(request, str(exc), messages.ERROR)
                else:
                    if resultado["erros"]:
                        self.message_user(
                            request,
                            "Planilha validada com erros. Corrija antes de importar.",
                            messages.ERROR,
                        )
                    else:
                        self.message_user(
                            request,
                            "Planilha validada. Nesta etapa nenhum certificado foi gravado automaticamente.",
                            messages.WARNING,
                        )
        else:
            form = CalibracaoImportForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Importar calibracoes por Excel",
            "opts": self.model._meta,
            "form": form,
            "resultado": resultado,
            "download_model_url": reverse("admin:calibracao_calibracao_modelo_importacao"),
        }
        return render(request, "admin/calibracao/calibracao/importar_excel.html", context)

    def download_modelo_importacao_view(self, request):
        workbook = Workbook()
        workbook.remove(workbook.active)
        self._criar_aba_instrucoes(workbook)

        for nome_aba, (cabecalhos, exemplo) in CALIBRACAO_IMPORT_SHEETS.items():
            self._criar_aba_modelo_importacao(workbook, nome_aba, cabecalhos, exemplo)

        buffer = BytesIO()
        workbook.save(buffer)
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="modelo_importacao_calibracoes.xlsx"'
        return response

    def _criar_aba_instrucoes(self, workbook):
        sheet = workbook.create_sheet("INSTRUCOES")
        linhas = [
            ["Modelo oficial para importacao de calibracoes"],
            [""],
            ["Fluxo recomendado"],
            ["1. Preencha uma linha na aba CALIBRACOES para cada certificado."],
            ["2. Relacione padroes e leituras usando o mesmo certificado_numero."],
            ["3. Use tipo_calibracao: pressao, colorimetro, ph, turbidez ou condutividade."],
            ["4. Cliente deve ser identificado por codigo, CNPJ ou razao social."],
            ["5. Instrumento deve ser identificado por codigo, tag ou numero de serie."],
            ["6. Datas devem ser preenchidas como data do Excel ou AAAA-MM-DD."],
            ["7. Esta primeira importacao faz pre-validacao; gravacao automatica sera habilitada por tipo."],
            [""],
            ["Risco tecnico"],
            ["Nao altere nomes de abas ou cabecalhos. Isso compromete rastreabilidade e preenchimento automatico."],
        ]
        for linha in linhas:
            sheet.append(linha)
        sheet.column_dimensions["A"].width = 110

    def _criar_aba_modelo_importacao(self, workbook, nome_aba, cabecalhos, exemplo):
        sheet = workbook.create_sheet(nome_aba)
        sheet.append(cabecalhos)
        sheet.append(exemplo)
        sheet.freeze_panes = "A2"
        for column_cells in sheet.columns:
            header = str(column_cells[0].value or "")
            sheet.column_dimensions[column_cells[0].column_letter].width = max(14, min(34, len(header) + 4))

    def _validar_planilha_calibracoes(self, arquivo):
        nome_arquivo = (getattr(arquivo, "name", "") or "").lower()
        if not nome_arquivo.endswith(".xlsx"):
            raise ValueError("Envie um arquivo .xlsx. Arquivos .xls, .csv ou pdf nao sao aceitos neste importador.")

        workbook = load_workbook(arquivo, data_only=True)
        abas_faltantes = [
            nome for nome in CALIBRACAO_IMPORT_REQUIRED_SHEETS
            if nome not in workbook.sheetnames
        ]
        if abas_faltantes:
            raise ValueError("Planilha incompleta. Abas obrigatorias ausentes: " + ", ".join(abas_faltantes))

        resultado = {
            "arquivo": getattr(arquivo, "name", ""),
            "abas": [],
            "erros": [],
            "avisos": [],
            "total_calibracoes": 0,
            "tipos": {},
        }

        for nome_aba, (cabecalhos_esperados, _exemplo) in CALIBRACAO_IMPORT_SHEETS.items():
            if nome_aba not in workbook.sheetnames:
                resultado["avisos"].append(f"Aba opcional ausente: {nome_aba}.")
                continue
            sheet = workbook[nome_aba]
            cabecalhos = self._cabecalhos_planilha(sheet)
            ausentes = [
                cabecalho for cabecalho in cabecalhos_esperados
                if cabecalho not in cabecalhos
            ]
            linhas_preenchidas = self._contar_linhas_preenchidas(sheet)
            resultado["abas"].append({
                "nome": nome_aba,
                "linhas": linhas_preenchidas,
                "ausentes": ausentes,
            })
            if ausentes and nome_aba in CALIBRACAO_IMPORT_REQUIRED_SHEETS:
                resultado["erros"].append(
                    f"Aba {nome_aba}: cabecalhos obrigatorios ausentes: {', '.join(ausentes)}."
                )

        self._validar_aba_calibracoes(workbook["CALIBRACOES"], resultado)
        return resultado

    def _cabecalhos_planilha(self, sheet):
        primeira_linha = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), [])
        return [
            InstrumentoAdmin._normalizar_cabecalho_excel(valor)
            for valor in primeira_linha
            if valor not in (None, "")
        ]

    def _contar_linhas_preenchidas(self, sheet):
        total = 0
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not self._linha_planilha_vazia(row):
                total += 1
        return total

    def _linha_planilha_vazia(self, row):
        return not any(valor not in (None, "") for valor in row)

    def _validar_aba_calibracoes(self, sheet, resultado):
        cabecalhos = self._cabecalhos_planilha(sheet)
        indices = {cabecalho: pos for pos, cabecalho in enumerate(cabecalhos)}
        certificados = set()

        for numero_linha, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if self._linha_planilha_vazia(row):
                continue

            def valor(campo):
                indice = indices.get(campo)
                if indice is None or indice >= len(row):
                    return ""
                return InstrumentoAdmin._texto_excel(row[indice])

            tipo = valor("tipo_calibracao").lower()
            certificado_numero = valor("certificado_numero")
            resultado["total_calibracoes"] += 1

            if tipo:
                resultado["tipos"][tipo] = resultado["tipos"].get(tipo, 0) + 1
            if tipo not in CALIBRACAO_IMPORT_TIPOS:
                resultado["erros"].append(
                    f"CALIBRACOES linha {numero_linha}: tipo_calibracao invalido ou vazio ({tipo or '-'})."
                )

            if not certificado_numero:
                resultado["erros"].append(f"CALIBRACOES linha {numero_linha}: certificado_numero e obrigatorio.")
            elif certificado_numero in certificados:
                resultado["erros"].append(
                    f"CALIBRACOES linha {numero_linha}: certificado_numero duplicado na planilha ({certificado_numero})."
                )
            else:
                certificados.add(certificado_numero)

            if not (valor("cliente_codigo") or valor("cliente_cnpj") or valor("cliente_razao_social")):
                resultado["erros"].append(
                    f"CALIBRACOES linha {numero_linha}: informe cliente_codigo, cliente_cnpj ou cliente_razao_social."
                )

            if not (valor("instrumento_codigo") or valor("instrumento_tag") or valor("instrumento_numero_serie")):
                resultado["erros"].append(
                    f"CALIBRACOES linha {numero_linha}: informe instrumento_codigo, instrumento_tag ou instrumento_numero_serie."
                )

            data_calibracao_indice = indices.get("data_calibracao")
            data_calibracao = row[data_calibracao_indice] if data_calibracao_indice is not None and data_calibracao_indice < len(row) else None
            if data_calibracao in (None, ""):
                resultado["erros"].append(f"CALIBRACOES linha {numero_linha}: data_calibracao e obrigatoria.")
            else:
                try:
                    InstrumentoAdmin._normalizar_data_excel(data_calibracao)
                except ValueError as exc:
                    resultado["erros"].append(f"CALIBRACOES linha {numero_linha}: {exc}")

    readonly_fields = (
        "certificado_numero",
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
                "origem_certificado",
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
        if not obj.instrumento:
            return "?"

        links = [
            (p.certificado.url, p.codigo)
            for p in obj.instrumento.padroes.all()
            if p.certificado
        ]
        if not links:
            return "?"
        return format_html_join(
            mark_safe("<br>"),
            '<a href="{}" target="_blank">{}</a>',
            links,
        )
    
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


@admin.register(CalibracaoTurbidez)
class CalibracaoTurbidezAdmin(OrdemServicoAutomaticaAdminMixin, admin.ModelAdmin):
    form = CalibracaoTurbidezAdminForm

    change_form_template = "admin/calibracao/calibracaoturbidez/change_form.html"

    list_display = (
        "numero_certificado",
        "instrumento",
        "cliente",
        "data_calibracao",
        "data_emissao",
        "pdf_certificado",
    )

    list_filter = ("data_calibracao", "data_emissao", "cliente")

    search_fields = (
        "numero_certificado",
        "instrumento__codigo",
        "instrumento__descricao",
        "cliente__razao_social",
        "ordem_servico",
    )

    autocomplete_fields = (
        "instrumento",
        "cliente",
        "procedimento_documento",
        "responsavel_tecnico_ref",
        "tecnico_executante_ref",
    )

    readonly_fields = (
        "numero_certificado",
        "procedimento_numero",
        "procedimento_revisao",
        "revisao_de",
    )

    fieldsets = (
        ("Planilha - Informações Gerais", {
            "fields": (
                "numero_certificado",
                "ordem_servico",
                "data_calibracao",
                "data_emissao",
                "revisao",
                "revisao_de",
                "motivo_revisao",
                "instrumento",
                "cliente",
                "contratante",
                "endereco_contratante",
                "endereco_cliente",
                "local_calibracao",
            )
        }),
        ("Planilha - Equipamento", {
            "fields": (
                "equipamento_calibrado",
                "numero_identificacao",
                "capacidade_total",
                "faixa_calibrada",
                "menor_resolucao",
                "unidade_leitura",
            )
        }),
        ("Planilha - Sonda Multiparâmetro", {
            "fields": (
                "sonda_multiparametro",
                "serie_sonda_optica_turbidez",
                "serie_cabo_multi",
                "id_sonda_multiparametro",
                "id_sonda_optica_turbidez",
                "id_cabo_multi",
            )
        }),
        ("Certificado - Procedimento e Ambiente", {
            "fields": (
                "procedimento_documento",
                "procedimento_numero",
                "procedimento_revisao",
                "temperatura_inicial",
                "temperatura_final",
                "umidade_inicial",
                "umidade_final",
                "ajuste_efetuado",
                "preparacao_padrao",
            )
        }),
        ("Certificado - Responsáveis e Observações", {
            "fields": (
                "responsavel_tecnico_ref",
                "tecnico_executante_ref",
                "funcao_signatario",
                "resultado_final",
                "observacoes_certificado",
            )
        }),
    )
    inlines = [
        TurbidezPadraoInline,
        TurbidezVerificacaoInline,
        TurbidezCalibracaoInline,
        TurbidezIncertezaInline,
    ]

    class Media:
        css = {"all": ("css/padrao_autofill.css",)}
        js = (
            "js/calibracao_turbidez.js",
            "js/calibracao_ordem_servico.js",
            "js/padrao_autofill.js",
        )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj=obj, change=change, **kwargs)
        instrumento_field = form.base_fields.get("instrumento")
        if instrumento_field:
            instrumento_url = reverse(
                "admin:calibracao_calibracaoturbidez_instrumento_dados",
                args=["00000000-0000-0000-0000-000000000000"],
            )
            instrumento_field.widget.attrs["data-instrumento-dados-url"] = instrumento_url.replace(
                "00000000-0000-0000-0000-000000000000",
                "__instrumento__",
            )
        return form

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        responsavel = ResponsavelCertificado.objects.filter(nome="Diego Henrique Alves Saldanha").first()
        if responsavel:
            initial.setdefault("responsavel_tecnico_ref", responsavel.pk)
            initial.setdefault("tecnico_executante_ref", responsavel.pk)
            initial.setdefault("funcao_signatario", responsavel.cargo)
        return initial

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "procedimento_documento":
            kwargs["queryset"] = Documento.objects.filter(
                tipo__in=("procedimento", "instrucao", "metodo"),
                status="vigente",
            ).order_by("codigo", "titulo")
        if db_field.name == "padrao_referencia":
            kwargs["queryset"] = Padrao.objects.order_by("codigo", "descricao")
        if db_field.name == "preparacao_padrao":
            from .dilution_models import PreparacaoPadrao

            kwargs["queryset"] = PreparacaoPadrao.objects.filter(
                aplicacao="turbidez",
            ).order_by("-data_preparacao", "-pk")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        calibracao = form.instance
        importados = calibracao.importar_padroes_da_preparacao()
        if importados:
            self.message_user(
                request,
                f"{importados} padrão(ões) importado(s) automaticamente da preparação.",
                messages.SUCCESS,
            )
        calibracao.sincronizar_pontos_incerteza()

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "instrumento/<uuid:instrumento_id>/dados/",
                self.admin_site.admin_view(self.instrumento_dados_view),
                name="calibracao_calibracaoturbidez_instrumento_dados",
            ),
            path(
                "<uuid:pk>/pdf/",
                self.admin_site.admin_view(self.pdf_view),
                name="calibracao_calibracaoturbidez_pdf",
            ),
        ]
        return custom_urls + urls

    def pdf_view(self, request, pk):
        from .views import pdf_calibracao_turbidez

        return pdf_calibracao_turbidez(request, pk)

    def instrumento_dados_view(self, request, instrumento_id):
        instrumento = get_object_or_404(Instrumento.objects.select_related("cliente"), pk=instrumento_id)
        cliente = instrumento.cliente

        try:
            tecnico = instrumento.tecnico
        except InstrumentoTecnico.DoesNotExist:
            tecnico = None

        endereco_partes = [
            getattr(cliente, "endereco", ""),
            getattr(cliente, "numero", ""),
            getattr(cliente, "bairro", ""),
            getattr(cliente, "cidade", ""),
            getattr(cliente, "uf", ""),
        ]
        endereco_cliente = ", ".join([parte for parte in endereco_partes if parte])
        local_calibracao = CalibracaoTurbidez._normalizar_local_calibracao(instrumento.local_instalacao)

        return JsonResponse({
            "cliente": {
                "id": str(cliente.pk),
                "text": str(cliente),
                "razao_social": cliente.razao_social,
            },
            "contratante": cliente.razao_social or "",
            "endereco_contratante": endereco_cliente,
            "endereco_cliente": endereco_cliente,
            "local_calibracao": local_calibracao,
            "equipamento_calibrado": instrumento.descricao or "",
            "numero_identificacao": instrumento.codigo or "",
            "capacidade_total": (tecnico.capacidade_total if tecnico and tecnico.capacidade_total else instrumento.modelo or ""),
            "faixa_calibrada": tecnico.faixa_medicao if tecnico else "",
            "menor_resolucao": str(tecnico.menor_resolucao) if tecnico and tecnico.menor_resolucao is not None else "",
            "unidade_leitura": tecnico.unidade if tecnico else "",
            "numero_serie": instrumento.numero_serie or "",
            "marca": instrumento.marca or "",
            "modelo": instrumento.modelo or "",
        })

    def pdf_certificado(self, obj):
        return format_html(
            "<a class='button' href='{}' target='_blank'>Gerar PDF</a>",
            reverse("admin:calibracao_calibracaoturbidez_pdf", args=[obj.pk]),
        )

    pdf_certificado.short_description = "Certificado"


@admin.register(CalibracaoColorimetro)
class CalibracaoColorimetroAdmin(OrdemServicoAutomaticaAdminMixin, admin.ModelAdmin):
    form = CalibracaoColorimetroAdminForm

    change_form_template = "admin/calibracao/calibracaocolorimetro/change_form.html"

    list_display = (
        "numero_certificado",
        "tipo_aplicacao",
        "instrumento",
        "cliente",
        "data_calibracao",
        "data_emissao",
        "pdf_certificado",
    )

    list_filter = ("tipo_aplicacao", "data_calibracao", "data_emissao", "cliente")

    search_fields = (
        "numero_certificado",
        "instrumento__codigo",
        "instrumento__descricao",
        "cliente__razao_social",
        "ordem_servico",
    )

    autocomplete_fields = (
        "instrumento",
        "cliente",
        "procedimento_documento",
        "responsavel_tecnico_ref",
        "tecnico_executante_ref",
    )

    readonly_fields = ("numero_certificado", "procedimento_numero", "procedimento_revisao")

    fieldsets = (
        ("Planilha - Informações Gerais", {
            "fields": (
                "numero_certificado",
                "ordem_servico",
                "data_calibracao",
                "data_emissao",
                "revisao",
                "instrumento",
                "cliente",
                "contratante",
                "endereco_contratante",
                "endereco_cliente",
                "local_calibracao",
            )
        }),
        ("Planilha - Aplicação", {
            "fields": (
                "tipo_aplicacao",
                "unidade_leitura",
            )
        }),
        ("Planilha - Equipamento", {
            "fields": (
                "equipamento_calibrado",
                "numero_identificacao",
                "capacidade_total",
                "faixa_calibrada",
                "menor_resolucao",
            )
        }),
        ("Certificado - Procedimento e Ambiente", {
            "fields": (
                "procedimento_documento",
                "procedimento_numero",
                "procedimento_revisao",
                "temperatura_inicial",
                "temperatura_final",
                "umidade_inicial",
                "umidade_final",
                "ajuste_efetuado",
            )
        }),
        ("Certificado - Responsáveis e Observações", {
            "fields": (
                "responsavel_tecnico_ref",
                "tecnico_executante_ref",
                "funcao_signatario",
                "resultado_final_status",
                "resultado_final",
                "observacoes_certificado",
            )
        }),
    )

    inlines = [
        ColorimetroPadraoInline,
        ColorimetroVerificacaoInline,
        ColorimetroCalibracaoInline,
    ]

    class Media:
        css = {"all": ("css/padrao_autofill.css",)}
        js = (
            "js/calibracao_colorimetro.js",
            "js/calibracao_ordem_servico.js",
            "js/padrao_autofill.js",
        )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj=obj, change=change, **kwargs)
        instrumento_field = form.base_fields.get("instrumento")
        tipo_field = form.base_fields.get("tipo_aplicacao")
        if instrumento_field:
            instrumento_url = reverse(
                "admin:calibracao_calibracaocolorimetro_instrumento_dados",
                args=["00000000-0000-0000-0000-000000000000"],
            )
            instrumento_field.widget.attrs["data-instrumento-dados-url"] = instrumento_url.replace(
                "00000000-0000-0000-0000-000000000000",
                "__instrumento__",
            )
        if tipo_field:
            metodo_url = reverse(
                "admin:calibracao_calibracaocolorimetro_metodo_dados",
                args=["__tipo__"],
            )
            tipo_field.widget.attrs["data-metodo-dados-url"] = metodo_url
        return form

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        responsavel = ResponsavelCertificado.objects.filter(nome="Diego Henrique Alves Saldanha").first()
        if responsavel:
            initial.setdefault("responsavel_tecnico_ref", responsavel.pk)
            initial.setdefault("tecnico_executante_ref", responsavel.pk)
            initial.setdefault("funcao_signatario", responsavel.cargo)
        return initial

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "procedimento_documento":
            kwargs["queryset"] = Documento.objects.filter(
                tipo__in=("procedimento", "instrucao", "metodo"),
                status="vigente",
            ).order_by("codigo", "titulo")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        calibracao = form.instance
        calibracao.sincronizar_pontos_incerteza()

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "instrumento/<uuid:instrumento_id>/dados/",
                self.admin_site.admin_view(self.instrumento_dados_view),
                name="calibracao_calibracaocolorimetro_instrumento_dados",
            ),
            path(
                "metodo/<str:tipo_aplicacao>/dados/",
                self.admin_site.admin_view(self.metodo_dados_view),
                name="calibracao_calibracaocolorimetro_metodo_dados",
            ),
            path(
                "<uuid:pk>/pdf/",
                self.admin_site.admin_view(self.pdf_view),
                name="calibracao_calibracaocolorimetro_pdf",
            ),
        ]
        return custom_urls + urls

    def instrumento_dados_view(self, request, instrumento_id):
        instrumento = get_object_or_404(Instrumento.objects.select_related("cliente"), pk=instrumento_id)
        cliente = instrumento.cliente
        try:
            tecnico = instrumento.tecnico
        except InstrumentoTecnico.DoesNotExist:
            tecnico = None

        endereco_partes = [
            getattr(cliente, "endereco", ""),
            getattr(cliente, "numero", ""),
            getattr(cliente, "bairro", ""),
            getattr(cliente, "cidade", ""),
            getattr(cliente, "uf", ""),
        ]
        endereco_cliente = ", ".join([parte for parte in endereco_partes if parte])
        local_calibracao = CalibracaoColorimetro._normalizar_local_calibracao(instrumento.local_instalacao)

        return JsonResponse({
            "cliente": {
                "id": str(cliente.pk),
                "text": str(cliente),
                "razao_social": cliente.razao_social,
            },
            "contratante": cliente.razao_social or "",
            "endereco_contratante": endereco_cliente,
            "endereco_cliente": endereco_cliente,
            "local_calibracao": local_calibracao,
            "equipamento_calibrado": instrumento.descricao or "Colorímetro",
            "numero_identificacao": instrumento.codigo or "",
            "capacidade_total": (tecnico.capacidade_total if tecnico and tecnico.capacidade_total else instrumento.modelo or ""),
            "faixa_calibrada": tecnico.faixa_medicao if tecnico else "",
            "menor_resolucao": str(tecnico.menor_resolucao) if tecnico and tecnico.menor_resolucao is not None else "",
            "unidade_leitura": tecnico.unidade if tecnico else "",
            "numero_serie": instrumento.numero_serie or "",
            "marca": instrumento.marca or "",
            "modelo": instrumento.modelo or "",
        })

    def pdf_view(self, request, pk):
        from .views import pdf_calibracao_colorimetro
        return pdf_calibracao_colorimetro(request, pk)

    def metodo_dados_view(self, request, tipo_aplicacao):
        calibracao_dummy = CalibracaoColorimetro(tipo_aplicacao=tipo_aplicacao)
        documento = calibracao_dummy._obter_documento_metodo_padrao()
        if not documento:
            return JsonResponse({})
        return JsonResponse({
            "documento": {
                "id": str(documento.pk),
                "text": str(documento),
            },
            "codigo": documento.codigo or "",
            "revisao": documento.revisao or "",
            "arquivo_url": documento.arquivo.url if documento.arquivo else "",
        })

    def pdf_certificado(self, obj):
        return format_html(
            "<a class='button' href='{}' target='_blank'>Gerar PDF</a>",
            reverse("admin:calibracao_calibracaocolorimetro_pdf", args=[obj.pk]),
        )

    pdf_certificado.short_description = "Certificado"

    def arquivo_metodo_pdf(self, obj):
        documento = getattr(obj, "procedimento_documento", None)
        if documento and documento.arquivo:
            return format_html("<a href='{}' target='_blank'>Abrir PDF do método</a>", documento.arquivo.url)
        return "—"

    arquivo_metodo_pdf.short_description = "PDF do método"

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
        "conta_receber_gerada",
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
        "numero_automatico",
        "data_abertura",
        "conta_receber_gerada",
        "ver_anexo",
    )

    fieldsets = (
        ("Dados da Ordem de Serviço", {
            "fields": (
                "numero_automatico",
                "proposta",
                "cliente",
                "status",
                "data_abertura",
                "data_conclusao",
                "conta_receber_gerada",
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

    @admin.display(description="Número")
    def numero_automatico(self, obj):
        if obj and obj.numero:
            return obj.numero
        ano = timezone.localdate().year % 100
        return (
            "Gerado automaticamente ao salvar. A sequência é contínua e "
            f"somente o ano final é atualizado (ex.: 0001/{ano:02d})."
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

    @admin.display(description="Conta a receber")
    def conta_receber_gerada(self, obj):
        if not obj or not obj.pk:
            return "Gerada conforme o faturamento da proposta após concluir a OS."
        try:
            conta = obj.conta_receber
        except ObjectDoesNotExist:
            return "—"
        return format_html(
            "<a href='{}'>R$ {}</a>",
            reverse("admin:financeiro_contareceber_change", args=[conta.pk]),
            conta.valor,
        )


# =========================
# PADRÃO
# =========================

@admin.register(Padrao)
class PadraoAdmin(admin.ModelAdmin):

    readonly_fields = ("codigo",)

    list_display = (
        "codigo",
        "descricao_objetiva",
        "numero_certificado",
        "data_calibracao",
        "vencimento",
        "situacao_operacional",
        "ver_certificado",
    )

    search_fields = (
        "codigo",
        "descricao",
        "numero_certificado",
        "laboratorio_emitente",
    )

    list_filter = (
        "status",
        "vencimento",
        "laboratorio_emitente",
    )

    ordering = ("codigo",)
    list_per_page = 50

    fieldsets = (
        ("Identificação", {
            "fields": (
                "codigo",
                "descricao",
                "status",
                "vencimento",
                "certificado",
            )
        }),
        ("Dados metrológicos", {
            "fields": (
                "numero_certificado",
                "laboratorio_emitente",
                "data_calibracao",
                "valor_nominal",
                "resolucao",
                "incerteza",
                "fator_k",
                "graus_liberdade",
                "unidade",
            )
        }),
    )

    def get_queryset(self, request):
        """Mantém resultados de diluição fora do cadastro geral de padrões."""
        return self.model.para_monitoramento(super().get_queryset(request))

    def get_urls(self):
        return [
            path(
                "<uuid:object_id>/dados/",
                self.admin_site.admin_view(self.dados_metrologicos_view),
                name="calibracao_padrao_dados_metrologicos",
            ),
        ] + super().get_urls()

    def dados_metrologicos_view(self, request, object_id):
        if not self.has_view_permission(request):
            raise PermissionDenied
        padrao = get_object_or_404(Padrao, pk=object_id)
        return JsonResponse(
            {
                "id": str(padrao.pk),
                "codigo": padrao.codigo,
                "descricao": padrao.descricao,
                "numero_certificado": padrao.numero_certificado,
                "laboratorio_emitente": padrao.laboratorio_emitente,
                "data_calibracao": padrao.data_calibracao.isoformat() if padrao.data_calibracao else "",
                "validade": padrao.vencimento.isoformat(),
                "resolucao": str(padrao.resolucao) if padrao.resolucao is not None else "",
                "incerteza": str(padrao.incerteza) if padrao.incerteza is not None else "",
                "fator_k": str(padrao.fator_k) if padrao.fator_k is not None else "",
                "graus_liberdade": str(padrao.graus_liberdade) if padrao.graus_liberdade is not None else "",
                "unidade": padrao.unidade,
                "valor_nominal": str(padrao.valor_nominal) if padrao.valor_nominal is not None else "",
                "status": padrao.status,
                "certificado_url": padrao.certificado.url if padrao.certificado else "",
            }
        )

    def ver_certificado(self, obj):
        if obj.certificado:
            return format_html(
                "<a href='{}' target='_blank'>Abrir PDF</a>",
                obj.certificado.url
            )
        return "—"

    ver_certificado.short_description = "PDF"

    @admin.display(description="Padrão", ordering="descricao")
    def descricao_objetiva(self, obj):
        descricao = obj.descricao or "—"
        resumo = descricao if len(descricao) <= 70 else f"{descricao[:67]}..."
        return format_html('<span title="{}">{}</span>', descricao, resumo)

    @admin.display(description="Situação", ordering="vencimento")
    def situacao_operacional(self, obj):
        if obj.status == "suspenso":
            rotulo, classe = "Suspenso", "is-suspended"
        elif obj.status == "vencido" or obj.vencimento < date.today():
            rotulo, classe = "Vencido", "is-expired"
        else:
            rotulo, classe = "Válido", "is-valid"
        return format_html(
            '<span class="metrology-status {}">{}</span>',
            classe,
            rotulo,
        )


@admin.register(CalibracaoPressao)
class CalibracaoPressaoAdmin(OrdemServicoAutomaticaAdminMixin, admin.ModelAdmin):
    form = CalibracaoPressaoAdminForm
    change_form_template = "admin/calibracao/calibracaopressao/change_form.html"

    list_display = (
        "numero_certificado",
        "tipo_instrumento",
        "instrumento",
        "cliente",
        "data_calibracao",
        "data_emissao",
        "pdf_certificado",
    )
    list_filter = ("tipo_instrumento", "tipo_indicacao", "data_calibracao", "data_emissao", "cliente")
    search_fields = (
        "numero_certificado",
        "instrumento__codigo",
        "instrumento__descricao",
        "cliente__razao_social",
        "ordem_servico",
    )
    autocomplete_fields = (
        "instrumento",
        "cliente",
        "procedimento_documento",
        "responsavel_tecnico_ref",
        "tecnico_executante_ref",
    )
    readonly_fields = ("numero_certificado", "procedimento_numero", "procedimento_revisao", "valor_por_divisao")
    fieldsets = (
        ("Planilha - InformaÃ§Ãµes Gerais", {
            "fields": (
                "numero_certificado",
                "ordem_servico",
                "data_calibracao",
                "data_emissao",
                "revisao",
                "instrumento",
                "cliente",
                "contratante",
                "endereco_contratante",
                "endereco_cliente",
                "local_calibracao",
            )
        }),
        ("Planilha - Equipamento", {
            "fields": (
                "tipo_instrumento",
                "tipo_indicacao",
                "referencia_calculo",
                "equipamento_calibrado",
                "numero_identificacao",
                "marca",
                "modelo",
                "numero_serie",
                "faixa_indicacao",
                "faixa_calibrada",
                "capacidade_total",
                "menor_resolucao",
                "classe_declarada",
                "unidade_indicacao",
                "unidade_padrao",
                "divisao_escala",
                "valor_por_divisao",
            )
        }),
        ("Certificado - MÃ©todo e Ambiente", {
            "fields": (
                "procedimento_documento",
                "procedimento_numero",
                "procedimento_revisao",
                "temperatura_inicial",
                "temperatura_final",
                "umidade_inicial",
                "umidade_final",
                "ajuste_efetuado",
            )
        }),
        ("Certificado - ResponsÃ¡veis e ObservaÃ§Ãµes", {
            "fields": (
                "responsavel_tecnico_ref",
                "tecnico_executante_ref",
                "funcao_signatario",
                "resultado_final_status",
                "resultado_final",
                "observacoes_certificado",
            )
        }),
    )
    inlines = [PressaoPadraoInline, PressaoCalibracaoInline, PressaoIncertezaInline]

    class Media:
        css = {"all": ("css/padrao_autofill.css",)}
        js = (
            "js/calibracao_pressao.js",
            "js/calibracao_ordem_servico.js",
            "js/padrao_autofill.js",
        )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj=obj, change=change, **kwargs)
        instrumento_field = form.base_fields.get("instrumento")
        if instrumento_field:
            instrumento_url = reverse(
                "admin:calibracao_calibracaopressao_instrumento_dados",
                args=["00000000-0000-0000-0000-000000000000"],
            )
            instrumento_field.widget.attrs["data-instrumento-dados-url"] = instrumento_url.replace(
                "00000000-0000-0000-0000-000000000000",
                "__instrumento__",
            )
        return form

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        responsavel = ResponsavelCertificado.objects.filter(nome="Diego Henrique Alves Saldanha").first()
        if responsavel:
            initial.setdefault("responsavel_tecnico_ref", responsavel.pk)
            initial.setdefault("tecnico_executante_ref", responsavel.pk)
            initial.setdefault("funcao_signatario", responsavel.cargo)
        return initial

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "procedimento_documento":
            kwargs["queryset"] = Documento.objects.filter(
                tipo__in=("procedimento", "instrucao", "metodo"),
                status="vigente",
            ).order_by("codigo", "titulo")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "instrumento/<uuid:instrumento_id>/dados/",
                self.admin_site.admin_view(self.instrumento_dados_view),
                name="calibracao_calibracaopressao_instrumento_dados",
            ),
            path(
                "<uuid:pk>/pdf/",
                self.admin_site.admin_view(self.pdf_view),
                name="calibracao_calibracaopressao_pdf",
            ),
        ]
        return custom_urls + urls

    def instrumento_dados_view(self, request, instrumento_id):
        instrumento = get_object_or_404(Instrumento.objects.select_related("cliente"), pk=instrumento_id)
        cliente = instrumento.cliente
        try:
            tecnico = instrumento.tecnico
        except InstrumentoTecnico.DoesNotExist:
            tecnico = None

        endereco_partes = [
            getattr(cliente, "endereco", ""),
            getattr(cliente, "numero", ""),
            getattr(cliente, "bairro", ""),
            getattr(cliente, "cidade", ""),
            getattr(cliente, "uf", ""),
        ]
        endereco_cliente = ", ".join([parte for parte in endereco_partes if parte])
        local_calibracao = CalibracaoPressao._normalizar_local_calibracao(instrumento.local_instalacao)

        return JsonResponse({
            "cliente": {
                "id": str(cliente.pk),
                "text": str(cliente),
                "razao_social": cliente.razao_social,
            },
            "contratante": cliente.razao_social or "",
            "endereco_contratante": endereco_cliente,
            "endereco_cliente": endereco_cliente,
            "local_calibracao": local_calibracao,
            "equipamento_calibrado": instrumento.descricao or "Instrumento de PressÃ£o",
            "numero_identificacao": instrumento.codigo or "",
            "capacidade_total": (tecnico.capacidade_total if tecnico and tecnico.capacidade_total else instrumento.modelo or ""),
            "faixa_calibrada": tecnico.faixa_medicao if tecnico else "",
            "faixa_indicacao": tecnico.faixa_medicao if tecnico else "",
            "menor_resolucao": str(tecnico.menor_resolucao) if tecnico and tecnico.menor_resolucao is not None else "",
            "unidade_leitura": tecnico.unidade if tecnico else "",
            "unidade_indicacao": tecnico.unidade if tecnico else "",
            "numero_serie": instrumento.numero_serie or "",
            "marca": instrumento.marca or "",
            "modelo": instrumento.modelo or "",
            "classe_declarada": tecnico.classe if tecnico else "",
        })

    def pdf_view(self, request, pk):
        from .views import pdf_calibracao_pressao
        return pdf_calibracao_pressao(request, pk)

    def pdf_certificado(self, obj):
        return format_html(
            "<a class='button' href='{}' target='_blank'>Gerar PDF</a>",
            reverse("admin:calibracao_calibracaopressao_pdf", args=[obj.pk]),
        )

    pdf_certificado.short_description = "Certificado"


class PHPadraoInline(admin.TabularInline):
    model = CalibracaoPHPadraoUtilizado
    form = PHPadraoAdminForm
    extra = 1
    autocomplete_fields = ("padrao",)
    fields = (
        "tipo",
        "ordem",
        "padrao",
        "codigo",
        "descricao",
        "numero_certificado",
        "laboratorio_emitente",
        "data_calibracao",
        "validade",
        "resolucao",
        "incerteza",
        "fator_k",
        "graus_liberdade",
        "unidade",
        "valor_nominal",
    )
    verbose_name = "Padrao"
    verbose_name_plural = "Padroes"


class PHCalibracaoEletricaInline(admin.TabularInline):
    model = CalibracaoPHPonto
    form = PHPontoAdminForm
    extra = 3
    fields = (
        "ordem",
        "tipo",
        "valor_padrao_mv",
        "leitura_1",
        "leitura_2",
        "leitura_3",
        "media",
        "desvio_padrao",
        "erro",
        "ema",
        "criterio",
        "resultado",
    )
    readonly_fields = ("media", "desvio_padrao", "erro", "ema")
    verbose_name = "Ponto de calibracao eletrica"
    verbose_name_plural = "Calibracao eletrica"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(tipo__in=("eletrica_mv", "eletrica_ph"))


class PHCalibracaoMRCInline(admin.TabularInline):
    model = CalibracaoPHPonto
    form = PHPontoAdminForm
    extra = 5
    fields = (
        "ordem",
        "tipo",
        "valor_padrao_ph",
        "leitura_1",
        "leitura_2",
        "leitura_3",
        "media",
        "desvio_padrao",
        "erro",
        "ema",
        "criterio",
        "resultado",
    )
    readonly_fields = ("media", "desvio_padrao", "erro", "ema")
    verbose_name = "Ponto de calibracao da parte quimica"
    verbose_name_plural = "Calibracao com parte quimica"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(
            tipo__in=(
                "quimica_acida",
                "quimica_neutra",
                "quimica_basica",
                "verificacao_acida",
                "verificacao_basica",
                "mrc_acida",
                "mrc_neutra",
                "mrc_basica",
                "mrc_verificacao_acida",
                "mrc_verificacao_basica",
            )
        )


class PHIncertezaInline(admin.TabularInline):
    model = CalibracaoPHIncertezaPonto
    form = PHIncertezaAdminForm
    extra = 1
    fields = (
        "ordem",
        "repetibilidade",
        "resolucao_instrumento",
        "resolucao_padrao",
        "incerteza_padrao",
        "incerteza_curva",
        "incerteza_temperatura",
        "incerteza_constante_faraday",
        "incerteza_constante_gas",
        "incerteza_phx",
        "fator_k",
        "graus_liberdade",
        "incerteza_padrao_combinada",
        "incerteza_expandida",
    )
    readonly_fields = ("incerteza_padrao_combinada", "incerteza_expandida")
    verbose_name = "Ponto de incerteza"
    verbose_name_plural = "Incerteza"


@admin.register(CalibracaoPH)
class CalibracaoPHAdmin(OrdemServicoAutomaticaAdminMixin, admin.ModelAdmin):
    form = CalibracaoPHAdminForm

    change_form_template = "admin/calibracao/calibracaoph/change_form.html"

    list_display = (
        "numero_certificado",
        "tipo_calibracao",
        "instrumento",
        "cliente",
        "data_calibracao",
        "data_emissao",
        "pdf_certificado",
    )

    list_filter = ("tipo_calibracao", "local_calibracao", "data_calibracao", "cliente", OrdemServicoNumeroFilter)

    search_fields = (
        "numero_certificado",
        "instrumento__codigo",
        "instrumento__descricao",
        "cliente__razao_social",
        "ordem_servico",
    )

    autocomplete_fields = (
        "instrumento",
        "cliente",
        "procedimento_documento",
        "responsavel_tecnico_ref",
        "tecnico_executante_ref",
    )

    readonly_fields = ("numero_certificado", "procedimento_numero", "procedimento_revisao", "resultado_final_status", "resultado_final")

    fieldsets = (
        ("Planilha - Informacoes Gerais", {
            "fields": (
                "numero_certificado",
                "ordem_servico",
                "data_calibracao",
                "data_emissao",
                "revisao",
                "instrumento",
                "cliente",
                "contratante",
                "endereco_contratante",
                "endereco_cliente",
                "local_calibracao",
                "tipo_calibracao",
                "tipo_indicacao",
            )
        }),
        ("Planilha - Equipamento", {
            "fields": (
                "equipamento_calibrado",
                "numero_identificacao",
                "marca",
                "modelo",
                "numero_serie",
                "capacidade_total",
                "faixa_calibrada",
                "menor_resolucao",
                "resolucao_mv",
                "resolucao_ph",
                "identificacao_eletrodo",
                "resolucao_termometro",
                "temperatura_referencia",
                "id_sensor_temperatura",
                "unidade_leitura",
                "tipo_sensor_temperatura",
            )
        }),
        ("Calibracao - Parte quimica", {
            "fields": (
                "slope_indicado",
            )
        }),
        ("Certificado - Procedimento e Ambiente", {
            "fields": (
                "procedimento_documento",
                "procedimento_numero",
                "procedimento_revisao",
                "temperatura_inicial",
                "temperatura_final",
                "umidade_inicial",
                "umidade_final",
                "ajuste_efetuado",
            )
        }),
        ("Certificado - Responsaveis e Observacoes", {
            "fields": (
                "responsavel_tecnico_ref",
                "tecnico_executante_ref",
                "funcao_signatario",
                "signatario_autorizado",
                "resultado_final_status",
                "resultado_final",
                "observacoes_certificado",
            )
        }),
    )

    inlines = [
        PHPadraoInline,
        PHCalibracaoEletricaInline,
        PHCalibracaoMRCInline,
        PHIncertezaInline,
    ]

    class Media:
        css = {"all": ("css/padrao_autofill.css",)}
        js = (
            "js/calibracao_ph.js",
            "js/calibracao_ordem_servico.js",
            "js/padrao_autofill.js",
        )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj=obj, change=change, **kwargs)
        instrumento_field = form.base_fields.get("instrumento")
        if instrumento_field:
            instrumento_url = reverse(
                "admin:calibracao_calibracaoph_instrumento_dados",
                args=["00000000-0000-0000-0000-000000000000"],
            )
            instrumento_field.widget.attrs["data-instrumento-dados-url"] = instrumento_url.replace(
                "00000000-0000-0000-0000-000000000000",
                "__instrumento__",
            )
        return form

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        responsavel = ResponsavelCertificado.objects.filter(nome="Diego Henrique Alves Saldanha").first()
        if responsavel:
            initial.setdefault("responsavel_tecnico_ref", responsavel.pk)
            initial.setdefault("tecnico_executante_ref", responsavel.pk)
            initial.setdefault("funcao_signatario", responsavel.cargo)
        return initial

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "procedimento_documento":
            kwargs["queryset"] = Documento.objects.filter(
                tipo__in=("procedimento", "instrucao", "metodo"),
                status="vigente",
            ).order_by("codigo", "titulo")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "instrumento/<uuid:instrumento_id>/dados/",
                self.admin_site.admin_view(self.instrumento_dados_view),
                name="calibracao_calibracaoph_instrumento_dados",
            ),
            path(
                "<int:pk>/pdf/",
                self.admin_site.admin_view(self.pdf_view),
                name="calibracao_calibracaoph_pdf",
            ),
        ]
        return custom_urls + urls

    def instrumento_dados_view(self, request, instrumento_id):
        instrumento = get_object_or_404(Instrumento.objects.select_related("cliente"), pk=instrumento_id)
        cliente = instrumento.cliente
        try:
            tecnico = instrumento.tecnico
        except InstrumentoTecnico.DoesNotExist:
            tecnico = None

        return JsonResponse({
            "cliente": {
                "id": str(cliente.pk),
                "text": str(cliente),
                "razao_social": cliente.razao_social,
            },
            "contratante": cliente.razao_social or "",
            "endereco_contratante": _join_address(cliente),
            "endereco_cliente": _join_address(cliente),
            "local_calibracao": CalibracaoPH._normalizar_local_calibracao(instrumento.local_instalacao),
            "equipamento_calibrado": instrumento.descricao or "Medidor de pH",
            "numero_identificacao": instrumento.codigo or "",
            "marca": instrumento.marca or "",
            "modelo": instrumento.modelo or "",
            "numero_serie": instrumento.numero_serie or "",
            "capacidade_total": (tecnico.capacidade_total if tecnico and tecnico.capacidade_total else instrumento.modelo or ""),
            "faixa_calibrada": tecnico.faixa_medicao if tecnico else "",
            "menor_resolucao": str(tecnico.menor_resolucao) if tecnico and tecnico.menor_resolucao is not None else "",
            "unidade_leitura": tecnico.unidade if tecnico else "",
            "tipo_indicacao": "digital" if tecnico and tecnico.classe else "",
            "resolucao_mv": str(tecnico.menor_resolucao) if tecnico and tecnico.menor_resolucao is not None else "",
            "resolucao_ph": str(tecnico.menor_resolucao) if tecnico and tecnico.menor_resolucao is not None else "",
            "identificacao_eletrodo": instrumento.codigo or "",
            "id_sensor_temperatura": "",
        })

    def pdf_view(self, request, pk):
        from .views import pdf_calibracao_ph

        return pdf_calibracao_ph(request, pk)

    def pdf_certificado(self, obj):
        return format_html(
            "<a class='button' href='{}' target='_blank'>Gerar PDF</a>",
            reverse("admin:calibracao_calibracaoph_pdf", args=[obj.pk]),
        )

    pdf_certificado.short_description = "Certificado"


@admin.register(CalibracaoCondutividade)
class CalibracaoCondutividadeAdmin(OrdemServicoAutomaticaAdminMixin, admin.ModelAdmin):
    form = CalibracaoCondutividadeAdminForm
    list_display = (
        "numero_certificado",
        "cliente",
        "instrumento",
        "data_calibracao",
        "resultado_final",
        "status",
    )


# Registros especializados da calibração de balanças.
    list_filter = ("status", "resultado_final", "local_calibracao")
    search_fields = (
        "numero_certificado",
        "cliente__razao_social",
        "instrumento__codigo",
        "instrumento__descricao",
    )
    autocomplete_fields = ("cliente", "instrumento")
    fieldsets = (
        ("Identificação", {
            "fields": (
                "cliente",
                "instrumento",
                "ordem_servico",
                "numero_certificado",
                "revisao",
            )
        }),
        ("Datas e status", {
            "fields": (
                "data_calibracao",
                "data_emissao",
                "local_calibracao",
                "status",
                "resultado_final",
            )
        }),
        ("Dados do equipamento", {
            "fields": (
                "contratante",
                "endereco_contratante",
                "endereco_cliente",
                "equipamento_calibrado",
                "numero_identificacao",
                "marca",
                "modelo",
                "numero_serie",
                "faixa_capacidade",
                "resolucao",
                "unidade_indicacao",
                "unidade_padrao",
                "unidade_leitura",
                "temperatura_referencia",
                "identificacao_celula",
                "constante_celula",
                "compensacao_temperatura",
            )
        }),
        ("Responsáveis", {
            "fields": (
                "tecnico_responsavel",
                "responsavel_conferencia",
                "signatario_autorizado",
                "funcao_signatario",
            )
        }),
        ("Ambiente e controle", {
            "fields": (
                "temperatura_ambiente",
                "umidade_ambiente",
                "observacoes",
                "snapshot_json",
                "pdf_arquivo",
            )
        }),
    )
