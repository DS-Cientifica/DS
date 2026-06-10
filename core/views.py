from datetime import timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from calibracao.models import Calibracao, Instrumento, OrdemServico, Padrao
from clientes.models import Cliente
from comercial.models import CRMRegistro, CRMTicket, ProdutoServico, Proposta
from financeiro.models import ContaPagar, ContaReceber, Imposto
from planejamento.models import PlanejamentoServico
from qualidade.models import Documento


PERIODOS = (
    ("hoje", "Hoje"),
    ("30d", "30 dias"),
    ("mes", "Mês"),
    ("ano", "Ano"),
    ("tudo", "Tudo"),
)

MESES = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")


def _money(value):
    value = value or Decimal("0")
    formatted = f"{value:,.2f}"
    return f"R$ {formatted}".replace(",", "X").replace(".", ",").replace("X", ".")


def _periodo_bounds(periodo, today):
    if periodo == "hoje":
        return today, today, "Hoje"

    if periodo == "mes":
        start = today.replace(day=1)
        end = start + relativedelta(months=1, days=-1)
        return start, end, "Mês atual"

    if periodo == "ano":
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
        return start, end, "Ano atual"

    if periodo == "tudo":
        return None, today, "Todo o histórico"

    end = today + timedelta(days=30)
    return today, end, "Próximos 30 dias"


def _filtrar_periodo(queryset, field_name, start, end):
    if not start:
        return queryset

    return queryset.filter(
        **{
            f"{field_name}__gte": start,
            f"{field_name}__lte": end,
        }
    )


def _percentual_rows(rows, value_key="total"):
    max_value = max((row[value_key] for row in rows), default=0) or 1

    for row in rows:
        row["percentual"] = f"{((row[value_key] / max_value) * 100):.1f}"

    return rows


def _financeiro_mensal(today):
    start_month = today.replace(day=1) - relativedelta(months=5)
    rows = []

    for index in range(6):
        month_start = start_month + relativedelta(months=index)
        next_month = month_start + relativedelta(months=1)

        receber = (
            ContaReceber.objects.exclude(status="cancelado")
            .filter(vencimento__gte=month_start, vencimento__lt=next_month)
            .aggregate(total=Sum("valor"))["total"]
            or Decimal("0")
        )
        pagar = (
            ContaPagar.objects.exclude(status="cancelado")
            .filter(vencimento__gte=month_start, vencimento__lt=next_month)
            .aggregate(total=Sum("valor"))["total"]
            or Decimal("0")
        )

        rows.append(
            {
                "label": f"{MESES[month_start.month - 1]}/{month_start:%y}",
                "receber": receber,
                "pagar": pagar,
                "receber_formatado": _money(receber),
                "pagar_formatado": _money(pagar),
            }
        )

    max_value = max(
        [value for row in rows for value in (row["receber"], row["pagar"])],
        default=Decimal("0"),
    ) or Decimal("1")

    for row in rows:
        row["receber_percentual"] = f"{float((row['receber'] / max_value) * 100):.1f}"
        row["pagar_percentual"] = f"{float((row['pagar'] / max_value) * 100):.1f}"

    return rows


def _qualidade_documental(today):
    documentos = list(Documento.objects.all().order_by("titulo"))
    limite_30 = today + timedelta(days=30)
    limite_revisao = today - relativedelta(months=12)
    limite_30_revisao = today - relativedelta(months=11)

    vigentes = [doc for doc in documentos if doc.status == "vigente"]
    obsoletos = [doc for doc in documentos if doc.status == "obsoleto"]
    em_revisao = [doc for doc in documentos if doc.status == "em_revisao"]
    elaboracao = [doc for doc in documentos if doc.status == "em_elaboracao"]
    sem_codigo = [doc for doc in documentos if not doc.codigo.strip()]
    sem_aprovacao = [doc for doc in documentos if not doc.aprovado_por.strip() or doc.status == "em_elaboracao"]
    sem_responsavel = [doc for doc in documentos if not doc.responsavel.strip()]
    sem_historico = [doc for doc in documentos if not doc.historico_revisoes.exists()]
    vencendo = [doc for doc in vigentes if limite_revisao <= doc.data_ultima_revisao <= limite_30_revisao]
    vencidos = [doc for doc in vigentes if doc.data_proxima_revisao < today]
    proxima_revisao = [doc for doc in vigentes if today <= doc.data_proxima_revisao <= limite_30]

    return {
        "documentos": documentos,
        "vigentes": vigentes,
        "obsoletos": obsoletos,
        "em_revisao": em_revisao,
        "elaboracao": elaboracao,
        "sem_codigo": sem_codigo,
        "sem_aprovacao": sem_aprovacao,
        "sem_responsavel": sem_responsavel,
        "sem_historico": sem_historico,
        "vencendo": vencendo,
        "vencidos": vencidos,
        "proxima_revisao": proxima_revisao,
    }


@login_required(login_url="/admin/login/")
def dashboard(request):
    today = timezone.localdate()
    next_7_days = today + timedelta(days=7)
    next_30_days = today + timedelta(days=30)

    periodo_atual = request.GET.get("periodo", "tudo")
    if periodo_atual not in dict(PERIODOS):
        periodo_atual = "tudo"

    period_start, period_end, periodo_label = _periodo_bounds(periodo_atual, today)
    periodos = [
        {
            "key": key,
            "label": label,
            "url": f"?periodo={key}",
            "ativo": key == periodo_atual,
        }
        for key, label in PERIODOS
    ]

    contas_receber_abertas_base = ContaReceber.objects.filter(status__in=("pendente", "atrasado"))
    contas_pagar_abertas_base = ContaPagar.objects.filter(status__in=("pendente", "atrasado"))
    propostas_ativas_base = Proposta.objects.filter(status__in=("rascunho", "enviado", "pendente"))

    contas_receber_abertas = _filtrar_periodo(
        contas_receber_abertas_base,
        "vencimento",
        period_start,
        period_end,
    )
    contas_pagar_abertas = _filtrar_periodo(
        contas_pagar_abertas_base,
        "vencimento",
        period_start,
        period_end,
    )
    propostas_ativas = _filtrar_periodo(
        propostas_ativas_base,
        "data_emissao",
        period_start,
        period_end,
    )

    oportunidades_abertas = CRMRegistro.objects.exclude(etapa_funil="fechado")
    tickets_abertos = CRMTicket.objects.exclude(status__in=("resolvido", "fechado"))

    receita_aberta = contas_receber_abertas.aggregate(total=Sum("valor"))["total"] or Decimal("0")
    despesa_aberta = contas_pagar_abertas.aggregate(total=Sum("valor"))["total"] or Decimal("0")
    propostas_em_aberto = propostas_ativas.aggregate(total=Sum("total"))["total"] or Decimal("0")
    saldo_previsto = receita_aberta - despesa_aberta

    receber_atrasadas = contas_receber_abertas_base.filter(Q(status="atrasado") | Q(vencimento__lt=today))
    pagar_atrasadas = contas_pagar_abertas_base.filter(Q(status="atrasado") | Q(vencimento__lt=today))
    calibracoes_vencidas = Instrumento.objects.filter(
        ativo=True,
        proxima_calibracao__isnull=False,
        proxima_calibracao__lt=today,
    )
    calibracoes_7_dias = Instrumento.objects.filter(
        ativo=True,
        proxima_calibracao__gte=today,
        proxima_calibracao__lte=next_7_days,
    )
    padroes_vencidos = Padrao.objects.filter(Q(vencimento__lt=today) | Q(status="vencido")).distinct()
    padroes_7_dias = Padrao.objects.filter(vencimento__gte=today, vencimento__lte=next_7_days)
    impostos_vencidos = Imposto.objects.filter(pago=False, vencimento__lt=today)
    tickets_urgentes = tickets_abertos.filter(prioridade="urgente")
    planejamentos_periodo = PlanejamentoServico.objects.filter(
        data_inicio__gte=today,
        data_inicio__lte=next_30_days,
    ).prefetch_related("padroes")
    planejamentos_alerta = [item for item in planejamentos_periodo if item.possui_alerta_padroes()]
    qualidade = _qualidade_documental(today)

    alertas_possiveis = [
        {
            "titulo": "Calibrações vencidas",
            "texto": "Instrumentos precisam de ação metrológica.",
            "total": calibracoes_vencidas.count(),
            "url": reverse("admin:calibracao_instrumento_changelist"),
            "tipo": "danger",
            "icone": "CA",
        },
        {
            "titulo": "Padrões vencidos",
            "texto": "Certificados fora do prazo de validade.",
            "total": padroes_vencidos.count(),
            "url": reverse("admin:calibracao_padrao_changelist"),
            "tipo": "danger",
            "icone": "PD",
        },
        {
            "titulo": "Contas atrasadas",
            "texto": "Receber ou pagar com vencimento ultrapassado.",
            "total": receber_atrasadas.count() + pagar_atrasadas.count(),
            "url": reverse("admin:financeiro_contareceber_changelist"),
            "tipo": "danger",
            "icone": "R$",
        },
        {
            "titulo": "Impostos vencidos",
            "texto": "Obrigações fiscais pendentes.",
            "total": impostos_vencidos.count(),
            "url": reverse("admin:financeiro_imposto_changelist"),
            "tipo": "danger",
            "icone": "%",
        },
        {
            "titulo": "Próximos 7 dias",
            "texto": "Calibrações ou padrões chegando no prazo.",
            "total": calibracoes_7_dias.count() + padroes_7_dias.count(),
            "url": reverse("admin:calibracao_instrumento_changelist"),
            "tipo": "warn",
            "icone": "7D",
        },
        {
            "titulo": "Docs vencendo",
            "texto": "Documentos com revisão chegando em 30 dias.",
            "total": len(qualidade["proxima_revisao"]),
            "url": reverse("admin:qualidade_documento_changelist"),
            "tipo": "warn",
            "icone": "QD",
        },
        {
            "titulo": "Docs vencidos",
            "texto": "Documentos que precisam ser revistos.",
            "total": len(qualidade["vencidos"]),
            "url": reverse("admin:qualidade_documento_changelist"),
            "tipo": "danger",
            "icone": "QV",
        },
        {
            "titulo": "Tickets urgentes",
            "texto": "Atendimentos críticos em aberto.",
            "total": tickets_urgentes.count(),
            "url": reverse("admin:comercial_crmticket_changelist"),
            "tipo": "warn",
            "icone": "TK",
        },
        {
            "titulo": "Planejamentos com alerta",
            "texto": "Servicos com padrao faltando ou vencido.",
            "total": len(planejamentos_alerta),
            "url": reverse("admin:planejamento_planejamentoservico_calendario"),
            "tipo": "warn",
            "icone": "PL",
        },
    ]
    alertas = [alerta for alerta in alertas_possiveis if alerta["total"] > 0]

    indicadores = [
        {
            "titulo": "Clientes ativos",
            "valor": Cliente.objects.filter(ativo=True).count(),
            "detalhe": f"{Cliente.objects.count()} cadastrados",
            "url": reverse("admin:clientes_cliente_changelist"),
            "tom": "teal",
            "icone": "CL",
        },
        {
            "titulo": "Instrumentos ativos",
            "valor": Instrumento.objects.filter(ativo=True).count(),
            "detalhe": f"{Instrumento.objects.filter(status='manutencao').count()} em manutenção",
            "url": reverse("admin:calibracao_instrumento_changelist"),
            "tom": "blue",
            "icone": "IN",
        },
        {
            "titulo": "Calibrações abertas",
            "valor": Calibracao.objects.filter(status="aberta").count(),
            "detalhe": f"{Instrumento.objects.filter(proxima_calibracao__lte=next_30_days, proxima_calibracao__gte=today).count()} vencem em 30 dias",
            "url": reverse("admin:calibracao_calibracao_changelist"),
            "tom": "amber",
            "icone": "CA",
        },
        {
            "titulo": "Propostas ativas",
            "valor": propostas_ativas.count(),
            "detalhe": _money(propostas_em_aberto),
            "url": reverse("admin:comercial_proposta_changelist"),
            "tom": "green",
            "icone": "PR",
        },
        {
            "titulo": "Documentos vigentes",
            "valor": len(qualidade["vigentes"]),
            "detalhe": f"{len(qualidade['obsoletos'])} obsoletos",
            "url": reverse("admin:qualidade_documento_changelist"),
            "tom": "teal",
            "icone": "QD",
        },
        {
            "titulo": "Receber no período",
            "valor": _money(receita_aberta),
            "detalhe": f"{receber_atrasadas.count()} atrasadas no total",
            "url": reverse("admin:financeiro_contareceber_changelist"),
            "tom": "indigo",
            "icone": "RC",
        },
        {
            "titulo": "Pagar no período",
            "valor": _money(despesa_aberta),
            "detalhe": f"{pagar_atrasadas.count()} atrasadas no total",
            "url": reverse("admin:financeiro_contapagar_changelist"),
            "tom": "red",
            "icone": "PG",
        },
    ]

    propostas_periodo = _filtrar_periodo(
        Proposta.objects.all(),
        "data_emissao",
        period_start,
        period_end,
    )
    status_propostas_count = dict(
        propostas_periodo.values_list("status").annotate(total=Count("id"))
    )
    funil_count = dict(
        CRMRegistro.objects.values_list("etapa_funil").annotate(total=Count("id"))
    )

    status_propostas = _percentual_rows(
        [
            {
                "rotulo": label,
                "total": status_propostas_count.get(value, 0),
                "url": f"{reverse('admin:comercial_proposta_changelist')}?status__exact={value}",
            }
            for value, label in Proposta.STATUS_CHOICES
        ]
    )
    funil = _percentual_rows(
        [
            {
                "rotulo": label,
                "total": funil_count.get(value, 0),
                "url": f"{reverse('admin:comercial_crmregistro_changelist')}?etapa_funil__exact={value}",
            }
            for value, label in CRMRegistro.ETAPA_CHOICES
        ]
    )

    context = {
        "hoje": today,
        "periodo_atual": periodo_atual,
        "periodo_label": periodo_label,
        "periodo_inicio": period_start,
        "periodo_fim": period_end,
        "periodos": periodos,
        "saldo_previsto": _money(saldo_previsto),
        "receita_aberta": _money(receita_aberta),
        "despesa_aberta": _money(despesa_aberta),
        "indicadores": indicadores,
        "alertas": alertas,
        "status_propostas": status_propostas,
        "funil": funil,
        "financeiro_mensal": _financeiro_mensal(today),
        "atalhos": [
            {"rotulo": "Nova proposta", "url": reverse("admin:comercial_proposta_add"), "icone": "PR"},
            {"rotulo": "Novo cliente", "url": reverse("admin:clientes_cliente_add"), "icone": "CL"},
            {"rotulo": "Novo instrumento", "url": reverse("admin:calibracao_instrumento_add"), "icone": "IN"},
            {"rotulo": "Conta a receber", "url": reverse("admin:financeiro_contareceber_add"), "icone": "RC"},
            {"rotulo": "Conta a pagar", "url": reverse("admin:financeiro_contapagar_add"), "icone": "PG"},
            {"rotulo": "Planejamento", "url": reverse("admin:planejamento_planejamentoservico_calendario"), "icone": "PL"},
            {"rotulo": "Documento", "url": reverse("admin:qualidade_documento_add"), "icone": "DOC"},
            {"rotulo": "Gestão documental", "url": "#qualidade-section", "icone": "QD"},
        ],
        "proximas_calibracoes": Instrumento.objects.filter(
            ativo=True,
            proxima_calibracao__isnull=False,
            proxima_calibracao__lte=next_30_days,
        ).select_related("cliente").order_by("proxima_calibracao")[:6],
        "padroes_vencendo": Padrao.objects.filter(
            vencimento__lte=next_30_days,
        ).order_by("vencimento")[:6],
        "propostas_recentes": Proposta.objects.select_related("cliente").order_by("-data_emissao")[:6],
        "tickets_prioridade": tickets_abertos.filter(
            prioridade__in=("urgente", "alta")
        ).select_related("cliente").order_by("prazo_resposta", "-data_abertura")[:6],
        "contas_receber_atrasadas": receber_atrasadas.select_related("cliente").order_by("vencimento")[:5],
        "contas_pagar_atrasadas": pagar_atrasadas.order_by("vencimento")[:5],
        "qualidade": qualidade,
        "resumo_operacional": {
            "ordens_servico": OrdemServico.objects.count(),
            "produtos_servicos": ProdutoServico.objects.filter(ativo=True).count(),
            "documentos": Documento.objects.count(),
            "impostos_abertos": Imposto.objects.filter(pago=False).count(),
            "oportunidades": oportunidades_abertas.count(),
            "tickets": tickets_abertos.count(),
            "planejamentos": PlanejamentoServico.objects.count(),
        },
        "admin_url": reverse("admin:index"),
        "refresh_url": f"{reverse('dashboard')}?periodo={periodo_atual}",
    }

    return render(request, "dashboard.html", context)
