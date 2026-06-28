from io import BytesIO
from pathlib import Path

from django.contrib.staticfiles import finders
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


EMPRESA = {
    "nome": "DS Científica",
    "site": "www.dscientifica.com.br",
    "telefone": "(11) 98859-9577",
    "cnpj": "63.669.660/0001-80",
    "email": "contato@dscientifica.com.br",
    "codigo_documento": "RMT-0001",
}

PRIMARY = colors.HexColor("#283864")
SOFT = colors.HexColor("#f4f6f9")
LINE = colors.HexColor("#b9c1cd")
LINE_SOFT = colors.HexColor("#d8dde6")
MUTED = colors.HexColor("#5f6b7a")


def _logo_path():
    caminho = finders.find("img/logo_ds.png")
    if caminho and Path(caminho).exists():
        return caminho
    return None


def _valor(valor, vazio="NÃO CONSTA"):
    if valor in (None, ""):
        return vazio
    return str(valor)


def _data(valor):
    if not valor:
        return "NÃO CONSTA"
    return valor.strftime("%d/%m/%Y")


def _data_hora(valor):
    if not valor:
        return "NÃO CONSTA"
    if timezone.is_aware(valor):
        valor = timezone.localtime(valor)
    return valor.strftime("%d/%m/%Y %H:%M")


def _responsavel_nome(manutencao):
    if getattr(manutencao, "responsavel_tecnico_ref_id", None):
        return manutencao.responsavel_tecnico_ref.nome
    return manutencao.responsavel_tecnico or manutencao.aprovado_por or "NÃO CONSTA"


def _responsavel_cargo(manutencao):
    if getattr(manutencao, "responsavel_tecnico_ref_id", None) and manutencao.responsavel_tecnico_ref.cargo:
        return manutencao.responsavel_tecnico_ref.cargo
    return manutencao.aprovado_cargo or "Responsável técnico"


def _responsavel_cliente_nome(manutencao):
    if getattr(manutencao, "responsavel_cliente_ref_id", None):
        return manutencao.responsavel_cliente_ref.nome
    return "NÃO CONSTA"


def _responsavel_cliente_cargo(manutencao):
    if getattr(manutencao, "responsavel_cliente_ref_id", None) and manutencao.responsavel_cliente_ref.cargo:
        return manutencao.responsavel_cliente_ref.cargo
    return "Responsável do cliente"


def _paragrafo(texto, style):
    return Paragraph((texto or "").replace("\n", "<br/>"), style)


def _section_title(titulo, width):
    table = Table(
        [[Paragraph(
            titulo,
            ParagraphStyle(
                "section-title",
                fontName="Helvetica-Bold",
                fontSize=10,
                textColor=colors.white,
                leading=13,
            ),
        )]],
        colWidths=[width],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.7, PRIMARY),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def gerar_pdf_manutencao(manutencao):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"Relatório de Manutenção {manutencao.numero_relatorio}",
        author=EMPRESA["nome"],
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=18,
        textColor=PRIMARY,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="DocSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10.2,
        leading=12,
        textColor=MUTED,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=12,
        textColor=colors.HexColor("#172033"),
        splitLongWords=True,
    ))
    styles.add(ParagraphStyle(
        name="BodyCenter",
        parent=styles["Body"],
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="BodyBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.2,
        leading=12,
        textColor=colors.HexColor("#172033"),
        splitLongWords=True,
    ))
    styles.add(ParagraphStyle(
        name="HeaderBand",
        parent=styles["BodyBold"],
        textColor=colors.white,
    ))

    def cell(texto, estilo="Body"):
        return _paragrafo(_valor(texto), styles[estilo])

    story = []
    logo = _logo_path()
    company_name = Paragraph(f"<b>{EMPRESA['nome'].upper()}</b>", styles["DocTitle"])
    company_text = Paragraph(
        f"{EMPRESA['site']} | {EMPRESA['email']}<br/>"
        f"{EMPRESA['telefone']} | CNPJ: {EMPRESA['cnpj']}",
        styles["DocSub"],
    )
    if logo:
        header = Table([[
            Image(logo, width=24 * mm, height=24 * mm),
            Table([[company_name], [company_text]], colWidths=[144 * mm]),
        ]], colWidths=[30 * mm, 144 * mm])
    else:
        header = Table([[Table([[company_name], [company_text]], colWidths=[174 * mm])]], colWidths=[174 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    titulo_doc = Table([
        [Paragraph("RELATÓRIO DE MANUTENÇÃO", styles["DocTitle"])],
        [Paragraph(EMPRESA["codigo_documento"], styles["DocSub"])],
    ], colWidths=[174 * mm])
    titulo_doc.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    story.append(header)
    story.append(Spacer(1, 3 * mm))
    story.append(titulo_doc)
    story.append(Spacer(1, 3 * mm))
    linha = Table([[""]], colWidths=[174 * mm])
    linha.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.6, PRIMARY)]))
    story.append(linha)
    story.append(Spacer(1, 4 * mm))

    geral = Table([
        [
            Paragraph("1. INFORMAÇÕES GERAIS", styles["HeaderBand"]),
            Paragraph("2. DADOS DO CLIENTE", styles["HeaderBand"]),
        ],
        [
            Paragraph(
                f"<b>Número:</b> {_valor(manutencao.numero_relatorio)}<br/>"
                f"<b>Data do serviço:</b> {_data(manutencao.data_servico)}<br/>"
                f"<b>Tipo:</b> {_valor(manutencao.get_tipo_manutencao_display())}<br/>"
                f"<b>Status:</b> {_valor(manutencao.get_status_display())}",
                styles["Body"],
            ),
            Paragraph(
                f"<b>Cliente:</b> {_valor(manutencao.cliente.razao_social if manutencao.cliente_id else None)}<br/>"
                f"<b>CNPJ:</b> {_valor(manutencao.cliente.cnpj if manutencao.cliente_id else None)}<br/>"
                f"<b>Responsável:</b> {_valor(_responsavel_cliente_nome(manutencao))}<br/>"
                f"<b>Ordem de serviço:</b> {_valor(manutencao.ordem_servico)}",
                styles["Body"],
            ),
        ],
    ], colWidths=[84 * mm, 90 * mm])
    geral.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE_SOFT),
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(geral)
    story.append(Spacer(1, 4 * mm))

    equipamento = Table([
        [Paragraph("3. DADOS DO EQUIPAMENTO / ATENDIMENTO", styles["HeaderBand"]), ""],
        [cell("Equipamento", "BodyBold"), cell(manutencao.instrumento.descricao if manutencao.instrumento_id else None)],
        [cell("Código", "BodyBold"), cell(manutencao.instrumento.codigo if manutencao.instrumento_id else None)],
        [cell("Marca", "BodyBold"), cell(manutencao.instrumento.marca if manutencao.instrumento_id else None)],
        [cell("Modelo", "BodyBold"), cell(manutencao.instrumento.modelo if manutencao.instrumento_id else None)],
        [cell("Número de série", "BodyBold"), cell(manutencao.instrumento.numero_serie if manutencao.instrumento_id else None)],
        [cell("Local de instalação", "BodyBold"), cell(manutencao.instrumento.local_instalacao if manutencao.instrumento_id else None)],
        [cell("Condição recebida", "BodyBold"), cell(manutencao.condicao_recebida)],
        [cell("Condição de saída", "BodyBold"), cell(manutencao.condicao_saida)],
    ], colWidths=[46 * mm, 128 * mm], repeatRows=1)
    equipamento.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BACKGROUND", (0, 1), (0, -1), SOFT),
        ("BOX", (0, 0), (-1, -1), 0.8, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE_SOFT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(equipamento)
    story.append(Spacer(1, 4 * mm))

    for titulo, valor in [
        ("4. Diagnóstico", manutencao.diagnostico),
        ("5. Parecer técnico", manutencao.parecer_tecnico),
    ]:
        story.append(_section_title(titulo, 174 * mm))
        story.append(Spacer(1, 1.5 * mm))
        story.append(_paragrafo(_valor(valor), styles["Body"]))
        story.append(Spacer(1, 3 * mm))

    controle = Table([
        [Paragraph("8. CONTROLE DO ATENDIMENTO", styles["HeaderBand"]), ""],
        [cell("Intervenções", "BodyBold"), cell(manutencao.intervencoes)],
        [cell("Materiais", "BodyBold"), cell(manutencao.materiais)],
        [cell("Verificações", "BodyBold"), cell(manutencao.verificacoes)],
        [cell("Resultados", "BodyBold"), cell(manutencao.resultados)],
        [cell("Observações", "BodyBold"), cell(manutencao.observacoes)],
    ], colWidths=[38 * mm, 136 * mm], repeatRows=1)
    controle.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BACKGROUND", (0, 1), (0, -1), SOFT),
        ("BOX", (0, 0), (-1, -1), 0.8, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE_SOFT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(controle)
    story.append(Spacer(1, 4 * mm))

    story.append(_section_title("9. Evidências", 174 * mm))
    story.append(Spacer(1, 1.5 * mm))
    evidencias = list(manutencao.evidencias.all())
    if evidencias:
        for evidencia in evidencias:
            story.append(_paragrafo(f"<b>{_valor(evidencia.titulo, evidencia.nome_arquivo)}</b>", styles["Body"]))
            story.append(Spacer(1, 1.5 * mm))
            if evidencia.eh_imagem:
                try:
                    image = Image(evidencia.arquivo.path)
                    image._restrictSize(150 * mm, 85 * mm)
                    story.append(image)
                except Exception:
                    story.append(_paragrafo(f"Arquivo anexado: {_valor(evidencia.nome_arquivo)}", styles["Body"]))
            else:
                story.append(_paragrafo(f"Arquivo anexado: {_valor(evidencia.nome_arquivo)}", styles["Body"]))
            story.append(Spacer(1, 3 * mm))
    else:
        story.append(_paragrafo("NÃO CONSTA", styles["Body"]))
        story.append(Spacer(1, 3 * mm))

    story.append(_section_title("10. Aprovação", 174 * mm))
    story.append(Spacer(1, 1.5 * mm))
    aprovacao = Table([
        [cell("Responsável do cliente", "BodyBold"), cell(_responsavel_cliente_nome(manutencao))],
        [cell("Departamento", "BodyBold"), cell(_responsavel_cliente_cargo(manutencao))],
        [cell("Responsável técnico", "BodyBold"), cell(_responsavel_nome(manutencao))],
        [cell("Data", "BodyBold"), cell(_data_hora(manutencao.aprovado_em))],
    ], colWidths=[38 * mm, 136 * mm])
    aprovacao.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE_SOFT),
        ("BACKGROUND", (0, 0), (0, -1), SOFT),
        ("TEXTCOLOR", (0, 0), (0, -1), PRIMARY),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(aprovacao)
    story.append(Spacer(1, 5 * mm))

    story.append(_section_title("11. Notas", 174 * mm))
    story.append(Spacer(1, 1.5 * mm))
    for nota in [
        "Este relatório refere-se exclusivamente ao instrumento e às condições descritas.",
        "Não é permitida a reprodução parcial ou total sem autorização prévia.",
        "Campos sem informação foram mantidos como 'NÃO CONSTA' para preservar a rastreabilidade documental.",
    ]:
        story.append(Paragraph(f"• {nota}", styles["Body"]))
        story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 44 * mm))
    assinatura = Table([[
        Paragraph(_valor(_responsavel_nome(manutencao)), styles["BodyCenter"]),
    ], [
        Paragraph(_valor(_responsavel_cargo(manutencao)), styles["BodyCenter"]),
    ]], colWidths=[90 * mm])
    assinatura.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.black),
    ]))
    story.append(assinatura)

    def on_page(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#5f6b7a"))
        canvas.drawRightString(doc_obj.pagesize[0] - doc_obj.rightMargin, 10 * mm, f"Página {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buffer.seek(0)
    return buffer
