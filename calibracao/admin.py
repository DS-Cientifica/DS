from django import forms
from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.urls import path, reverse

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
    fields = (
        "faixa_medicao",
        "capacidade_total",
        "menor_resolucao",
        "unidade",
        "classe",
        "observacoes",
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


class TurbidezVerificacaoInline(admin.TabularInline):
    model = TurbidezVerificacaoPonto
    extra = 5
    fields = ("ordem", "valor_padrao", "leitura", "erro", "criterio", "resultado")
    readonly_fields = ("erro",)
    verbose_name = "Ponto de verificação"
    verbose_name_plural = "Verificação"


class TurbidezCalibracaoInline(admin.TabularInline):
    model = TurbidezCalibracaoPonto
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
    extra = 5
    fields = ("ordem", "valor_padrao", "leitura", "erro", "criterio", "criterio_origem", "resultado")
    readonly_fields = ("erro",)
    verbose_name = "Ponto de verificação"
    verbose_name_plural = "Verificação"


class ColorimetroCalibracaoInline(admin.TabularInline):
    model = ColorimetroCalibracaoPonto
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
        "criterio_origem",
    )
    readonly_fields = ("media", "erro", "ema")
    verbose_name = "Ponto de calibração"
    verbose_name_plural = "Calibração"


class ColorimetroIncertezaInline(admin.TabularInline):
    model = ColorimetroIncertezaPonto
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


class PressaoPadraoInlineForm(forms.ModelForm):
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


class PressaoCalibracaoInlineForm(forms.ModelForm):
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


class CalibracaoPressaoAdminForm(forms.ModelForm):
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
class CalibracaoTurbidezAdmin(admin.ModelAdmin):

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
        js = ("js/calibracao_turbidez.js",)

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
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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
class CalibracaoColorimetroAdmin(admin.ModelAdmin):

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
        ColorimetroIncertezaInline,
    ]

    class Media:
        js = ("js/calibracao_turbidez.js",)

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
        "numero_certificado",
        "laboratorio_emitente",
        "data_calibracao",
        "status",
        "vencimento",
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
    )

    ordering = ("codigo",)

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

    def ver_certificado(self, obj):
        if obj.certificado:
            return format_html(
                "<a href='{}' target='_blank'>Abrir</a>",
                obj.certificado.url
            )
        return "—"

    ver_certificado.short_description = "Certificado"


@admin.register(CalibracaoPressao)
class CalibracaoPressaoAdmin(admin.ModelAdmin):
    change_form_template = "admin/calibracao/calibracaopressao/change_form.html"
    form = CalibracaoPressaoAdminForm

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
        js = ("js/calibracao_pressao.js",)

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
