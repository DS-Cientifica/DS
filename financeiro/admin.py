import calendar
from datetime import date

from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.db.models import Q, Sum

from clientes.models import Cliente
from comercial.models import Proposta

from .helpers import EMPRESA_COMPRADORA, contato_principal_cliente, endereco_cliente
from .models import (
    AnexoNotaFiscal,
    CategoriaFinanceira,
    ContaPagar,
    ContaReceber,
    Imposto,
    ItemNotaFiscal,
    NotaFiscal,
    PedidoCompra,
    PedidoCompraItem,
)


@admin.register(CategoriaFinanceira)
class CategoriaFinanceiraAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome")
    readonly_fields = ("codigo",)
    search_fields = ("codigo", "nome")


@admin.register(ContaPagar)
class ContaPagarAdmin(admin.ModelAdmin):
    change_list_template = "admin/financeiro/contapagar/change_list.html"

    list_display = (
        "descricao",
        "fornecedor",
        "pedido_compra",
        "valor",
        "vencimento",
        "status",
    )
    list_filter = ("status", "vencimento", "categoria")
    search_fields = ("descricao", "fornecedor", "pedido_compra__numero_pedido")
    date_hierarchy = "vencimento"
    ordering = ("vencimento",)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "calendario/",
                self.admin_site.admin_view(self.calendario_view),
                name="financeiro_contapagar_calendario",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        response = super().changelist_view(request, extra_context=extra_context)

        if hasattr(response, "context_data") and response.context_data and "cl" in response.context_data:
            changelist = response.context_data["cl"]
            response.context_data.update({
                "filtro_status_atual": request.GET.get("status__exact", ""),
                "filtro_categoria_atual": request.GET.get("categoria__id__exact", ""),
                "status_choices_rapido": self.model.STATUS_CHOICES,
                "categoria_choices_rapido": CategoriaFinanceira.objects.order_by("nome"),
                "total_filtrado_contas_pagar": changelist.queryset.aggregate(total=Sum("valor"))["total"] or 0,
                "quantidade_filtrada_contas_pagar": changelist.result_count,
            })

        return response

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

        contas = (
            ContaPagar.objects.filter(
                Q(vencimento__range=(primeiro_dia, ultimo_dia))
                | Q(data_pagamento__range=(primeiro_dia, ultimo_dia))
            )
            .select_related("categoria", "pedido_compra")
            .order_by("vencimento", "fornecedor", "descricao")
        )

        status = request.GET.get("status", "").strip()
        categoria = request.GET.get("categoria", "").strip()
        fornecedor = request.GET.get("fornecedor", "").strip()

        if status:
            contas = contas.filter(status=status)
        if categoria:
            contas = contas.filter(categoria_id=categoria)
        if fornecedor:
            contas = contas.filter(fornecedor=fornecedor)

        contas = list(contas)

        cal = calendar.Calendar(firstweekday=6)
        semanas = []
        for semana in cal.monthdatescalendar(ano, mes):
            dias = []
            for dia in semana:
                eventos = []
                for conta in contas:
                    if conta.vencimento == dia:
                        eventos.append(self._evento_calendario(conta, "vencimento"))
                    if conta.data_pagamento == dia:
                        eventos.append(self._evento_calendario(conta, "pagamento"))
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

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Calendario de contas a pagar",
            "subtitulo": primeiro_dia.strftime("%B de %Y").capitalize(),
            "semanas": semanas,
            "mes": mes,
            "ano": ano,
            "status_choices": self.model.STATUS_CHOICES,
            "categorias": CategoriaFinanceira.objects.order_by("nome"),
            "fornecedores": (
                ContaPagar.objects.exclude(fornecedor="")
                .order_by("fornecedor")
                .values_list("fornecedor", flat=True)
                .distinct()
            ),
            "filtros": {
                "status": status,
                "categoria": categoria,
                "fornecedor": fornecedor,
            },
            "link_anterior": f"?mes={anterior_mes}&ano={anterior_ano}&status={status}&categoria={categoria}&fornecedor={fornecedor}",
            "link_proximo": f"?mes={proximo_mes}&ano={proximo_ano}&status={status}&categoria={categoria}&fornecedor={fornecedor}",
            "novo_url": reverse("admin:financeiro_contapagar_add"),
            "lista_url": reverse("admin:financeiro_contapagar_changelist"),
            "legenda_tipos": [
                ("vencimento", "Vencimento"),
                ("pagamento", "Pagamento"),
                ("atrasado", "Atrasado"),
            ],
        }
        return render(request, "admin/financeiro/contapagar/calendar.html", context)

    def _evento_calendario(self, conta, tipo_evento):
        titulo = "Pagamento" if tipo_evento == "pagamento" else "Vencimento"
        status_key = "atrasado" if tipo_evento == "vencimento" and conta.status == "atrasado" else tipo_evento
        return {
            "titulo": titulo,
            "tipo_evento": status_key,
            "descricao": conta.descricao,
            "fornecedor": conta.fornecedor,
            "categoria": conta.categoria.nome if conta.categoria_id else "-",
            "pedido_compra": conta.pedido_compra.numero_pedido if conta.pedido_compra_id else "",
            "status": conta.get_status_display(),
            "valor": conta.valor,
            "tem_comprovante": bool(conta.comprovante),
            "url": reverse("admin:financeiro_contapagar_change", args=[conta.pk]),
        }


@admin.register(ContaReceber)
class ContaReceberAdmin(admin.ModelAdmin):
    change_list_template = "admin/financeiro/contareceber/change_list.html"

    list_display = (
        "proposta",
        "cliente",
        "descricao",
        "valor",
        "vencimento",
        "status",
    )
    list_filter = ("status", "vencimento")
    search_fields = (
        "proposta__codigo",
        "cliente__razao_social",
        "cliente__cnpj",
        "descricao",
    )
    autocomplete_fields = ("proposta", "cliente")
    date_hierarchy = "vencimento"
    ordering = ("vencimento",)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        response = super().changelist_view(request, extra_context=extra_context)

        if hasattr(response, "context_data") and response.context_data and "cl" in response.context_data:
            changelist = response.context_data["cl"]
            response.context_data.update({
                "filtro_status_atual": request.GET.get("status__exact", ""),
                "status_choices_rapido": self.model.STATUS_CHOICES,
                "total_filtrado_contas_receber": changelist.queryset.aggregate(total=Sum("valor"))["total"] or 0,
                "quantidade_filtrada_contas_receber": changelist.result_count,
            })

        return response

    class Media:
        js = ("js/conta_receber_proposta.js",)

    fieldsets = (
        (
            "Origem",
            {
                "description": "Ao selecionar uma proposta aprovada, cliente, descrição e valor são preenchidos automaticamente.",
                "fields": (
                    "proposta",
                    "cliente",
                ),
            },
        ),
        (
            "Financeiro",
            {
                "fields": (
                    "descricao",
                    "valor",
                    "vencimento",
                    "status",
                    "data_recebimento",
                )
            },
        ),
        (
            "Comprovante",
            {
                "fields": ("comprovante",),
            },
        ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "proposta":
            kwargs["queryset"] = Proposta.objects.filter(status="aprovado").order_by("-data_emissao")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "calendario/",
                self.admin_site.admin_view(self.calendario_view),
                name="financeiro_contareceber_calendario",
            ),
            path(
                "proposta/<uuid:proposta_id>/dados/",
                self.admin_site.admin_view(self.proposta_dados),
                name="financeiro_contareceber_proposta_dados",
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

        contas = (
            ContaReceber.objects.filter(
                Q(vencimento__range=(primeiro_dia, ultimo_dia))
                | Q(data_recebimento__range=(primeiro_dia, ultimo_dia))
            )
            .select_related("cliente", "proposta")
            .order_by("vencimento", "cliente__razao_social", "descricao")
        )

        status = request.GET.get("status", "").strip()
        cliente = request.GET.get("cliente", "").strip()

        if status:
            contas = contas.filter(status=status)
        if cliente:
            contas = contas.filter(cliente_id=cliente)

        contas = list(contas)

        cal = calendar.Calendar(firstweekday=6)
        semanas = []
        for semana in cal.monthdatescalendar(ano, mes):
            dias = []
            for dia in semana:
                eventos = []
                for conta in contas:
                    if conta.vencimento == dia:
                        eventos.append(self._evento_calendario(conta, "vencimento"))
                    if conta.data_recebimento == dia:
                        eventos.append(self._evento_calendario(conta, "recebimento"))
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
            Cliente.objects.filter(contas_receber__isnull=False)
            .order_by("codigo", "razao_social")
            .distinct()
        )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Calendario de contas a receber",
            "subtitulo": primeiro_dia.strftime("%B de %Y").capitalize(),
            "semanas": semanas,
            "mes": mes,
            "ano": ano,
            "status_choices": self.model.STATUS_CHOICES,
            "clientes": clientes,
            "filtros": {
                "status": status,
                "cliente": cliente,
            },
            "link_anterior": f"?mes={anterior_mes}&ano={anterior_ano}&status={status}&cliente={cliente}",
            "link_proximo": f"?mes={proximo_mes}&ano={proximo_ano}&status={status}&cliente={cliente}",
            "novo_url": reverse("admin:financeiro_contareceber_add"),
            "lista_url": reverse("admin:financeiro_contareceber_changelist"),
            "legenda_tipos": [
                ("vencimento", "Vencimento"),
                ("recebimento", "Recebimento"),
                ("atrasado", "Atrasado"),
            ],
        }
        return render(request, "admin/financeiro/contareceber/calendar.html", context)

    def _evento_calendario(self, conta, tipo_evento):
        titulo = "Recebimento" if tipo_evento == "recebimento" else "Vencimento"
        status_key = "atrasado" if tipo_evento == "vencimento" and conta.status == "atrasado" else tipo_evento
        return {
            "titulo": titulo,
            "tipo_evento": status_key,
            "descricao": conta.descricao or "-",
            "cliente": str(conta.cliente) if conta.cliente_id else "-",
            "proposta": conta.proposta.codigo if conta.proposta_id else "",
            "status": conta.get_status_display(),
            "valor": conta.valor,
            "tem_comprovante": bool(conta.comprovante),
            "url": reverse("admin:financeiro_contareceber_change", args=[conta.pk]),
        }

    def proposta_dados(self, request, proposta_id):
        proposta = get_object_or_404(
            Proposta.objects.select_related("cliente"),
            pk=proposta_id,
            status="aprovado",
        )

        return JsonResponse(
            {
                "cliente_id": str(proposta.cliente_id),
                "cliente_label": str(proposta.cliente),
                "descricao": f"Proposta {proposta.codigo}",
                "valor": f"{proposta.total:.2f}".replace(".", ","),
            }
        )


class PedidoCompraItemInline(admin.TabularInline):
    model = PedidoCompraItem
    extra = 1
    autocomplete_fields = ("produto",)


@admin.register(PedidoCompra)
class PedidoCompraAdmin(admin.ModelAdmin):
    change_form_template = "admin/financeiro/pedidocompra/change_form.html"
    change_list_template = "admin/financeiro/pedidocompra/change_list.html"

    list_display = (
        "numero_pedido",
        "fornecedor",
        "data_emissao",
        "prazo_entrega",
        "vencimento_pagamento",
        "condicao_pagamento",
        "total",
        "gerar_pdf",
    )
    list_filter = ("data_emissao", "prazo_entrega", "vencimento_pagamento", "fornecedor")
    search_fields = ("numero_pedido", "fornecedor__razao_social", "fornecedor__cnpj", "condicao_pagamento")
    date_hierarchy = "data_emissao"
    autocomplete_fields = ("fornecedor", "responsavel_compra")
    readonly_fields = (
        "numero_pedido",
        "data_emissao",
        "subtotal",
        "desconto",
        "total",
        "conta_pagar_vinculada",
        "comprador_empresa",
        "comprador_cnpj",
        "comprador_endereco",
        "comprador_cidade",
        "comprador_estado",
        "comprador_telefone",
        "comprador_email",
        "fornecedor_razao_social",
        "fornecedor_nome_fantasia",
        "fornecedor_cnpj",
        "fornecedor_ie",
        "fornecedor_contato",
        "fornecedor_telefone",
        "fornecedor_email",
        "fornecedor_endereco",
    )

    fieldsets = (
        (
            "Dados do Comprador",
            {
                "fields": (
                    "comprador_empresa",
                    "comprador_cnpj",
                    "comprador_endereco",
                    "comprador_cidade",
                    "comprador_estado",
                    "comprador_telefone",
                    "comprador_email",
                )
            },
        ),
        (
            "Fornecedor",
            {
                "fields": (
                    "fornecedor",
                    "fornecedor_razao_social",
                    "fornecedor_nome_fantasia",
                    "fornecedor_cnpj",
                    "fornecedor_ie",
                    "fornecedor_contato",
                    "fornecedor_telefone",
                    "fornecedor_email",
                    "fornecedor_endereco",
                )
            },
        ),
        (
            "Dados do Pedido",
            {
                "fields": (
                    "numero_pedido",
                    "data_emissao",
                    "responsavel_compra",
                    "prazo_entrega",
                    "vencimento_pagamento",
                    "condicao_pagamento",
                    "frete",
                    "outros_custos",
                    "observacoes",
                    "anexo",
                    "incluir_nome_anexo_pdf",
                )
            },
        ),
        (
            "Totais",
            {
                "fields": (
                    "subtotal",
                    "desconto",
                    "total",
                    "conta_pagar_vinculada",
                )
            },
        ),
    )

    inlines = [PedidoCompraItemInline]

    class Media:
        js = ("js/pedido_compra.js",)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        response = super().changelist_view(request, extra_context=extra_context)

        if hasattr(response, "context_data") and response.context_data and "cl" in response.context_data:
            changelist = response.context_data["cl"]
            fornecedor_model = self.model._meta.get_field("fornecedor").remote_field.model
            fornecedores_com_pedido = (
                fornecedor_model.objects
                .filter(pedidos_compra__isnull=False)
                .distinct()
                .order_by("razao_social", "nome_empresa")
            )
            response.context_data.update({
                "filtro_fornecedor_atual": request.GET.get("fornecedor__id__exact", ""),
                "fornecedor_choices_rapido": fornecedores_com_pedido,
                "total_filtrado_pedidos_compra": changelist.queryset.aggregate(total=Sum("total"))["total"] or 0,
                "quantidade_filtrada_pedidos_compra": changelist.result_count,
            })

        return response

    def comprador_empresa(self, obj):
        return EMPRESA_COMPRADORA["empresa"]

    comprador_empresa.short_description = "Empresa"

    def conta_pagar_vinculada(self, obj):
        conta = getattr(obj, "conta_pagar_gerada", None)
        if not conta:
            return "-"
        return format_html(
            '<a href="{}">{} | R$ {} | {}</a>',
            reverse("admin:financeiro_contapagar_change", args=[conta.pk]),
            conta.descricao,
            f"{conta.valor:.2f}".replace(".", ","),
            conta.get_status_display(),
        )

    conta_pagar_vinculada.short_description = "Conta a pagar gerada"

    def comprador_cnpj(self, obj):
        return EMPRESA_COMPRADORA["cnpj"]

    comprador_cnpj.short_description = "CNPJ"

    def comprador_endereco(self, obj):
        return EMPRESA_COMPRADORA["endereco"]

    comprador_endereco.short_description = "Endereço"

    def comprador_cidade(self, obj):
        return EMPRESA_COMPRADORA["cidade"]

    comprador_cidade.short_description = "Cidade"

    def comprador_estado(self, obj):
        return EMPRESA_COMPRADORA["estado"]

    comprador_estado.short_description = "Estado"

    def comprador_telefone(self, obj):
        return EMPRESA_COMPRADORA["telefone"]

    comprador_telefone.short_description = "Telefone"

    def comprador_email(self, obj):
        return EMPRESA_COMPRADORA["email"]

    comprador_email.short_description = "E-mail"

    def fornecedor_nome_fantasia(self, obj):
        if not obj.fornecedor_id:
            return "-"
        return getattr(obj.fornecedor, "nome_empresa", "-")

    fornecedor_nome_fantasia.short_description = "Nome fantasia"

    def fornecedor_razao_social(self, obj):
        if not obj.fornecedor_id:
            return "-"
        return getattr(obj.fornecedor, "razao_social", "-")

    fornecedor_razao_social.short_description = "Razão social"

    def fornecedor_cnpj(self, obj):
        if not obj.fornecedor_id:
            return "-"
        return getattr(obj.fornecedor, "cnpj", "-")

    fornecedor_cnpj.short_description = "CNPJ"

    def fornecedor_ie(self, obj):
        if not obj.fornecedor_id:
            return "-"
        return getattr(obj.fornecedor, "ie", "-")

    fornecedor_ie.short_description = "Inscrição estadual"

    def fornecedor_contato(self, obj):
        if not obj.fornecedor_id:
            return "-"
        contato = contato_principal_cliente(obj.fornecedor)
        return contato.nome if contato else "-"

    fornecedor_contato.short_description = "Contato"

    def fornecedor_telefone(self, obj):
        if not obj.fornecedor_id:
            return "-"
        contato = contato_principal_cliente(obj.fornecedor)
        if contato and contato.telefone:
            return contato.telefone
        return getattr(obj.fornecedor, "telefone", "-")

    fornecedor_telefone.short_description = "Telefone"

    def fornecedor_email(self, obj):
        if not obj.fornecedor_id:
            return "-"
        contato = contato_principal_cliente(obj.fornecedor)
        if contato and contato.email:
            return contato.email
        return getattr(obj.fornecedor, "email", "-")

    fornecedor_email.short_description = "E-mail"

    def fornecedor_endereco(self, obj):
        return endereco_cliente(obj.fornecedor) if obj.fornecedor_id else "-"

    fornecedor_endereco.short_description = "Endereço"

    def save_model(self, request, obj, form, change):
        if not obj.responsavel_compra_id:
            obj.responsavel_compra = request.user
        super().save_model(request, obj, form, change)

    def gerar_pdf(self, obj):
        return format_html(
            "<a class='button' href='{}' target='_blank'>Gerar PDF</a>",
            reverse("financeiro:pedido_compra_pdf", args=[obj.id]),
        )

    gerar_pdf.short_description = "PDF"

    def duplicar_pedido(self, request, pk):
        pedido = get_object_or_404(
            PedidoCompra.objects.prefetch_related("itens"),
            pk=pk,
        )
        novo = PedidoCompra.objects.create(
            fornecedor=pedido.fornecedor,
            responsavel_compra=request.user,
            prazo_entrega=pedido.prazo_entrega,
            condicao_pagamento=pedido.condicao_pagamento,
            observacoes=pedido.observacoes,
            anexo=pedido.anexo,
            incluir_nome_anexo_pdf=pedido.incluir_nome_anexo_pdf,
            frete=pedido.frete,
            outros_custos=pedido.outros_custos,
        )

        for item in pedido.itens.all():
            PedidoCompraItem.objects.create(
                pedido=novo,
                produto=item.produto,
                codigo=item.codigo,
                descricao=item.descricao,
                quantidade=item.quantidade,
                unidade=item.unidade,
                valor_unitario=item.valor_unitario,
                desconto=item.desconto,
            )

        return redirect(f"/admin/financeiro/pedidocompra/{novo.pk}/change/")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "pedido-compra/<uuid:pk>/duplicar/",
                self.admin_site.admin_view(self.duplicar_pedido),
                name="financeiro_pedidocompra_duplicar",
            ),
        ]
        return custom_urls + urls


@admin.register(Imposto)
class ImpostoAdmin(admin.ModelAdmin):
    change_list_template = "admin/financeiro/imposto/change_list.html"

    list_display = (
        "nome",
        "competencia",
        "valor",
        "vencimento",
        "pago",
    )
    list_filter = ("pago", "competencia")
    date_hierarchy = "vencimento"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        response = super().changelist_view(request, extra_context=extra_context)

        if hasattr(response, "context_data") and response.context_data and "cl" in response.context_data:
            changelist = response.context_data["cl"]
            response.context_data.update({
                "filtro_pago_atual": request.GET.get("pago__exact", ""),
                "pago_choices_rapido": (("1", "Pago"), ("0", "Pendente")),
                "total_filtrado_impostos": changelist.queryset.aggregate(total=Sum("valor"))["total"] or 0,
                "quantidade_filtrada_impostos": changelist.result_count,
            })

        return response

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "calendario/",
                self.admin_site.admin_view(self.calendario_view),
                name="financeiro_imposto_calendario",
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

        impostos = Imposto.objects.filter(
            Q(vencimento__range=(primeiro_dia, ultimo_dia))
            | Q(data_pagamento__range=(primeiro_dia, ultimo_dia))
        ).order_by("vencimento", "nome", "competencia")

        pago = request.GET.get("pago", "").strip()
        competencia = request.GET.get("competencia", "").strip()

        if pago == "1":
            impostos = impostos.filter(pago=True)
        elif pago == "0":
            impostos = impostos.filter(pago=False)
        if competencia:
            impostos = impostos.filter(competencia=competencia)

        impostos = list(impostos)

        cal = calendar.Calendar(firstweekday=6)
        semanas = []
        for semana in cal.monthdatescalendar(ano, mes):
            dias = []
            for dia in semana:
                eventos = []
                for imposto in impostos:
                    if imposto.vencimento == dia:
                        eventos.append(self._evento_calendario(imposto, "vencimento", hoje))
                    if imposto.data_pagamento == dia:
                        eventos.append(self._evento_calendario(imposto, "pagamento", hoje))
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

        competencias = (
            Imposto.objects.exclude(competencia="")
            .order_by("-competencia")
            .values_list("competencia", flat=True)
            .distinct()
        )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Calendario de impostos",
            "subtitulo": primeiro_dia.strftime("%B de %Y").capitalize(),
            "semanas": semanas,
            "mes": mes,
            "ano": ano,
            "pago_choices": (("1", "Pago"), ("0", "Pendente")),
            "competencias": competencias,
            "filtros": {
                "pago": pago,
                "competencia": competencia,
            },
            "link_anterior": f"?mes={anterior_mes}&ano={anterior_ano}&pago={pago}&competencia={competencia}",
            "link_proximo": f"?mes={proximo_mes}&ano={proximo_ano}&pago={pago}&competencia={competencia}",
            "novo_url": reverse("admin:financeiro_imposto_add"),
            "lista_url": reverse("admin:financeiro_imposto_changelist"),
            "legenda_tipos": [
                ("vencimento", "Vencimento"),
                ("pagamento", "Pagamento"),
                ("atrasado", "Atrasado"),
            ],
        }
        return render(request, "admin/financeiro/imposto/calendar.html", context)

    def _evento_calendario(self, imposto, tipo_evento, hoje):
        titulo = "Pagamento" if tipo_evento == "pagamento" else "Vencimento"
        status_key = (
            "atrasado"
            if tipo_evento == "vencimento" and not imposto.pago and imposto.vencimento < hoje
            else tipo_evento
        )
        return {
            "titulo": titulo,
            "tipo_evento": status_key,
            "nome": imposto.nome,
            "competencia": imposto.competencia,
            "status": "Pago" if imposto.pago else "Pendente",
            "valor": imposto.valor,
            "tem_comprovante": bool(imposto.comprovante),
            "url": reverse("admin:financeiro_imposto_change", args=[imposto.pk]),
        }


class ItemNotaFiscalInline(admin.TabularInline):
    model = ItemNotaFiscal
    extra = 1
    fields = (
        "tipo_item",
        "descricao",
        "codigo_interno",
        "quantidade",
        "unidade",
        "valor_unitario",
        "valor_total",
        "cfop",
        "ncm",
        "codigo_servico",
        "marca",
        "modelo",
        "numero_serie",
        "patrimonio",
        "observacoes",
    )


class AnexoNotaFiscalInline(admin.TabularInline):
    model = AnexoNotaFiscal
    extra = 1
    fields = ("arquivo", "descricao", "criado_em")
    readonly_fields = ("criado_em",)


class GrupoTipoNotaFilter(admin.SimpleListFilter):
    title = "Grupo do documento"
    parameter_name = "grupo_tipo_nota"

    def lookups(self, request, model_admin):
        return (
            ("vendas", "Somente notas de venda"),
            ("servicos", "Somente notas de servico"),
            ("entradas", "Somente notas de entrada"),
            ("devolucoes", "Somente devolucoes"),
            ("remessas", "Somente remessas"),
            ("retornos", "Somente retornos"),
            ("documentos_sem_nf", "Documentos internos sem NF"),
        )

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == "vendas":
            return queryset.filter(tipo_nota__in=["venda_produto", "venda_produto_servico"])
        if valor == "servicos":
            return queryset.filter(tipo_nota="prestacao_servico")
        if valor == "entradas":
            return queryset.filter(tipo_nota__in=["entrada_compra", "entrada_equipamento_cliente"])
        if valor == "devolucoes":
            return queryset.filter(tipo_nota__in=["devolucao_compra", "devolucao_venda"])
        if valor == "remessas":
            return queryset.filter(tipo_nota__in=["remessa_conserto", "remessa_calibracao", "simples_remessa"])
        if valor == "retornos":
            return queryset.filter(tipo_nota__in=["retorno_conserto", "retorno_calibracao", "saida_devolucao_equipamento_cliente"])
        if valor == "documentos_sem_nf":
            return queryset.filter(tipo_nota="documento_interno_sem_nf")
        return queryset


class TemPdfFilter(admin.SimpleListFilter):
    title = "PDF"
    parameter_name = "tem_pdf"

    def lookups(self, request, model_admin):
        return (("nao", "Notas sem PDF"),)

    def queryset(self, request, queryset):
        if self.value() == "nao":
            return queryset.filter(Q(pdf="") | Q(pdf__isnull=True))
        return queryset


class TemXmlFilter(admin.SimpleListFilter):
    title = "XML"
    parameter_name = "tem_xml"

    def lookups(self, request, model_admin):
        return (("nao", "Notas sem XML"),)

    def queryset(self, request, queryset):
        if self.value() == "nao":
            return queryset.filter(Q(xml="") | Q(xml__isnull=True))
        return queryset


class RemessaAbertaFilter(admin.SimpleListFilter):
    title = "Remessas em aberto"
    parameter_name = "remessa_aberta"

    def lookups(self, request, model_admin):
        return (("sim", "Remessas aguardando retorno"),)

    def queryset(self, request, queryset):
        if self.value() == "sim":
            return queryset.filter(
                tipo_nota__in=["remessa_conserto", "remessa_calibracao", "simples_remessa"],
                status_operacional__in=["aguardando_envio", "em_transito", "recebido", "em_analise", "em_manutencao", "em_calibracao", "aguardando_retorno"],
            )
        return queryset


@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    change_list_template = "admin/financeiro/notafiscal/change_list.html"

    list_display = (
        "numero",
        "tipo_nota",
        "cliente",
        "fornecedor_nome",
        "data_emissao",
        "valor_total",
        "status",
        "status_operacional",
        "possui_pdf",
        "possui_xml",
        "atualizado_em",
    )
    list_filter = (
        "tipo_nota",
        GrupoTipoNotaFilter,
        "status",
        "status_operacional",
        "data_emissao",
        "cliente",
        TemPdfFilter,
        TemXmlFilter,
        RemessaAbertaFilter,
    )
    search_fields = (
        "numero",
        "chave_acesso",
        "cliente__razao_social",
        "cliente__nome_empresa",
        "fornecedor_nome",
        "fornecedor_cnpj",
        "observacoes",
    )
    autocomplete_fields = (
        "cliente",
        "proposta",
        "pedido_compra",
        "conta_receber",
        "conta_pagar",
        "calibracao",
        "nota_referenciada",
    )
    readonly_fields = ("criado_em", "atualizado_em")
    inlines = (ItemNotaFiscalInline, AnexoNotaFiscalInline)

    fieldsets = (
        (
            "Identificacao da Nota",
            {
                "fields": (
                    "tipo_nota",
                    "status",
                    "status_operacional",
                    "numero",
                    "serie",
                    "chave_acesso",
                    "natureza_operacao",
                )
            },
        ),
        (
            "Cliente / Fornecedor",
            {
                "fields": (
                    "cliente",
                    "fornecedor_nome",
                    "fornecedor_cnpj",
                )
            },
        ),
        (
            "Datas e Valores",
            {
                "fields": (
                    "data_emissao",
                    "data_entrada_saida",
                    "data_vencimento",
                    "valor_total",
                )
            },
        ),
        (
            "Dados Fiscais",
            {
                "fields": (
                    "cfop",
                    "codigo_servico",
                    "municipio_emissao",
                )
            },
        ),
        (
            "Arquivos",
            {
                "fields": (
                    "pdf",
                    "xml",
                )
            },
        ),
        (
            "Vinculos no Axion",
            {
                "fields": (
                    "proposta",
                    "pedido_compra",
                    "conta_receber",
                    "conta_pagar",
                    "calibracao",
                    "nota_referenciada",
                )
            },
        ),
        (
            "Motivo e Observacoes",
            {
                "fields": (
                    "motivo",
                    "observacoes",
                )
            },
        ),
        (
            "Controle Interno",
            {
                "fields": (
                    "criado_por",
                    "criado_em",
                    "atualizado_em",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not obj.criado_por_id:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "calendario/",
                self.admin_site.admin_view(self.calendario_view),
                name="financeiro_notafiscal_calendario",
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

        notas = (
            NotaFiscal.objects.filter(
                Q(data_emissao__range=(primeiro_dia, ultimo_dia))
                | Q(data_entrada_saida__range=(primeiro_dia, ultimo_dia))
                | Q(data_vencimento__range=(primeiro_dia, ultimo_dia))
            )
            .select_related("cliente")
            .order_by("data_emissao", "numero", "cliente__razao_social")
        )

        status = request.GET.get("status", "").strip()
        tipo = request.GET.get("tipo", "").strip()
        operacional = request.GET.get("operacional", "").strip()
        cliente = request.GET.get("cliente", "").strip()

        if status:
            notas = notas.filter(status=status)
        if tipo:
            notas = notas.filter(tipo_nota=tipo)
        if operacional:
            notas = notas.filter(status_operacional=operacional)
        if cliente:
            notas = notas.filter(cliente_id=cliente)

        notas = list(notas)

        cal = calendar.Calendar(firstweekday=6)
        semanas = []
        for semana in cal.monthdatescalendar(ano, mes):
            dias = []
            for dia in semana:
                eventos = []
                for nota in notas:
                    if nota.data_emissao == dia:
                        eventos.append(self._evento_calendario(nota, "emissao"))
                    if nota.data_entrada_saida == dia:
                        eventos.append(self._evento_calendario(nota, "entrada_saida"))
                    if nota.data_vencimento == dia:
                        eventos.append(self._evento_calendario(nota, "vencimento"))
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

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Calendario de notas fiscais",
            "subtitulo": primeiro_dia.strftime("%B de %Y").capitalize(),
            "semanas": semanas,
            "mes": mes,
            "ano": ano,
            "status_choices": self.model.STATUS_CHOICES,
            "tipo_choices": self.model.TIPO_NOTA_CHOICES,
            "operacional_choices": self.model.STATUS_OPERACIONAL_CHOICES,
            "clientes": Cliente.objects.filter(notas_fiscais__isnull=False).distinct().order_by("razao_social"),
            "filtros": {
                "status": status,
                "tipo": tipo,
                "operacional": operacional,
                "cliente": cliente,
            },
            "link_anterior": f"?mes={anterior_mes}&ano={anterior_ano}&status={status}&tipo={tipo}&operacional={operacional}&cliente={cliente}",
            "link_proximo": f"?mes={proximo_mes}&ano={proximo_ano}&status={status}&tipo={tipo}&operacional={operacional}&cliente={cliente}",
            "novo_url": reverse("admin:financeiro_notafiscal_add"),
            "lista_url": reverse("admin:financeiro_notafiscal_changelist"),
            "legenda_tipos": [
                ("emissao", "Data de emissao"),
                ("entrada_saida", "Entrada / saida"),
                ("vencimento", "Vencimento"),
            ],
        }
        return render(request, "admin/financeiro/notafiscal/calendar.html", context)

    def _evento_calendario(self, nota, tipo_evento):
        titulos = {
            "emissao": "Emissao",
            "entrada_saida": "Entrada / saida",
            "vencimento": "Vencimento",
        }
        referencia = nota.cliente.razao_social if nota.cliente_id else (nota.fornecedor_nome or "Sem vinculo")
        return {
            "titulo": titulos.get(tipo_evento, "Nota fiscal"),
            "tipo_evento": tipo_evento,
            "referencia": referencia,
            "numero": nota.numero or "S/N",
            "tipo_nota": nota.get_tipo_nota_display(),
            "status": nota.get_status_display(),
            "status_operacional": nota.get_status_operacional_display(),
            "valor": nota.valor_total,
            "tem_pdf": nota.tem_pdf,
            "tem_xml": nota.tem_xml,
            "url": reverse("admin:financeiro_notafiscal_change", args=[nota.pk]),
        }

    def possui_pdf(self, obj):
        return "Sim" if obj.tem_pdf else "Nao"

    possui_pdf.short_description = "PDF"

    def possui_xml(self, obj):
        return "Sim" if obj.tem_xml else "Nao"

    possui_xml.short_description = "XML"
