import json
import mimetypes
from email.mime.image import MIMEImage
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from clientes.models import ContatoCliente
from comercial.models import Prospecto

from .models import CampanhaMarketing, EnvioCampanha


class CampanhaMarketingInvalida(ValueError):
    pass


def _contatos_da_campanha(campanha):
    contatos = ContatoCliente.objects.select_related("cliente")
    if campanha.enviar_todos_contatos_autorizados:
        return contatos.filter(cliente__ativo=True)
    return contatos.filter(pk__in=campanha.destinatarios.values("pk"), cliente__ativo=True)


def _prospectos_da_campanha(campanha):
    prospectos = Prospecto.objects.filter(status__in=("disponivel", "em_prospeccao"))
    if campanha.enviar_todos_prospectos_email_autorizados:
        return (
            prospectos.filter(
                marketing_email_autorizado=True,
                marketing_autorizado_em__isnull=False,
                marketing_revogado_em__isnull=True,
            )
            .exclude(email="")
            .exclude(marketing_base_legal="")
            .exclude(marketing_origem="")
        )
    return prospectos.filter(pk__in=campanha.destinatarios_prospectos.values("pk"))


def preparar_envios_campanha(campanha_id):
    campanha = CampanhaMarketing.objects.prefetch_related(
        "destinatarios",
        "destinatarios_prospectos",
    ).get(pk=campanha_id)
    campanha.full_clean(exclude=("destinatarios",))

    if not campanha.autorizar_disparo:
        return {"criados": 0, "existentes": 0, "ignorados": 0}

    contatos = list(_contatos_da_campanha(campanha))
    prospectos = list(_prospectos_da_campanha(campanha)) if campanha.enviar_email else []
    if not contatos and not prospectos:
        raise CampanhaMarketingInvalida("Nenhum contato destinatário foi selecionado.")

    canais = []
    if campanha.enviar_email:
        canais.append("email")
    if campanha.enviar_whatsapp:
        canais.append("whatsapp")

    agendado_para = campanha.agendado_para or timezone.now()
    resultado = {"criados": 0, "existentes": 0, "ignorados": 0}
    destinos_ativos = set(
        EnvioCampanha.objects.filter(campanha=campanha)
        .exclude(status="cancelado")
        .values_list("canal", "destinatario_endereco")
    )

    for contato in contatos:
        for canal in canais:
            envio_existente = EnvioCampanha.objects.filter(
                campanha=campanha,
                contato=contato,
                canal=canal,
            ).first()
            if envio_existente:
                resultado["existentes"] += 1
                if envio_existente.status != "cancelado":
                    destinos_ativos.add((canal, envio_existente.destinatario_endereco))
                continue
            if not contato.marketing_autorizado(canal):
                resultado["ignorados"] += 1
                continue

            try:
                endereco = (
                    contato.email.strip().lower()
                    if canal == "email"
                    else _normalizar_whatsapp(contato.telefone)
                )
            except CampanhaMarketingInvalida:
                resultado["ignorados"] += 1
                continue
            if (canal, endereco) in destinos_ativos:
                resultado["ignorados"] += 1
                continue
            _, criado = EnvioCampanha.objects.get_or_create(
                campanha=campanha,
                contato=contato,
                canal=canal,
                defaults={
                    "cliente": contato.cliente,
                    "destinatario_nome": contato.nome,
                    "destinatario_endereco": endereco,
                    "assunto_snapshot": campanha.assunto_email if canal == "email" else "",
                    "conteudo_snapshot": (
                        campanha.conteudo_email if canal == "email" else campanha.mensagem_whatsapp_referencia
                    ),
                    "template_snapshot": campanha.whatsapp_template_nome if canal == "whatsapp" else "",
                    "idioma_template_snapshot": (
                        campanha.whatsapp_template_idioma if canal == "whatsapp" else ""
                    ),
                    "agendado_para": agendado_para,
                },
            )
            resultado["criados" if criado else "existentes"] += 1
            if criado:
                destinos_ativos.add((canal, endereco))

    for prospecto in prospectos:
        envio_existente = EnvioCampanha.objects.filter(
            campanha=campanha,
            prospecto=prospecto,
            canal="email",
        ).first()
        if envio_existente:
            resultado["existentes"] += 1
            if envio_existente.status != "cancelado":
                destinos_ativos.add(("email", envio_existente.destinatario_endereco))
            continue
        if not prospecto.marketing_email_permitido():
            resultado["ignorados"] += 1
            continue

        endereco = prospecto.email.strip().lower()
        if ("email", endereco) in destinos_ativos:
            resultado["ignorados"] += 1
            continue
        _, criado = EnvioCampanha.objects.get_or_create(
            campanha=campanha,
            prospecto=prospecto,
            canal="email",
            defaults={
                "destinatario_nome": prospecto.contato_nome or prospecto.razao_social,
                "destinatario_endereco": endereco,
                "assunto_snapshot": campanha.assunto_email,
                "conteudo_snapshot": campanha.conteudo_email,
                "agendado_para": agendado_para,
            },
        )
        resultado["criados" if criado else "existentes"] += 1
        if criado:
            destinos_ativos.add(("email", endereco))

    if resultado["criados"] or resultado["existentes"]:
        CampanhaMarketing.objects.filter(pk=campanha.pk).update(
            disparo_solicitado_em=campanha.disparo_solicitado_em or timezone.now(),
        )
    return resultado


def _normalizar_whatsapp(telefone):
    numero = "".join(ch for ch in str(telefone or "") if ch.isdigit())
    if len(numero) in (10, 11):
        numero = f"55{numero}"
    if len(numero) not in (12, 13) or not numero.startswith("55"):
        raise CampanhaMarketingInvalida(
            f"Telefone/WhatsApp inválido para envio internacional: {telefone!r}."
        )
    return numero


def _enviar_email(envio):
    texto_rodape = (
        "\n\n---\nPara deixar de receber campanhas, responda a este e-mail solicitando "
        "o cancelamento. A DS Científica registrará a revogação no AXION."
    )
    midias_inline = []
    anexos = []
    midias = envio.campanha.midias.filter(uso_autorizado=True, canal_sugerido="email")
    for midia in midias:
        mime_type, _ = mimetypes.guess_type(midia.arquivo.name)
        mime_type = mime_type or "application/octet-stream"
        with midia.arquivo.open("rb") as arquivo:
            conteudo = arquivo.read()
        if mime_type.startswith("image/") and midia.tipo in ("imagem", "logo", "arte"):
            cid = f"midia-{midia.pk}@axion"
            midias_inline.append({"titulo": midia.titulo, "src": f"cid:{cid}"})
            anexos.append((midia, conteudo, mime_type, cid))
        else:
            anexos.append((midia, conteudo, mime_type, ""))

    contexto = {
        "campanha": envio.campanha,
        "envio": envio,
        "midias_inline": midias_inline,
        "logo_src": "cid:logo-ds@axion",
    }
    corpo_texto = render_to_string("projetos/email/campanha.txt", contexto) + texto_rodape
    corpo_html = render_to_string("projetos/email/campanha.html", contexto)
    mensagem = EmailMultiAlternatives(
        subject=envio.assunto_snapshot,
        body=corpo_texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[envio.destinatario_endereco],
    )
    mensagem.attach_alternative(corpo_html, "text/html")

    logo_path = Path(settings.BASE_DIR) / "static" / "img" / "logo_ds.png"
    if logo_path.exists():
        logo = MIMEImage(logo_path.read_bytes(), _subtype="png")
        logo.add_header("Content-ID", "<logo-ds@axion>")
        logo.add_header("Content-Disposition", "inline", filename="logo-ds.png")
        mensagem.attach(logo)

    for midia, conteudo, mime_type, cid in anexos:
        nome = Path(midia.arquivo.name).name
        if cid:
            imagem = MIMEImage(conteudo, _subtype=mime_type.split("/", 1)[1])
            imagem.add_header("Content-ID", f"<{cid}>")
            imagem.add_header("Content-Disposition", "inline", filename=nome)
            mensagem.attach(imagem)
        else:
            mensagem.attach(nome, conteudo, mime_type)
    quantidade = mensagem.send(fail_silently=False)
    if quantidade != 1:
        raise RuntimeError("O provedor SMTP não confirmou o envio da mensagem.")
    return ""


def _enviar_whatsapp(envio):
    token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
    phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
    api_version = getattr(settings, "WHATSAPP_API_VERSION", "")
    if not token or not phone_number_id or not api_version:
        raise RuntimeError("A API oficial do WhatsApp ainda não está configurada.")

    payload = {
        "messaging_product": "whatsapp",
        "to": envio.destinatario_endereco,
        "type": "template",
        "template": {
            "name": envio.template_snapshot,
            "language": {"code": envio.idioma_template_snapshot or "pt_BR"},
        },
    }
    request = Request(
        f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            resposta = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detalhe = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"WhatsApp HTTP {exc.code}: {detalhe[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Falha de conexão com o WhatsApp: {exc.reason}") from exc

    mensagens = resposta.get("messages") or []
    if not mensagens or not mensagens[0].get("id"):
        raise RuntimeError("A API do WhatsApp não retornou o identificador da mensagem.")
    return mensagens[0]["id"]


def processar_envio_campanha(envio_id):
    with transaction.atomic():
        envio = (
            EnvioCampanha.objects.select_for_update(of=("self",))
            .select_related("contato", "contato__cliente", "prospecto", "campanha")
            .get(pk=envio_id)
        )
        if envio.status not in ("pendente", "falha"):
            return envio.status
        if envio.agendado_para > timezone.now():
            return "agendado"
        contato_autorizado = bool(
            envio.contato and envio.contato.marketing_autorizado(envio.canal)
        )
        prospecto_autorizado = bool(
            envio.prospecto
            and envio.canal == "email"
            and envio.prospecto.marketing_email_permitido()
        )
        if not (contato_autorizado or prospecto_autorizado):
            envio.status = "cancelado"
            envio.erro = "Envio cancelado porque o destinatário não possui mais autorização válida."
            envio.save(update_fields=("status", "erro"))
            return "cancelado"
        envio.status = "processando"
        envio.tentativas += 1
        envio.ultima_tentativa_em = timezone.now()
        envio.erro = ""
        envio.save(update_fields=("status", "tentativas", "ultima_tentativa_em", "erro"))

    try:
        identificador = _enviar_email(envio) if envio.canal == "email" else _enviar_whatsapp(envio)
    except Exception as exc:
        EnvioCampanha.objects.filter(pk=envio.pk).update(
            status="falha",
            erro=f"{type(exc).__name__}: {exc}"[:2000],
        )
        return "falha"

    EnvioCampanha.objects.filter(pk=envio.pk).update(
        status="enviado",
        enviado_em=timezone.now(),
        identificador_provedor=identificador,
        erro="",
    )
    return "enviado"
