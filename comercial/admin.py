import calendar
from datetime import date

from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.html import format_html
from django.urls import reverse
from django.urls import path
from django.db.models import Sum

from clientes.models import Cliente

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

@admin.register(Proposta)
class PropostaAdmin(admin.ModelAdmin):
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
    )

    class Media:
        js = ("js/proposta_margem.js",)

    autocomplete_fields = ("cliente", "responsavel")

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
        except (TypeError, ValueError):
            return None

    def _produto_item_label(self, produto):
        if not produto:
            return "-"
        return str(produto)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
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
    fields = ("data", "tipo", "resultado", "proxima_acao", "descricao")


@admin.register(ProspeccaoComercial)
class ProspeccaoComercialAdmin(admin.ModelAdmin):

    list_display = (
        "codigo",
        "razao_social",
        "contato_nome",
        "telefone",
        "origem_lead",
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
    )

    autocomplete_fields = ("cliente", "responsavel")
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
                "cliente",
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
                "<path:object_id>/converter-crm/",
                self.admin_site.admin_view(self.converter_para_crm_view),
                name="comercial_prospeccaocomercial_converter_crm",
            ),
        ]
        return custom_urls + urls

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
