import calendar
from datetime import date, timedelta
from io import BytesIO
import re
import uuid

from django import forms
from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.validators import URLValidator, validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from django.urls import path
from django.db.models import OuterRef, Q, Subquery, Sum
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from clientes.models import Cliente, ContatoCliente

from .models import (
    Proposta,
    ItemProposta,
    ProdutoServico,
    ProdutoAnexo,
    PropostaAnexo,
    PropostaMovimentacao,
    ComposicaoPreco,
    DadosTecnicos,
    ProspeccaoComercial,
    ProspeccaoInteracao,
    Prospecto,
    CRMRegistro,
    CRMInteracao,
    CRMTicket,
)


# =========================
# ANEXOS PRODUTO
# =========================

class ProdutoAnexoInline(admin.TabularInline):
    model = ProdutoAnexo
    extra = 1


# =========================
# ANEXOS PROPOSTA
# =========================

class PropostaAnexoInline(admin.TabularInline):
    model = PropostaAnexo
    extra = 1
    fields = ("nome", "tipo", "arquivo", "legenda", "ordem", "exibir_no_pdf")


class PropostaMovimentacaoInline(admin.TabularInline):
    model = PropostaMovimentacao
    extra = 0
    can_delete = False
    fields = ("data", "usuario", "tipo", "revisao", "descricao")
    readonly_fields = ("data", "usuario", "tipo", "revisao", "descricao")

    def has_add_permission(self, request, obj=None):
        return False


# =========================
# ITENS PROPOSTA
# =========================

class ItemPropostaInline(admin.TabularInline):
    model = ItemProposta
    extra = 1
    autocomplete_fields = ("produto",)


# =========================
# PROPOSTA
# =========================


class PropostaAdminForm(forms.ModelForm):
    class Meta:
        model = Proposta
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cliente_id = self.data.get("cliente") if self.is_bound else None
        if not cliente_id and self.instance and self.instance.cliente_id:
            cliente_id = self.instance.cliente_id

        queryset = ContatoCliente.objects.none()
        if cliente_id:
            try:
                queryset = ContatoCliente.objects.filter(cliente_id=cliente_id).order_by(
                    "-principal",
                    "nome",
                )
            except (TypeError, ValueError, DjangoValidationError):
                queryset = ContatoCliente.objects.none()
        self.fields["responsavel"].queryset = queryset


@admin.register(Proposta)
class PropostaAdmin(admin.ModelAdmin):
    form = PropostaAdminForm
    change_form_template = "admin/comercial/proposta/change_form.html"
    change_list_template = "admin/comercial/proposta/change_list.html"

    list_display = (
        "codigo",
        "data_emissao",
        "revisao",
        "cliente",
        "responsavel",
        "status",
        "resultado_fechamento",
        "ordem_servico_gerada",
        "motivo_perda",
        "total",
        "gerar_pdf",
    )

    search_fields = (
        "codigo",
        "cliente__razao_social",
    )

    list_filter = (
        ("data_emissao", admin.DateFieldListFilter),
        "status",
        "resultado_fechamento",
        "motivo_perda",
        "local_execucao",
        "frete",
    )
    date_hierarchy = "data_emissao"
    ordering = ("-data_emissao", "-codigo")

    readonly_fields = (
        "codigo",
        "crm_registro",
        "total",
        "margem_calculada",
        "metodo",
        "padroes_utilizados",
        "data_emissao",
        "ordem_servico_gerada",
    )

    class Media:
        js = (
            "js/proposta_margem.js",
            "js/proposta_contatos_cliente.js",
        )

    autocomplete_fields = ("cliente",)

    inlines = [
        ItemPropostaInline,
        PropostaAnexoInline,
        PropostaMovimentacaoInline,
    ]

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            "filtro_status_atual": request.GET.get("status__exact", ""),
            "filtro_resultado_atual": request.GET.get("resultado_fechamento__exact", ""),
            "filtro_motivo_atual": request.GET.get("motivo_perda__exact", ""),
            "status_choices_rapido": self.model.STATUS_CHOICES,
            "resultado_choices_rapido": self.model.RESULTADO_CHOICES,
            "motivo_choices_rapido": self.model.MOTIVO_PERDA_CHOICES,
        })
        response = super().changelist_view(request, extra_context=extra_context)
        if hasattr(response, "context_data") and response.context_data and "cl" in response.context_data:
            changelist = response.context_data["cl"]
            total_filtrado = changelist.queryset.aggregate(total=Sum("total"))["total"] or 0
            response.context_data["total_filtrado_propostas"] = total_filtrado
            response.context_data["quantidade_filtrada_propostas"] = changelist.result_count
        return response

    fieldsets = (
        ("Dados Gerais", {
            "fields": (
                "codigo",
                "crm_registro",
                "cliente",
                "responsavel",
                "status",
                "resultado_fechamento",
                "ordem_servico_gerada",
                "motivo_perda",
                "data_emissao",
                "revisao",
                "validade",
            )
        }),

        ("Execução do Serviço", {
            "fields": (
                "local_execucao",
                "prazo_execucao",
                "frete",
            )
        }),

        ("Financeiro", {
            "fields": (
                "prazo_pagamento",
                "gera_conta_receber_automaticamente",
                "tipo_faturamento",
                ("desconto_geral", "frete_valor"),
                ("outras_despesas", "seguro_valor"),
                ("margem_percentual", "margem_calculada"),
                "total",
            )
        }),

        ("Metodologia (Automática)", {
            "description": "Preenchido automaticamente com base nos itens",
            "fields": (
                "metodo",
                "padroes_utilizados",
            )
        }),

        ("Observações", {
            "fields": (
                "observacoes",
            )
        }),
    )

    def margem_calculada(self, obj):
        return obj.resumo_financeiro()["margem_valor"]

    margem_calculada.short_description = "Margem calculada"

    @admin.display(description="Ordem de serviço")
    def ordem_servico_gerada(self, obj):
        if not obj or not obj.pk:
            return "Gerada automaticamente após a aprovação positiva."
        ordem = obj.ordens_servico.first()
        if not ordem:
            return "—"
        return format_html(
            "<a href='{}'>{}</a>",
            reverse("admin:calibracao_ordemservico_change", args=[ordem.pk]),
            f"OS {ordem.numero}",
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.atualizar_total()

    def save_formset(self, request, form, formset, change):
        movimentacoes = self._movimentacoes_itens_proposta(formset)
        super().save_formset(request, form, formset, change)
        obj = form.instance
        if not obj.pk:
            return
        for descricao in movimentacoes:
            PropostaMovimentacao.registrar(
                proposta=obj,
                usuario=request.user,
                tipo="alteracao",
                descricao=descricao,
            )

    def _movimentacoes_itens_proposta(self, formset):
        if formset.model is not ItemProposta:
            return []

        movimentacoes = []
        for form in formset.forms:
            if not getattr(form, "cleaned_data", None):
                continue

            if form.cleaned_data.get("DELETE"):
                item = form.instance
                if item.pk:
                    movimentacoes.append(
                        f"Item removido: produto {self._produto_item_label(item.produto)}, "
                        f"quantidade {item.quantidade}."
                    )
                continue

            if not form.has_changed():
                continue

            produto_atual = form.cleaned_data.get("produto") or form.instance.produto
            quantidade_atual = form.cleaned_data.get("quantidade")

            if not form.instance.pk:
                if produto_atual or quantidade_atual:
                    movimentacoes.append(
                        f"Item adicionado: produto {self._produto_item_label(produto_atual)}, "
                        f"quantidade {quantidade_atual or 0}."
                    )
                continue

            partes = []
            if "produto" in form.changed_data:
                produto_anterior = self._produto_por_pk(form.initial.get("produto"))
                partes.append(
                    f"produto de {self._produto_item_label(produto_anterior)} "
                    f"para {self._produto_item_label(produto_atual)}"
                )
            if "quantidade" in form.changed_data:
                partes.append(f"quantidade de {form.initial.get('quantidade') or 0} para {quantidade_atual or 0}")

            if partes:
                movimentacoes.append("Item alterado: " + "; ".join(partes) + ".")

        return movimentacoes

    def _produto_por_pk(self, produto_id):
        if not produto_id:
            return None
        try:
            return ProdutoServico.objects.filter(pk=produto_id).first()
        except (TypeError, ValueError, DjangoValidationError):
            return None

    def _produto_item_label(self, produto):
        if not produto:
            return "-"
        return str(produto)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "contatos-por-cliente/",
                self.admin_site.admin_view(self.contatos_por_cliente_view),
                name="comercial_proposta_contatos_por_cliente",
            ),
            path(
                "calendario/",
                self.admin_site.admin_view(self.calendario_view),
                name="comercial_proposta_calendario",
            ),
            path(
                "<path:object_id>/criar-revisao/",
                self.admin_site.admin_view(self.criar_revisao_view),
                name="comercial_proposta_criar_revisao",
            ),
        ]
        return custom_urls + urls

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["contatos_cliente_url"] = reverse(
            "admin:comercial_proposta_contatos_por_cliente"
        )
        return super().changeform_view(request, object_id, form_url, extra_context)

    def contatos_por_cliente_view(self, request):
        cliente_id = request.GET.get("cliente", "").strip()
        if not cliente_id:
            return JsonResponse({"contatos": []})
        try:
            contatos = ContatoCliente.objects.filter(cliente_id=cliente_id).order_by(
                "-principal",
                "nome",
            )
        except (TypeError, ValueError):
            return JsonResponse({"contatos": []})
        return JsonResponse(
            {
                "contatos": [
                    {
                        "id": str(contato.pk),
                        "nome": contato.nome,
                        "cargo": contato.cargo,
                        "email": contato.email,
                        "principal": contato.principal,
                        "rotulo": str(contato),
                    }
                    for contato in contatos
                ]
            }
        )

    def calendario_view(self, request):
        hoje = date.today()
        try:
            ano = int(request.GET.get("ano", hoje.year))
        except (TypeError, ValueError):
            ano = hoje.year
        try:
            mes = int(request.GET.get("mes", hoje.month))
        except (TypeError, ValueError):
            mes = hoje.month

        if mes < 1:
            mes = 12
            ano -= 1
        elif mes > 12:
            mes = 1
            ano += 1

        primeiro_dia = date(ano, mes, 1)
        ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])

        propostas = (
            Proposta.objects.filter(data_emissao__range=(primeiro_dia, ultimo_dia))
            .select_related("cliente", "responsavel")
            .order_by("data_emissao", "cliente__razao_social", "codigo")
        )

        status = request.GET.get("status", "").strip()
        resultado = request.GET.get("resultado", "").strip()
        motivo = request.GET.get("motivo", "").strip()
        cliente = request.GET.get("cliente", "").strip()

        if status:
            propostas = propostas.filter(status=status)
        if resultado:
            propostas = propostas.filter(resultado_fechamento=resultado)
        if motivo:
            propostas = propostas.filter(motivo_perda=motivo)
        if cliente:
            propostas = propostas.filter(cliente_id=cliente)

        propostas = list(propostas)

        cal = calendar.Calendar(firstweekday=6)
        semanas = []
        for semana in cal.monthdatescalendar(ano, mes):
            dias = []
            for dia in semana:
                eventos = [
                    self._evento_calendario(proposta)
                    for proposta in propostas
                    if proposta.data_emissao == dia
                ]
                dias.append(
                    {
                        "data": dia,
                        "fora_mes": dia.month != mes,
                        "hoje": dia == hoje,
                        "eventos": eventos,
                    }
                )
            semanas.append(dias)

        anterior_ano, anterior_mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
        proximo_ano, proximo_mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)

        clientes = (
            Cliente.objects.filter(propostas__isnull=False)
            .order_by("codigo", "razao_social")
            .distinct()
        )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Calendario de propostas",
            "subtitulo": primeiro_dia.strftime("%B de %Y").capitalize(),
            "semanas": semanas,
            "mes": mes,
            "ano": ano,
            "status_choices": self.model.STATUS_CHOICES,
            "resultado_choices": self.model.RESULTADO_CHOICES,
            "motivo_choices": self.model.MOTIVO_PERDA_CHOICES,
            "clientes": clientes,
            "filtros": {
                "status": status,
                "resultado": resultado,
                "motivo": motivo,
                "cliente": cliente,
            },
            "link_anterior": (
                f"?mes={anterior_mes}&ano={anterior_ano}&status={status}"
                f"&resultado={resultado}&motivo={motivo}&cliente={cliente}"
            ),
            "link_proximo": (
                f"?mes={proximo_mes}&ano={proximo_ano}&status={status}"
                f"&resultado={resultado}&motivo={motivo}&cliente={cliente}"
            ),
            "novo_url": reverse("admin:comercial_proposta_add"),
            "lista_url": reverse("admin:comercial_proposta_changelist"),
            "legenda_tipos": [
                ("rascunho", "Rascunho"),
                ("enviado", "Enviado"),
                ("pendente", "Pendente"),
                ("aprovado", "Aprovado"),
                ("recusado", "Recusado"),
            ],
        }
        return render(request, "admin/comercial/proposta/calendar.html", context)

    def _evento_calendario(self, proposta):
        return {
            "codigo": proposta.codigo,
            "tipo_evento": proposta.status,
            "cliente": str(proposta.cliente) if proposta.cliente_id else "-",
            "responsavel": str(proposta.responsavel) if proposta.responsavel_id else "-",
            "status": proposta.get_status_display(),
            "resultado": proposta.get_resultado_fechamento_display(),
            "motivo": proposta.get_motivo_perda_display(),
            "total": proposta.total,
            "url": reverse("admin:comercial_proposta_change", args=[proposta.pk]),
            "pdf_url": reverse("pdf_proposta", args=[proposta.pk]),
        }

    def criar_revisao_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            self.message_user(request, "Proposta nao encontrada.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:comercial_proposta_changelist"))

        revisao = obj.criar_revisao(
            usuario=request.user,
            descricao=f"Revisao {obj.revisao or '00'} criada a partir da proposta.",
        )
        self.message_user(request, f"Revisao {revisao} criada para a proposta {obj.codigo}.", level=messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:comercial_proposta_change", args=[obj.pk]))

    def gerar_pdf(self, obj):
        try:
            url = reverse("pdf_proposta", args=[obj.id])
            return format_html(
                "<a class='button' href='{}' target='_blank'>Imprimir/PDF</a>",
                url
            )
        except:
            return "-"

    gerar_pdf.short_description = "Impressão"


# =========================
# PRODUTO / SERVIÇO
# =========================

class ComposicaoPrecoInline(admin.StackedInline):
    model = ComposicaoPreco
    extra = 0


class DadosTecnicosInline(admin.StackedInline):
    model = DadosTecnicos
    extra = 0


@admin.register(ProdutoServico)
class ProdutoServicoAdmin(admin.ModelAdmin):

    list_display = (
        "codigo",
        "nome",
        "tipo",
        "preco_venda",
        "ativo",
    )

    list_filter = ("tipo", "ativo")

    search_fields = ("codigo", "nome")

    readonly_fields = ("codigo", "preco_venda")

    inlines = [
        ComposicaoPrecoInline,
        DadosTecnicosInline,
        ProdutoAnexoInline,
    ]


# =========================
# CRM INTERAÇÕES
# =========================

class CRMInteracaoInline(admin.TabularInline):
    model = CRMInteracao
    extra = 1
    fields = ("data", "tipo", "resultado", "proxima_acao", "descricao")


class ProspeccaoInteracaoInline(admin.TabularInline):
    model = ProspeccaoInteracao
    extra = 1
    fields = (
        "data",
        "tipo",
        "resultado",
        "proxima_acao_tipo",
        "proxima_acao",
        "descricao",
    )


class ProspectoImportForm(forms.Form):
    arquivo = forms.FileField(
        label="Planilha Excel",
        help_text="Envie um arquivo .xlsx com até 50.000 contatos.",
    )


class ProspectoAutorizacaoEmailLoteForm(forms.Form):
    base_legal = forms.ChoiceField(
        label="Base legal",
        choices=Prospecto.BASE_LEGAL_MARKETING_CHOICES,
    )
    origem_evidencia = forms.CharField(
        label="Origem/evidência da autorização",
        max_length=255,
        help_text="Ex.: formulário, evento, contrato, lista revisada ou documento controlado.",
    )
    referencia_analise = forms.CharField(
        label="Referência do teste de legítimo interesse",
        max_length=255,
        required=False,
        help_text="Obrigatória quando a base legal for legítimo interesse documentado.",
    )
    observacoes = forms.CharField(
        label="Observações",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
    confirmar = forms.BooleanField(
        label="Confirmo que revisei a base legal e a evidência destes prospects.",
    )

    def __init__(self, *args, quantidade=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["confirmar"].help_text = (
            f"A ação autorizará {quantidade} prospect(s) elegível(is), sem enviar campanha."
        )

    def clean(self):
        dados = super().clean()
        if dados.get("base_legal") == "legitimo_interesse" and not (
            dados.get("referencia_analise") or ""
        ).strip():
            self.add_error(
                "referencia_analise",
                "Informe a referência do teste de balanceamento/legítimo interesse.",
            )
        return dados


class ProspeccaoComercialAdminForm(forms.ModelForm):
    class Meta:
        model = ProspeccaoComercial
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["razao_social"].required = False
        if "prospecto" in self.fields:
            queryset = Prospecto.objects.filter(
                status__in=("disponivel", "em_prospeccao")
            )
            if self.instance and self.instance.prospecto_id:
                queryset = Prospecto.objects.filter(
                    Q(pk=self.instance.prospecto_id)
                    | Q(status="disponivel", prospeccao__isnull=True)
                )
            else:
                queryset = queryset.filter(prospeccao__isnull=True)
            self.fields["prospecto"].queryset = queryset.order_by(
                "razao_social", "contato_nome"
            )

    def clean(self):
        cleaned_data = super().clean()
        prospecto = cleaned_data.get("prospecto")
        if prospecto:
            preenchimentos = {
                "razao_social": prospecto.razao_social,
                "contato_nome": prospecto.contato_nome,
                "cargo": prospecto.cargo,
                "telefone": prospecto.telefone or prospecto.whatsapp,
                "email": prospecto.email,
                "segmento": prospecto.segmento,
            }
            for campo, valor in preenchimentos.items():
                if not cleaned_data.get(campo):
                    cleaned_data[campo] = valor
                    setattr(self.instance, campo, valor)
        elif not cleaned_data.get("razao_social"):
            self.add_error(
                "razao_social",
                "Selecione um prospect ou informe a razão social.",
            )
        return cleaned_data


class ProspectoTextFilter(admin.SimpleListFilter):
    template = "admin/text_filter.html"

    def __init__(self, request, params, model, model_admin):
        self.request = request
        super().__init__(request, params, model, model_admin)

    def lookups(self, request, model_admin):
        # Mantém o filtro visível; as opções são digitadas no template.
        return (("ativo", "ativo"),)

    def has_output(self):
        return True


class ProspectoEmpresaFilter(ProspectoTextFilter):
    title = "Empresa"
    parameter_name = "empresa"
    placeholder = "Digite razão ou nome fantasia"

    def queryset(self, request, queryset):
        valor = (self.value() or "").strip()
        if valor:
            return queryset.filter(
                Q(razao_social__icontains=valor) | Q(nome_fantasia__icontains=valor)
            )
        return queryset


class ProspectoCidadeFilter(ProspectoTextFilter):
    title = "Cidade"
    parameter_name = "cidade"
    placeholder = "Digite a cidade"

    def queryset(self, request, queryset):
        valor = (self.value() or "").strip()
        return queryset.filter(cidade__icontains=valor) if valor else queryset


@admin.register(Prospecto)
class ProspectoAdmin(admin.ModelAdmin):
    change_form_template = "admin/comercial/prospecto/change_form.html"
    change_list_template = "admin/comercial/prospecto/change_list.html"
    list_display = (
        "codigo", "razao_social", "contato_nome", "telefone", "email", "cidade", "uf",
        "segmento", "status", "marketing_email_autorizado", "acao_prospeccao",
    )
    list_filter = (
        ProspectoEmpresaFilter,
        ProspectoCidadeFilter,
        "segmento",
        "uf",
        "status",
        "origem",
        "marketing_email_autorizado",
        "marketing_base_legal",
        "criado_em",
    )
    search_fields = (
        "codigo", "referencia_externa", "razao_social", "nome_fantasia", "cnpj", "contato_nome", "telefone", "email",
        "cidade", "uf", "segmento",
    )
    readonly_fields = (
        "codigo", "chave_duplicidade", "lote_importacao", "linha_importacao", "cliente_convertido",
        "convertido_por", "data_conversao", "marketing_autorizado_em",
        "marketing_autorizado_por", "marketing_lote_autorizacao", "criado_em", "atualizado_em",
    )
    autocomplete_fields = ("responsavel",)
    ordering = ("razao_social", "contato_nome")
    list_per_page = 100
    actions = ("iniciar_prospeccao_em_lote", "autorizar_email_em_lote")

    fieldsets = (
        ("Empresa", {"fields": ("razao_social", "nome_fantasia", "cnpj", "segmento", "site")}),
        ("Contato", {"fields": ("contato_nome", "cargo", "telefone", "whatsapp", "email")}),
        ("Autorização para campanhas por e-mail", {
            "fields": (
                "marketing_email_autorizado",
                "marketing_base_legal",
                "marketing_autorizado_em",
                "marketing_autorizado_por",
                "marketing_lote_autorizacao",
                "marketing_origem",
                "marketing_referencia_analise",
                "marketing_revogado_em",
                "marketing_observacoes",
            ),
            "description": (
                "Não autorize automaticamente uma base importada. Registre a base legal e a "
                "origem/evidência revisada antes de permitir campanhas."
            ),
        }),
        ("Localização e origem", {"fields": ("codigo", "endereco", "cidade", "uf", "cep", "origem", "referencia_externa", "observacoes")}),
        ("Controle", {"fields": ("responsavel", "status")}),
        ("Rastreabilidade", {
            "classes": ("collapse",),
            "fields": (
                "lote_importacao", "linha_importacao", "chave_duplicidade",
                "cliente_convertido", "convertido_por", "data_conversao",
                "criado_em", "atualizado_em",
            ),
        }),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related(
            "responsavel", "cliente_convertido"
        )
        url_name = getattr(getattr(request, "resolver_match", None), "url_name", "")
        if url_name in {
            "comercial_prospecto_changelist",
            "comercial_prospecto_exportar_excel",
        } and "status__exact" not in request.GET:
            queryset = queryset.exclude(status="convertido")
        return queryset

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(
            request, queryset, search_term
        )
        if request.GET.get("field_name") == "prospecto":
            queryset = queryset.filter(status="disponivel", prospeccao__isnull=True)
        elif request.GET.get("field_name") == "destinatarios_prospectos":
            queryset = queryset.filter(
                status__in=("disponivel", "em_prospeccao"),
                marketing_email_autorizado=True,
                marketing_autorizado_em__isnull=False,
                marketing_revogado_em__isnull=True,
            ).exclude(email="").exclude(marketing_base_legal="").exclude(marketing_origem="")
        return queryset, may_have_duplicates

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "importar-excel/",
                self.admin_site.admin_view(self.importar_excel_view),
                name="comercial_prospecto_importar_excel",
            ),
            path(
                "modelo-importacao/",
                self.admin_site.admin_view(self.download_modelo_importacao_view),
                name="comercial_prospecto_modelo_importacao",
            ),
            path(
                "exportar-excel/",
                self.admin_site.admin_view(self.exportar_excel_view),
                name="comercial_prospecto_exportar_excel",
            ),
            path(
                "<path:object_id>/iniciar-prospeccao/",
                self.admin_site.admin_view(self.iniciar_prospeccao_view),
                name="comercial_prospecto_iniciar_prospeccao",
            ),
        ]
        return custom_urls + urls

    @admin.display(description="Prospecção")
    def acao_prospeccao(self, obj):
        if obj.status == "convertido":
            return "Convertido"
        if hasattr(obj, "prospeccao"):
            url = reverse("admin:comercial_prospeccaocomercial_change", args=[obj.prospeccao.pk])
            return format_html('<a class="button" href="{}">Abrir prospecção</a>', url)
        url = reverse("admin:comercial_prospecto_iniciar_prospeccao", args=[obj.pk])
        return format_html('<a class="button" href="{}">Iniciar prospecção</a>', url)

    @admin.action(description="Iniciar prospecção para os contatos selecionados")
    def iniciar_prospeccao_em_lote(self, request, queryset):
        criadas = 0
        for prospecto in queryset.filter(
            status="disponivel", prospeccao__isnull=True
        ).iterator(chunk_size=500):
            ProspeccaoComercial.objects.create(
                prospecto=prospecto,
                responsavel=prospecto.responsavel or request.user,
                razao_social=prospecto.razao_social,
            )
            criadas += 1
        self.message_user(request, f"{criadas} prospecção(ões) iniciada(s).", messages.SUCCESS)

    @staticmethod
    def _elegiveis_autorizacao_email(queryset):
        return (
            queryset.filter(
                status__in=("disponivel", "em_prospeccao"),
                marketing_email_autorizado=False,
                marketing_revogado_em__isnull=True,
            )
            .exclude(email="")
        )

    @admin.action(description="Registrar autorização de e-mail em lote")
    def autorizar_email_em_lote(self, request, queryset):
        elegiveis = self._elegiveis_autorizacao_email(queryset)
        quantidade_selecionada = queryset.count()
        quantidade_elegivel = elegiveis.count()
        form = ProspectoAutorizacaoEmailLoteForm(
            request.POST if request.POST.get("confirmar_autorizacao_lote") else None,
            quantidade=quantidade_elegivel,
        )

        if request.POST.get("confirmar_autorizacao_lote") and form.is_valid():
            lote = uuid.uuid4()
            atualizados = elegiveis.update(
                marketing_email_autorizado=True,
                marketing_base_legal=form.cleaned_data["base_legal"],
                marketing_autorizado_em=timezone.now(),
                marketing_autorizado_por=request.user,
                marketing_lote_autorizacao=lote,
                marketing_origem=form.cleaned_data["origem_evidencia"].strip(),
                marketing_referencia_analise=(
                    form.cleaned_data["referencia_analise"] or ""
                ).strip(),
                marketing_observacoes=(form.cleaned_data["observacoes"] or "").strip(),
            )
            ignorados = quantidade_selecionada - atualizados
            self.message_user(
                request,
                (
                    f"{atualizados} prospect(s) autorizado(s) no lote {lote}; "
                    f"{ignorados} ignorado(s). Nenhuma campanha foi enviada."
                ),
                messages.SUCCESS,
            )
            return None

        selecionou_todos = request.POST.get("select_across") == "1"
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Registrar autorização de e-mail em lote",
            "form": form,
            "selecionados_ocultos": queryset[:1] if selecionou_todos else queryset,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "select_across": selecionou_todos,
            "quantidade_selecionada": quantidade_selecionada,
            "quantidade_elegivel": quantidade_elegivel,
            "quantidade_ignorada": quantidade_selecionada - quantidade_elegivel,
        }
        return render(
            request,
            "admin/comercial/prospecto/autorizar_email_lote.html",
            context,
        )

    def iniciar_prospeccao_view(self, request, object_id):
        prospecto = self.get_object(request, object_id)
        if prospecto is None:
            self.message_user(request, "Prospect não encontrado.", messages.ERROR)
            return redirect("admin:comercial_prospecto_changelist")
        if hasattr(prospecto, "prospeccao"):
            return redirect(
                "admin:comercial_prospeccaocomercial_change",
                prospecto.prospeccao.pk,
            )
        if prospecto.status == "convertido":
            self.message_user(
                request,
                "Este prospect já foi convertido em cliente e não pode iniciar outra prospecção.",
                messages.ERROR,
            )
            return redirect("admin:comercial_prospecto_change", prospecto.pk)
        if request.method != "POST":
            context = {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "title": "Transformar contato em prospecção",
                "prospecto": prospecto,
                "cancel_url": reverse(
                    "admin:comercial_prospecto_change",
                    args=[prospecto.pk],
                ),
            }
            return render(
                request,
                "admin/comercial/prospecto/confirmar_prospeccao.html",
                context,
            )
        prospeccao, criada = ProspeccaoComercial.objects.get_or_create(
            prospecto=prospecto,
            defaults={
                "responsavel": prospecto.responsavel or request.user,
                "razao_social": prospecto.razao_social,
            },
        )
        if criada:
            self.log_addition(request, prospeccao, "Prospecção iniciada a partir da base de prospects.")
        return redirect("admin:comercial_prospeccaocomercial_change", prospeccao.pk)

    def importar_excel_view(self, request):
        if not self.has_add_permission(request):
            return redirect("admin:comercial_prospecto_changelist")

        preview = None
        token = request.POST.get("token", "")
        if request.method == "POST" and request.POST.get("confirmar") and token:
            caminho = request.session.get(f"prospectos_importacao_{token}")
            if not caminho or not default_storage.exists(caminho):
                self.message_user(request, "A validação expirou. Envie a planilha novamente.", messages.ERROR)
            else:
                with default_storage.open(caminho, "rb") as arquivo:
                    resultado = self._analisar_planilha(arquivo)
                if resultado["erros"]:
                    preview = resultado
                    self.message_user(request, "A planilha possui erros e não foi importada.", messages.ERROR)
                else:
                    lote = uuid.uuid4()
                    objetos = [self._prospecto_da_linha(item, lote) for item in resultado["validos"]]
                    with transaction.atomic():
                        codigos = Prospecto.reservar_codigos(len(objetos))
                        for objeto, codigo in zip(objetos, codigos):
                            objeto.codigo = codigo
                        Prospecto.objects.bulk_create(objetos, batch_size=500)
                    default_storage.delete(caminho)
                    request.session.pop(f"prospectos_importacao_{token}", None)
                    request.session.pop("prospectos_importacao_token", None)
                    self.message_user(
                        request,
                        f"{len(objetos)} contato(s) importado(s); {resultado['duplicados']} duplicado(s) ignorado(s).",
                        messages.SUCCESS,
                    )
                    return redirect("admin:comercial_prospecto_changelist")

        form = ProspectoImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and request.POST.get("validar") and form.is_valid():
            arquivo = form.cleaned_data["arquivo"]
            conteudo = arquivo.read()
            preview = self._analisar_planilha(BytesIO(conteudo))
            if not preview["erros"]:
                token_anterior = request.session.get("prospectos_importacao_token")
                if token_anterior:
                    caminho_anterior = request.session.pop(
                        f"prospectos_importacao_{token_anterior}", None
                    )
                    if caminho_anterior and default_storage.exists(caminho_anterior):
                        default_storage.delete(caminho_anterior)
                token = uuid.uuid4().hex
                caminho = default_storage.save(
                    f"importacoes/prospectos/pendentes/{request.user.pk}/{token}.xlsx",
                    ContentFile(conteudo),
                )
                request.session[f"prospectos_importacao_{token}"] = caminho
                request.session["prospectos_importacao_token"] = token

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar base de prospects",
            "form": form,
            "preview": preview,
            "token": token,
            "download_model_url": reverse("admin:comercial_prospecto_modelo_importacao"),
        }
        return render(request, "admin/comercial/prospecto/importar_excel.html", context)

    def download_modelo_importacao_view(self, request):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Prospects"
        worksheet.append(self._headers_importacao())
        worksheet.append([
            "ORIGEM-00001", "Empresa Exemplo Ltda", "Empresa Exemplo", "12.345.678/0001-90", "Maria Silva",
            "Compras", "(11) 3333-4444", "(11) 99999-8888", "maria@exemplo.com",
            "https://exemplo.com", "Indústria", "Rua Exemplo, 100", "São Paulo", "SP",
            "01000-000", "Feira 2026", "",
        ])
        self._formatar_planilha(worksheet)
        output = BytesIO()
        workbook.save(output)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="modelo_base_prospects.xlsx"'
        return response

    def exportar_excel_view(self, request):
        changelist = self.get_changelist_instance(request)
        queryset = changelist.get_queryset(request).select_related(
            "responsavel", "cliente_convertido"
        )

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Base de prospects"
        headers = [
            "codigo", "referencia_externa", "razao_social", "nome_fantasia", "cnpj",
            "contato_nome", "cargo", "telefone", "whatsapp", "email", "site",
            "segmento", "endereco", "cidade", "uf", "cep", "origem", "status",
            "responsavel", "observacoes", "criado_em",
        ]
        worksheet.append(headers)
        for prospecto in queryset.iterator(chunk_size=1000):
            worksheet.append([
                prospecto.codigo,
                prospecto.referencia_externa,
                prospecto.razao_social,
                prospecto.nome_fantasia,
                prospecto.cnpj,
                prospecto.contato_nome,
                prospecto.cargo,
                prospecto.telefone,
                prospecto.whatsapp,
                prospecto.email,
                prospecto.site,
                prospecto.segmento,
                prospecto.endereco,
                prospecto.cidade,
                prospecto.uf,
                prospecto.cep,
                prospecto.origem,
                prospecto.status,
                prospecto.responsavel.get_username() if prospecto.responsavel else "",
                prospecto.observacoes,
                prospecto.criado_em.replace(tzinfo=None) if prospecto.criado_em else None,
            ])
        self._formatar_planilha(worksheet)
        worksheet.column_dimensions["T"].width = 45
        worksheet.column_dimensions["U"].width = 20
        for cell in worksheet["U"][1:]:
            cell.number_format = "yyyy-mm-dd hh:mm"

        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="base_prospects_exportada.xlsx"'
        return response

    @staticmethod
    def _formatar_planilha(worksheet):
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        worksheet.sheet_view.showGridLines = False
        preenchimento = PatternFill("solid", fgColor="0B4F9C")
        for cell in worksheet[1]:
            cell.fill = preenchimento
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center")
        worksheet.row_dimensions[1].height = 24
        for indice, coluna in enumerate(worksheet.columns, start=1):
            maior = max(len(str(celula.value or "")) for celula in coluna)
            worksheet.column_dimensions[get_column_letter(indice)].width = min(
                max(maior + 2, 14), 32
            )

    @staticmethod
    def _headers_importacao():
        return [
            "referencia_externa", "razao_social", "nome_fantasia", "cnpj", "contato_nome",
            "cargo", "telefone", "whatsapp", "email", "site", "segmento", "endereco",
            "cidade", "uf", "cep", "origem", "observacoes",
        ]

    @staticmethod
    def _texto(valor):
        if valor is None:
            return ""
        if isinstance(valor, float) and valor.is_integer():
            valor = int(valor)
        return str(valor).strip()

    def _analisar_planilha(self, arquivo):
        try:
            workbook = load_workbook(arquivo, read_only=True, data_only=True)
        except Exception as exc:
            return {"validos": [], "duplicados": 0, "erros": [f"Arquivo inválido: {exc}"], "amostra": []}
        worksheet = workbook.active
        linhas = worksheet.iter_rows(values_only=True)
        try:
            cabecalhos = [self._texto(item).casefold() for item in next(linhas)]
        except StopIteration:
            return {"validos": [], "duplicados": 0, "erros": ["A planilha está vazia."], "amostra": []}
        if "razao_social" not in cabecalhos:
            return {"validos": [], "duplicados": 0, "erros": ["Coluna obrigatória ausente: razao_social."], "amostra": []}

        validos = []
        erros = []
        duplicados = 0
        chaves_arquivo = set()
        chaves_existentes = set(
            Prospecto.objects.values_list("chave_duplicidade", flat=True).iterator(chunk_size=2000)
        )
        chaves_email_telefone_arquivo = set()
        chaves_email_telefone_existentes = set(
            Prospecto.objects.exclude(chave_email_telefone__isnull=True).values_list(
                "chave_email_telefone", flat=True
            ).iterator(chunk_size=2000)
        )
        limites = {
            "razao_social": 255, "nome_fantasia": 255, "cnpj": 18,
            "contato_nome": 120, "cargo": 120, "telefone": 100,
            "whatsapp": 100, "email": 254, "site": 200, "segmento": 120,
            "cidade": 100, "uf": 2, "origem": 120,
            "endereco": 255, "cep": 12, "referencia_externa": 50,
        }
        for numero_linha, valores in enumerate(linhas, start=2):
            if numero_linha > 50001:
                erros.append("Limite de 50.000 contatos por planilha excedido.")
                break
            registro = {
                cabecalhos[indice]: self._texto(valor)
                for indice, valor in enumerate(valores)
                if indice < len(cabecalhos) and cabecalhos[indice]
            }
            if not any(registro.values()):
                continue
            razao_social = registro.get("razao_social", "")
            if not razao_social:
                erros.append(f"Linha {numero_linha}: razao_social é obrigatória.")
                continue
            campo_excedido = next(
                (
                    campo for campo, limite in limites.items()
                    if len(registro.get(campo, "")) > limite
                ),
                None,
            )
            if campo_excedido:
                erros.append(
                    f"Linha {numero_linha}: campo {campo_excedido} excede o tamanho permitido."
                )
                continue
            email = registro.get("email", "").lower()
            if email:
                try:
                    validate_email(email)
                except DjangoValidationError:
                    erros.append(f"Linha {numero_linha}: e-mail inválido.")
                    continue
            site = registro.get("site", "")
            if site:
                try:
                    URLValidator()(site)
                except DjangoValidationError:
                    erros.append(f"Linha {numero_linha}: site/URL inválido.")
                    continue
            cnpj = registro.get("cnpj", "")
            digitos_cnpj = re.sub(r"\D", "", cnpj)
            if cnpj and len(digitos_cnpj) != 14:
                erros.append(f"Linha {numero_linha}: CNPJ deve conter 14 dígitos.")
                continue
            chave = Prospecto.gerar_chave_duplicidade(
                razao_social=razao_social,
                cnpj=cnpj,
                email=email,
                telefone=registro.get("telefone", ""),
                contato_nome=registro.get("contato_nome", ""),
            )
            chave_email_telefone = Prospecto.gerar_chave_email_telefone(
                email=email,
                telefone=registro.get("telefone", "") or registro.get("whatsapp", ""),
            )
            if (
                chave in chaves_arquivo
                or chave in chaves_existentes
                or chave_email_telefone in chaves_email_telefone_arquivo
                or chave_email_telefone in chaves_email_telefone_existentes
            ):
                duplicados += 1
                continue
            chaves_arquivo.add(chave)
            if chave_email_telefone:
                chaves_email_telefone_arquivo.add(chave_email_telefone)
            registro.update({
                "linha": numero_linha,
                "chave_duplicidade": chave,
                "chave_email_telefone": chave_email_telefone,
                "email": email,
            })
            validos.append(registro)
        workbook.close()
        return {
            "validos": validos,
            "duplicados": duplicados,
            "erros": erros,
            "amostra": validos[:20],
        }

    def _prospecto_da_linha(self, registro, lote):
        campos = self._headers_importacao()
        dados = {campo: registro.get(campo, "") for campo in campos}
        dados["uf"] = dados["uf"].upper()[:2]
        return Prospecto(
            **dados,
            lote_importacao=lote,
            linha_importacao=registro["linha"],
            chave_duplicidade=registro["chave_duplicidade"],
            chave_email_telefone=registro["chave_email_telefone"],
        )


@admin.register(ProspeccaoComercial)
class ProspeccaoComercialAdmin(admin.ModelAdmin):

    form = ProspeccaoComercialAdminForm
    change_list_template = "admin/comercial/prospeccaocomercial/change_list.html"

    list_display = (
        "codigo",
        "razao_social",
        "contato_nome",
        "telefone",
        "proxima_acao_exibicao",
        "status",
        "data_cadastro",
        "crm_gerado",
        "botao_converter",
    )

    list_filter = (
        "status",
        "origem_lead",
        "data_cadastro",
    )

    search_fields = (
        "codigo",
        "razao_social",
        "contato_nome",
        "telefone",
        "email",
    )

    readonly_fields = (
        "codigo",
        "data_cadastro",
        "data_conversao",
        "convertido_por",
        "crm_gerado",
        "botao_converter",
        "cliente",
    )

    autocomplete_fields = ("prospecto", "responsavel")
    ordering = ("-data_cadastro", "-id")
    inlines = [ProspeccaoInteracaoInline]

    fieldsets = (
        ("Controle", {
            "fields": (
                "codigo",
                "status",
                "origem_lead",
                "responsavel",
            )
        }),
        ("Empresa e contato", {
            "fields": (
                "prospecto",
                "razao_social",
                "contato_nome",
                "cargo",
                "telefone",
                "email",
                "segmento",
            )
        }),
        ("Conversão", {
            "fields": (
                "cliente",
                "crm_gerado",
                "data_cadastro",
                "data_conversao",
                "convertido_por",
                "botao_converter",
            )
        }),
        ("Observações", {
            "fields": ("observacoes",)
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "calendario/",
                self.admin_site.admin_view(self.calendario_view),
                name="comercial_prospeccaocomercial_calendario",
            ),
            path(
                "agenda/",
                self.admin_site.admin_view(self.agenda_view),
                name="comercial_prospeccaocomercial_agenda",
            ),
            path(
                "<path:object_id>/converter-crm/",
                self.admin_site.admin_view(self.converter_para_crm_view),
                name="comercial_prospeccaocomercial_converter_crm",
            ),
        ]
        return custom_urls + urls

    def get_queryset(self, request):
        ultima_interacao = ProspeccaoInteracao.objects.filter(
            prospeccao=OuterRef("pk")
        ).order_by("-data", "-pk")
        return super().get_queryset(request).annotate(
            proxima_acao_lista=Subquery(
                ultima_interacao.values("proxima_acao")[:1]
            )
        )

    @admin.display(ordering="proxima_acao_lista", description="Próxima ação")
    def proxima_acao_exibicao(self, obj):
        if not obj.proxima_acao_lista:
            return "—"
        return timezone.localtime(obj.proxima_acao_lista).strftime("%d/%m/%Y %H:%M")

    def changelist_view(self, request, extra_context=None):
        hoje = timezone.localdate()
        ultima_interacao = ProspeccaoInteracao.objects.filter(
            prospeccao=OuterRef("pk")
        ).order_by("-data", "-pk")
        total_acoes_hoje = (
            self.get_queryset(request)
            .exclude(status__in=("convertido", "perdido", "sem_interesse"))
            .annotate(
                proxima_acao_atual=Subquery(
                    ultima_interacao.values("proxima_acao")[:1]
                ),
                ultimo_resultado=Subquery(
                    ultima_interacao.values("resultado")[:1]
                ),
            )
            .filter(proxima_acao_atual__date=hoje)
            .exclude(ultimo_resultado__in=("sem_interesse", "convertido"))
            .count()
        )
        contexto = {
            "prospeccao_alerta_hoje_total": total_acoes_hoje,
            "prospeccao_alerta_hoje_data": hoje,
            "prospeccao_alerta_hoje_url": (
                f'{reverse("admin:comercial_prospeccaocomercial_agenda")}'
                f'?data={hoje.isoformat()}'
            ),
        }
        if extra_context:
            contexto.update(extra_context)
        return super().changelist_view(request, extra_context=contexto)

    def agenda_view(self, request):
        data_texto = (request.GET.get("data") or "").strip()
        try:
            data_referencia = date.fromisoformat(data_texto) if data_texto else timezone.localdate()
        except ValueError:
            data_referencia = timezone.localdate()

        ultima_interacao = ProspeccaoInteracao.objects.filter(
            prospeccao=OuterRef("pk")
        ).order_by("-data", "-pk")
        queryset = (
            self.get_queryset(request)
            .exclude(status__in=("convertido", "perdido", "sem_interesse"))
            .annotate(
                proxima_acao_atual=Subquery(ultima_interacao.values("proxima_acao")[:1]),
                proxima_acao_tipo_atual=Subquery(
                    ultima_interacao.values("proxima_acao_tipo")[:1]
                ),
                proxima_acao_descricao=Subquery(
                    ultima_interacao.values("descricao")[:1]
                ),
                ultimo_resultado=Subquery(ultima_interacao.values("resultado")[:1]),
            )
            .exclude(proxima_acao_atual__isnull=True)
            .select_related("responsavel", "prospecto")
            .order_by("proxima_acao_atual", "razao_social")
        )

        responsavel_id = (request.GET.get("responsavel") or "").strip()
        if responsavel_id:
            queryset = queryset.filter(responsavel_id=responsavel_id)

        atrasadas = []
        tarefas_do_dia = []
        proximas = []
        rotulos_tipo = dict(ProspeccaoInteracao.TIPO_PROXIMA_ACAO_CHOICES)
        for prospeccao in queryset:
            if prospeccao.ultimo_resultado in ("sem_interesse", "convertido"):
                continue
            momento_local = timezone.localtime(prospeccao.proxima_acao_atual)
            item = {
                "prospeccao": prospeccao,
                "momento": momento_local,
                "tipo": rotulos_tipo.get(
                    prospeccao.proxima_acao_tipo_atual,
                    "Não definido",
                ),
                "descricao": prospeccao.proxima_acao_descricao or "",
            }
            if momento_local.date() < data_referencia:
                atrasadas.append(item)
            elif momento_local.date() == data_referencia:
                tarefas_do_dia.append(item)
            else:
                proximas.append(item)

        modelo_usuario = ProspeccaoComercial._meta.get_field(
            "responsavel"
        ).remote_field.model
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Agenda de Prospecção",
            "data_referencia": data_referencia,
            "data_anterior": data_referencia - timedelta(days=1),
            "data_seguinte": data_referencia + timedelta(days=1),
            "hoje": timezone.localdate(),
            "atrasadas": atrasadas,
            "tarefas_do_dia": tarefas_do_dia,
            "proximas": proximas[:10],
            "responsaveis": modelo_usuario.objects.filter(is_active=True).order_by(
                "first_name", "username"
            ),
            "responsavel_id": responsavel_id,
        }
        return render(
            request,
            "admin/comercial/prospeccaocomercial/agenda.html",
            context,
        )

    def calendario_view(self, request):
        hoje = timezone.localdate()
        try:
            ano = int(request.GET.get("ano", hoje.year))
        except (TypeError, ValueError):
            ano = hoje.year
        try:
            mes = int(request.GET.get("mes", hoje.month))
        except (TypeError, ValueError):
            mes = hoje.month
        if mes < 1:
            mes, ano = 12, ano - 1
        elif mes > 12:
            mes, ano = 1, ano + 1

        calendario = calendar.Calendar(firstweekday=6)
        semanas_base = calendario.monthdatescalendar(ano, mes)
        inicio_grade = semanas_base[0][0]
        fim_grade = semanas_base[-1][-1]

        ultima_interacao = ProspeccaoInteracao.objects.filter(
            prospeccao=OuterRef("pk")
        ).order_by("-data", "-pk")
        queryset = (
            self.get_queryset(request)
            .exclude(status__in=("convertido", "perdido", "sem_interesse"))
            .annotate(
                proxima_acao_atual=Subquery(ultima_interacao.values("proxima_acao")[:1]),
                proxima_acao_tipo_atual=Subquery(
                    ultima_interacao.values("proxima_acao_tipo")[:1]
                ),
                proxima_acao_descricao=Subquery(
                    ultima_interacao.values("descricao")[:1]
                ),
                ultimo_resultado=Subquery(ultima_interacao.values("resultado")[:1]),
            )
            .filter(proxima_acao_atual__date__range=(inicio_grade, fim_grade))
            .select_related("responsavel", "prospecto")
            .order_by("proxima_acao_atual", "razao_social")
        )

        responsavel_id = (request.GET.get("responsavel") or "").strip()
        tipo_filtro = (request.GET.get("tipo") or "").strip()
        if responsavel_id:
            queryset = queryset.filter(responsavel_id=responsavel_id)
        if tipo_filtro:
            queryset = queryset.filter(proxima_acao_tipo_atual=tipo_filtro)

        rotulos_tipo = dict(ProspeccaoInteracao.TIPO_PROXIMA_ACAO_CHOICES)
        eventos_por_dia = {}
        for prospeccao in queryset:
            if prospeccao.ultimo_resultado in ("sem_interesse", "convertido"):
                continue
            momento = timezone.localtime(prospeccao.proxima_acao_atual)
            eventos_por_dia.setdefault(momento.date(), []).append(
                {
                    "prospeccao": prospeccao,
                    "hora": momento.strftime("%H:%M"),
                    "tipo": prospeccao.proxima_acao_tipo_atual or "indefinido",
                    "tipo_rotulo": rotulos_tipo.get(
                        prospeccao.proxima_acao_tipo_atual,
                        "Não definido",
                    ),
                    "descricao": prospeccao.proxima_acao_descricao or "",
                }
            )

        semanas = []
        for semana in semanas_base:
            semanas.append(
                [
                    {
                        "data": dia,
                        "fora_mes": dia.month != mes,
                        "hoje": dia == hoje,
                        "eventos": eventos_por_dia.get(dia, []),
                    }
                    for dia in semana
                ]
            )

        anterior_ano, anterior_mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
        proximo_ano, proximo_mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
        parametros_filtro = f"&responsavel={responsavel_id}&tipo={tipo_filtro}"
        meses = (
            "",
            "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
        )
        modelo_usuario = ProspeccaoComercial._meta.get_field(
            "responsavel"
        ).remote_field.model
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Calendário Geral da Prospecção",
            "subtitulo": f"{meses[mes]} de {ano}",
            "semanas": semanas,
            "mes": mes,
            "ano": ano,
            "hoje": hoje,
            "responsaveis": modelo_usuario.objects.filter(is_active=True).order_by(
                "first_name", "username"
            ),
            "responsavel_id": responsavel_id,
            "tipo_filtro": tipo_filtro,
            "tipos": ProspeccaoInteracao.TIPO_PROXIMA_ACAO_CHOICES,
            "link_anterior": (
                f"?mes={anterior_mes}&ano={anterior_ano}{parametros_filtro}"
            ),
            "link_proximo": (
                f"?mes={proximo_mes}&ano={proximo_ano}{parametros_filtro}"
            ),
            "agenda_url": reverse("admin:comercial_prospeccaocomercial_agenda"),
            "lista_url": reverse("admin:comercial_prospeccaocomercial_changelist"),
        }
        return render(
            request,
            "admin/comercial/prospeccaocomercial/calendario.html",
            context,
        )

    def botao_converter(self, obj):
        if not obj.pk:
            return "-"
        if obj.crm_gerado_id:
            try:
                url = reverse("admin:comercial_crmregistro_change", args=[obj.crm_gerado_id])
                return format_html("<a class='button' href='{}'>Abrir CRM</a>", url)
            except Exception:
                return obj.crm_gerado

        url = reverse("admin:comercial_prospeccaocomercial_converter_crm", args=[obj.pk])
        return format_html("<a class='button' href='{}'>Converter para CRM</a>", url)

    botao_converter.short_description = "Conversão"

    def converter_para_crm_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            self.message_user(request, "Prospecção não encontrada.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:comercial_prospeccaocomercial_changelist"))

        if request.method != "POST":
            context = {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "title": "Confirmar conversão para CRM",
                "obj": obj,
                "cancel_url": reverse(
                    "admin:comercial_prospeccaocomercial_change", args=[obj.pk]
                ),
            }
            return render(
                request,
                "admin/comercial/prospeccaocomercial/confirmar_conversao.html",
                context,
            )

        crm = obj.converter_para_crm(usuario=request.user)
        self.message_user(
            request,
            f"Prospecção {obj.codigo} convertida para CRM {crm.codigo}.",
            level=messages.SUCCESS,
        )
        return HttpResponseRedirect(reverse("admin:comercial_prospeccaocomercial_change", args=[obj.pk]))


@admin.register(CRMInteracao)
class CRMInteracaoAdmin(admin.ModelAdmin):

    list_display = (
        "data",
        "tipo",
        "resultado",
        "proxima_acao",
        "crm",
        "cliente_relacionado",
        "descricao_curta",
    )

    list_filter = (
        "tipo",
        "resultado",
        "data",
    )

    search_fields = (
        "crm__codigo",
        "crm__titulo",
        "crm__cliente__razao_social",
        "descricao",
    )

    autocomplete_fields = ("crm",)
    ordering = ("-data", "-id")

    def cliente_relacionado(self, obj):
        return obj.crm.cliente

    cliente_relacionado.short_description = "Cliente"

    def descricao_curta(self, obj):
        texto = (obj.descricao or "").strip().replace("\n", " ")
        return texto[:90] + ("..." if len(texto) > 90 else "")

    descricao_curta.short_description = "Descrição"


# =========================
# CRM REGISTRO
# =========================

@admin.register(CRMRegistro)
class CRMRegistroAdmin(admin.ModelAdmin):
    change_list_template = "admin/comercial/crmregistro/change_list.html"

    list_display = (
        "codigo",
        "cliente",
        "titulo",
        "data_registro",
        "etapa_funil",
        "valor_estimado",
        "probabilidade",
    )

    list_filter = (
        "etapa_funil",
        "data_registro",
    )

    search_fields = (
        "codigo",
        "cliente__razao_social",
        "titulo",
    )

    readonly_fields = ("codigo", "data_registro", "probabilidade_numero")
    ordering = ("-data_registro", "-id")

    autocomplete_fields = ("cliente", "proposta")

    inlines = [CRMInteracaoInline]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "calendario/",
                self.admin_site.admin_view(self.calendario_view),
                name="comercial_crmregistro_calendario",
            ),
        ]
        return custom_urls + urls

    def calendario_view(self, request):
        hoje = date.today()
        try:
            ano = int(request.GET.get("ano", hoje.year))
        except (TypeError, ValueError):
            ano = hoje.year
        try:
            mes = int(request.GET.get("mes", hoje.month))
        except (TypeError, ValueError):
            mes = hoje.month

        if mes < 1:
            mes = 12
            ano -= 1
        elif mes > 12:
            mes = 1
            ano += 1

        primeiro_dia = date(ano, mes, 1)
        ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])

        registros = (
            CRMRegistro.objects.filter(
                data_registro__date__range=(primeiro_dia, ultimo_dia)
            )
            | CRMRegistro.objects.filter(proxima_acao__range=(primeiro_dia, ultimo_dia))
        ).select_related("cliente", "proposta", "responsavel").order_by("data_registro", "cliente__razao_social", "codigo")

        etapa = request.GET.get("etapa", "").strip()
        cliente = request.GET.get("cliente", "").strip()
        probabilidade = request.GET.get("probabilidade", "").strip()

        if etapa:
            registros = registros.filter(etapa_funil=etapa)
        if cliente:
            registros = registros.filter(cliente_id=cliente)
        if probabilidade:
            registros = registros.filter(probabilidade=probabilidade)

        registros = list(registros.distinct())

        cal = calendar.Calendar(firstweekday=6)
        semanas = []
        for semana in cal.monthdatescalendar(ano, mes):
            dias = []
            for dia in semana:
                eventos = []
                for registro in registros:
                    if registro.data_registro.date() == dia:
                        eventos.append(self._evento_calendario(registro, "registro"))
                    if registro.proxima_acao == dia:
                        eventos.append(self._evento_calendario(registro, "proxima_acao"))
                dias.append(
                    {
                        "data": dia,
                        "fora_mes": dia.month != mes,
                        "hoje": dia == hoje,
                        "eventos": eventos,
                    }
                )
            semanas.append(dias)

        anterior_ano, anterior_mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
        proximo_ano, proximo_mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)

        clientes = (
            Cliente.objects.filter(crmregistro__isnull=False)
            .order_by("codigo", "razao_social")
            .distinct()
        )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Calendario de registros de CRM",
            "subtitulo": primeiro_dia.strftime("%B de %Y").capitalize(),
            "semanas": semanas,
            "mes": mes,
            "ano": ano,
            "etapa_choices": self.model.ETAPA_CHOICES,
            "probabilidade_choices": self.model.PROBABILIDADE_CHOICES,
            "clientes": clientes,
            "filtros": {
                "etapa": etapa,
                "cliente": cliente,
                "probabilidade": probabilidade,
            },
            "link_anterior": (
                f"?mes={anterior_mes}&ano={anterior_ano}&etapa={etapa}"
                f"&cliente={cliente}&probabilidade={probabilidade}"
            ),
            "link_proximo": (
                f"?mes={proximo_mes}&ano={proximo_ano}&etapa={etapa}"
                f"&cliente={cliente}&probabilidade={probabilidade}"
            ),
            "novo_url": reverse("admin:comercial_crmregistro_add"),
            "lista_url": reverse("admin:comercial_crmregistro_changelist"),
            "legenda_tipos": [
                ("registro", "Registro criado"),
                ("proxima_acao", "Proxima acao"),
                ("fechado_ganho", "Fechado ganho"),
                ("fechado_perdido", "Fechado perdido"),
            ],
        }
        return render(request, "admin/comercial/crmregistro/calendar.html", context)

    def _evento_calendario(self, registro, tipo_evento):
        status_key = tipo_evento
        if registro.etapa_funil in ("fechado_ganho", "fechado_perdido"):
            status_key = registro.etapa_funil

        return {
            "titulo": "Proxima acao" if tipo_evento == "proxima_acao" else "Registro",
            "tipo_evento": status_key,
            "codigo": registro.codigo,
            "cliente": str(registro.cliente),
            "titulo_crm": registro.titulo,
            "etapa": registro.get_etapa_funil_display(),
            "probabilidade": registro.get_probabilidade_display(),
            "valor_estimado": registro.valor_estimado,
            "responsavel": str(registro.responsavel) if registro.responsavel_id else "-",
            "proposta": registro.proposta.codigo if registro.proposta_id else "",
            "url": reverse("admin:comercial_crmregistro_change", args=[registro.pk]),
        }


# =========================
# CRM TICKET
# =========================

@admin.register(CRMTicket)
class CRMTicketAdmin(admin.ModelAdmin):

    list_display = (
        "codigo",
        "cliente",
        "titulo",
        "data_abertura",
        "status",
        "prioridade",
    )

    list_filter = (
        "status",
        "prioridade",
        "data_abertura",
    )

    search_fields = (
        "codigo",
        "cliente__razao_social",
        "titulo",
    )

    readonly_fields = ("codigo", "data_abertura")
    ordering = ("-data_abertura", "-id")

    autocomplete_fields = ("cliente",)
