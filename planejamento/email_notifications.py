import hashlib
import json
from datetime import datetime, timedelta, timezone as datetime_timezone

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .models import PlanejamentoServico


STATUS_NOTIFICAVEIS = {"agendado", "confirmado"}


def _dados_hash(planejamento):
    return {
        "codigo": planejamento.codigo,
        "titulo": planejamento.titulo,
        "tipo": planejamento.tipo_agendamento,
        "status": planejamento.status,
        "cliente": str(planejamento.cliente_id),
        "contato": str(planejamento.contato_id or ""),
        "email": planejamento.email_contato.strip().lower(),
        "data_inicio": planejamento.data_inicio.isoformat(),
        "data_fim": planejamento.data_fim.isoformat() if planejamento.data_fim else "",
        "hora_inicio": planejamento.hora_inicio.isoformat() if planejamento.hora_inicio else "",
        "hora_fim": planejamento.hora_fim.isoformat() if planejamento.hora_fim else "",
        "dia_inteiro": planejamento.dia_inteiro,
        "local": planejamento.local_servico,
        "tecnicos": list(planejamento.tecnicos.order_by("pk").values_list("pk", flat=True)),
        "instrumentos": list(planejamento.instrumentos.order_by("pk").values_list("pk", flat=True)),
        "observacoes": planejamento.observacoes,
    }


def calcular_hash_agendamento(planejamento):
    conteudo = json.dumps(_dados_hash(planejamento), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()


def _escapar_ics(valor):
    return (
        str(valor or "")
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _datetime_utc(valor):
    if timezone.is_naive(valor):
        valor = timezone.make_aware(valor, timezone.get_current_timezone())
    return valor.astimezone(datetime_timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def gerar_convite_ics(planejamento, destinatario):
    data_fim = planejamento.data_fim or planejamento.data_inicio
    linhas_data = []
    if planejamento.dia_inteiro or not planejamento.hora_inicio:
        linhas_data.extend(
            [
                f"DTSTART;VALUE=DATE:{planejamento.data_inicio:%Y%m%d}",
                f"DTEND;VALUE=DATE:{(data_fim + timedelta(days=1)):%Y%m%d}",
            ]
        )
    else:
        inicio = datetime.combine(planejamento.data_inicio, planejamento.hora_inicio)
        fim = (
            datetime.combine(data_fim, planejamento.hora_fim)
            if planejamento.hora_fim
            else inicio + timedelta(hours=1)
        )
        linhas_data.extend(
            [
                f"DTSTART:{_datetime_utc(inicio)}",
                f"DTEND:{_datetime_utc(fim)}",
            ]
        )

    descricao = planejamento.observacoes or "Agendamento de serviço da DS Científica."

    linhas = [
        "BEGIN:VCALENDAR",
        "PRODID:-//DS Cientifica//AXION Agenda//PT-BR",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{planejamento.pk}@dscientifica.com.br",
        f"DTSTAMP:{timezone.now().astimezone(datetime_timezone.utc):%Y%m%dT%H%M%SZ}",
        *linhas_data,
        f"SEQUENCE:{planejamento.email_agendamento_sequencia + 1}",
        f"SUMMARY:{_escapar_ics(planejamento.titulo)}",
        f"DESCRIPTION:{_escapar_ics(descricao)}",
        f"LOCATION:{_escapar_ics(planejamento.local_servico or 'A combinar')}",
        f"ORGANIZER;CN=DS Cientifica:mailto:{settings.DEFAULT_FROM_EMAIL}",
        f"ATTENDEE;CN={_escapar_ics(planejamento.nome_responsavel_cliente() or destinatario)};RSVP=TRUE:mailto:{destinatario}",
        "STATUS:CONFIRMED" if planejamento.status == "confirmado" else "STATUS:TENTATIVE",
    ]
    linhas.extend(["END:VEVENT", "END:VCALENDAR", ""])
    return "\r\n".join(linhas)


def enviar_email_agendamento(planejamento, *, forcar=False):
    if not planejamento.notificar_cliente_email:
        return "desativado"
    if planejamento.status not in STATUS_NOTIFICAVEIS:
        return "status_ignorado"

    destinatario = (planejamento.email_contato or "").strip()
    if not destinatario:
        PlanejamentoServico.objects.filter(pk=planejamento.pk).update(
            email_agendamento_erro="O contato selecionado não possui e-mail informado.",
        )
        return "sem_destinatario"

    hash_atual = calcular_hash_agendamento(planejamento)
    if not forcar and planejamento.email_agendamento_hash == hash_atual:
        return "duplicado"

    contexto = {
        "planejamento": planejamento,
        "contato_nome": planejamento.nome_responsavel_cliente(),
        "tecnicos": planejamento.nomes_tecnicos(),
        "instrumentos": list(planejamento.instrumentos.all()),
    }
    assunto = f"Agendamento DS Científica - {planejamento.codigo}"
    texto = render_to_string("planejamento/email/agendamento.txt", contexto)
    html = render_to_string("planejamento/email/agendamento.html", contexto)

    try:
        mensagem = EmailMultiAlternatives(
            subject=assunto,
            body=texto,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[destinatario],
        )
        mensagem.attach_alternative(html, "text/html")
        convite_ics = gerar_convite_ics(planejamento, destinatario)
        mensagem.attach(
            f"agendamento-{planejamento.codigo.replace('/', '-')}.ics",
            convite_ics,
            "text/calendar; method=REQUEST; charset=UTF-8",
        )
        mensagem.send(fail_silently=False)
    except Exception as exc:
        PlanejamentoServico.objects.filter(pk=planejamento.pk).update(
            email_agendamento_erro=f"{type(exc).__name__}: {exc}"[:1000],
        )
        return "falha"

    PlanejamentoServico.objects.filter(pk=planejamento.pk).update(
        email_agendamento_enviado_em=timezone.now(),
        email_agendamento_destinatario=destinatario,
        email_agendamento_hash=hash_atual,
        email_agendamento_erro="",
        email_agendamento_sequencia=planejamento.email_agendamento_sequencia + 1,
    )
    return "enviado"


def enviar_email_agendamento_por_id(planejamento_id, *, forcar=False):
    planejamento = (
        PlanejamentoServico.objects.select_related("cliente", "contato")
        .prefetch_related("tecnicos", "instrumentos")
        .filter(pk=planejamento_id)
        .first()
    )
    if not planejamento:
        return "nao_encontrado"
    return enviar_email_agendamento(planejamento, forcar=forcar)
