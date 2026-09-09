from django.core.exceptions import ValidationError
from django.db.models import Case, IntegerField, Value, When

from calibracao.models import Instrumento, OrdemServico


STATUS_PRIORIDADE = Case(
    When(status="em_andamento", then=Value(0)),
    When(status="aberta", then=Value(1)),
    When(status="concluida", then=Value(2)),
    default=Value(3),
    output_field=IntegerField(),
)


def buscar_ordem_servico_do_instrumento(instrumento_id, cliente_id=None):
    """Retorna a OS mais adequada explicitamente vinculada ao instrumento."""
    if not instrumento_id:
        return None

    if not cliente_id:
        try:
            cliente_id = (
                Instrumento.objects.filter(pk=instrumento_id)
                .values_list("cliente_id", flat=True)
                .first()
            )
        except (ValidationError, TypeError, ValueError):
            return None
    if not cliente_id:
        return None

    try:
        ordens = (
            OrdemServico.objects.filter(
                instrumentos__pk=instrumento_id,
                cliente_id=cliente_id,
            )
            .exclude(status="cancelada")
            .annotate(_status_prioridade=STATUS_PRIORIDADE)
        )
    except (ValidationError, TypeError, ValueError):
        return None

    return ordens.order_by(
        "_status_prioridade",
        "-data_abertura",
        "-numero",
    ).first()


def preencher_ordem_servico_da_calibracao(
    calibracao=None,
    *,
    sender=None,
    instance=None,
    **kwargs,
):
    """Preenche uma OS vazia sem substituir um valor informado manualmente."""
    calibracao = instance or calibracao
    if calibracao is None:
        return None
    if not hasattr(calibracao, "ordem_servico"):
        return None
    if (calibracao.ordem_servico or "").strip():
        return None

    ordem = buscar_ordem_servico_do_instrumento(
        getattr(calibracao, "instrumento_id", None),
        getattr(calibracao, "cliente_id", None),
    )
    if ordem:
        calibracao.ordem_servico = ordem.numero
    return ordem
