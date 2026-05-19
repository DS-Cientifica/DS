from django.db.models import Sum
from django.utils import timezone
from .models import ContaPagar, ContaReceber, Imposto


def resumo_financeiro():
    hoje = timezone.now().date()
    mes = hoje.month
    ano = hoje.year

    total_pagar = (
        ContaPagar.objects
        .filter(status__in=["pendente", "atrasado"])
        .aggregate(total=Sum("valor"))["total"] or 0
    )

    total_receber = (
        ContaReceber.objects
        .filter(status__in=["pendente", "atrasado"])
        .aggregate(total=Sum("valor"))["total"] or 0
    )

    total_impostos = (
        Imposto.objects
        .filter(pago=False)
        .aggregate(total=Sum("valor"))["total"] or 0
    )

    pagar_mes = (
        ContaPagar.objects
        .filter(vencimento__month=mes, vencimento__year=ano)
        .aggregate(total=Sum("valor"))["total"] or 0
    )

    receber_mes = (
        ContaReceber.objects
        .filter(vencimento__month=mes, vencimento__year=ano)
        .aggregate(total=Sum("valor"))["total"] or 0
    )

    saldo_previsto = total_receber - total_pagar - total_impostos

    return {
        "total_pagar": total_pagar,
        "total_receber": total_receber,
        "total_impostos": total_impostos,
        "saldo_previsto": saldo_previsto,
        "pagar_mes": pagar_mes,
        "receber_mes": receber_mes,
    }
