from io import BytesIO
from pathlib import Path

from django.contrib.staticfiles import finders
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


PRIMARY = colors.HexColor("#283864")
SOFT = colors.HexColor("#f4f6f9")
LINE = colors.HexColor("#b9c1cd")
LINE_SOFT = colors.HexColor("#d8dde6")
TEXT = colors.HexColor("#172033")
MUTED = colors.HexColor("#5f6b7a")


def _logo_path():
    caminho = finders.find("img/logo_ds.png")
    if caminho and Path(caminho).exists():
        return caminho
    return None


def _paragrafo(texto, style):
    return Paragraph((texto or "").replace("\n", "<br/>"), style)


def gerar_pdf_proposta(proposta, empresa, contexto):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=contexto["pdf_filename"],
        author=empresa["nome"],
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=TEXT,
        alignment=TA_LEFT,
        splitLongWords=True,
    ))
    styles.add(ParagraphStyle(
        name="BodyBold",
        parent=styles["Body"],
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="TitleMain",
        parent=styles["BodyBold"],
        fontSize=18,
        leading=20,
        textColor=PRIMARY,
    ))
    styles.add(ParagraphStyle(
        name="CompanyName",
        parent=styles["BodyBold"],
        fontSize=18,
        leading=18,
        textColor=PRIMARY,
    ))
    styles.add(ParagraphStyle(
        name="Muted",
        parent=styles["Body"],
        textColor=MUTED,
    ))
    styles.add(ParagraphStyle(
        name="HeaderBand",
        parent=styles["BodyBold"],
        textColor=colors.white,
        fontSize=10,
        leading=12,
    ))

    def section_title(texto):
        table = Table([[Paragraph(texto, styles["HeaderBand"])]], colWidths=[182 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
            ("BOX", (0, 0), (-1, -1), 0.8, PRIMARY),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    def info_table(rows, col_widths):
        table = Table(rows, colWidths=col_widths)
        table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.8, LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE_SOFT),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BACKGROUND", (0, 0), (0, -1), SOFT),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (0, -1), PRIMARY),
        ]))
        return table

    story = []
    logo = _logo_path()

    company_block = Table(
        [[
            Paragraph(empresa["nome"].upper(), styles["CompanyName"]),
            Paragraph(
                f'{empresa["site"]} | {empresa["telefone"]}<br/>{empresa["cidade"]} | CNPJ: {empresa["cnpj"]}',
                styles["Muted"],
            ),
        ]],
        colWidths=[95 * mm, 0],
    )
    company_block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    meta = Table([
        [Paragraph("ORÇAMENTO", styles["BodyBold"]), Paragraph(proposta.codigo, styles["BodyBold"])],
        [Paragraph("DATA", styles["BodyBold"]), Paragraph(proposta.data_emissao.strftime("%d/%m/%Y") if proposta.data_emissao else "-", styles["Body"])],
        [Paragraph("REVISÃO", styles["BodyBold"]), Paragraph(proposta.revisao or "00", styles["Body"])],
        [Paragraph("STATUS", styles["BodyBold"]), Paragraph(proposta.get_status_display(), styles["BodyBold"])],
    ], colWidths=[24 * mm, 34 * mm])
    meta.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE_SOFT),
        ("BACKGROUND", (0, 0), (0, -1), SOFT),
        ("TEXTCOLOR", (0, 0), (0, -1), PRIMARY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    if logo:
        header = Table([[
            Image(logo, width=24 * mm, height=24 * mm),
            company_block,
            meta,
        ]], colWidths=[28 * mm, 96 * mm, 58 * mm])
    else:
        header = Table([[company_block, meta]], colWidths=[124 * mm, 58 * mm])

    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    story.append(header)
    story.append(Spacer(1, 6 * mm))
    story.append(Table([[""]], colWidths=[182 * mm], style=TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.5, PRIMARY)])))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("PROPOSTA COMERCIAL", styles["TitleMain"]))
    story.append(Spacer(1, 4 * mm))

    cliente = proposta.cliente
    story.append(section_title("I. DADOS DO CLIENTE"))
    story.append(info_table([
        [Paragraph("RAZÃO SOCIAL", styles["BodyBold"]), Paragraph(cliente.razao_social or "-", styles["Body"])],
        [Paragraph("ENDEREÇO", styles["BodyBold"]), Paragraph(contexto["endereco_cliente"] or "-", styles["Body"])],
        [Paragraph("CNPJ", styles["BodyBold"]), Paragraph(cliente.cnpj or "-", styles["Body"])],
    ], [28 * mm, 154 * mm]))
    story.append(Spacer(1, 3 * mm))

    contato = contexto["contato"]
    contato_nome = getattr(contato, "nome", "") if contato else ""
    contato_telefone = getattr(contato, "telefone", "") if contato else ""
    contato_email = getattr(contato, "email", "") if contato else ""
    contato_cargo = getattr(contato, "cargo", "") if contato else ""
    story.append(section_title("II. DADOS PARA CONTATO"))
    story.append(info_table([
        [Paragraph("CONTATO", styles["BodyBold"]), Paragraph(contato_nome or "-", styles["Body"]), Paragraph("DEPARTAMENTO", styles["BodyBold"]), Paragraph(contato_cargo or "-", styles["Body"])],
        [Paragraph("TELEFONE", styles["BodyBold"]), Paragraph(contato_telefone or cliente.telefone or "-", styles["Body"]), Paragraph("CELULAR", styles["BodyBold"]), Paragraph(getattr(cliente, "telefone2", "") or "-", styles["Body"])],
        [Paragraph("EMAIL", styles["BodyBold"]), Paragraph(contato_email or cliente.email or "-", styles["Body"]), Paragraph("", styles["Body"]), Paragraph("", styles["Body"])],
    ], [22 * mm, 69 * mm, 24 * mm, 67 * mm]))
    story.append(Spacer(1, 3 * mm))

    story.append(section_title("III. CONDIÇÕES COMERCIAIS"))
    story.append(info_table([
        [Paragraph("PAGAMENTO", styles["BodyBold"]), Paragraph(proposta.prazo_pagamento or "-", styles["Body"]), Paragraph("FRETE", styles["BodyBold"]), Paragraph(contexto["frete"], styles["Body"])],
        [Paragraph("EXECUÇÃO", styles["BodyBold"]), Paragraph(contexto["local_execucao"], styles["Body"]), Paragraph("PRAZO PARA ATENDIMENTO", styles["BodyBold"]), Paragraph(proposta.prazo_execucao or "-", styles["Body"])],
        [Paragraph("VALIDADE", styles["BodyBold"]), Paragraph(proposta.validade.strftime("%d/%m/%Y") if proposta.validade else "-", styles["Body"]), Paragraph("", styles["Body"]), Paragraph("", styles["Body"])],
    ], [22 * mm, 69 * mm, 24 * mm, 67 * mm]))
    story.append(Spacer(1, 3 * mm))

    story.append(section_title("IV. DESCRIÇÃO DO ORÇAMENTO"))
    item_rows = [[
        Paragraph("ITEM", styles["BodyBold"]),
        Paragraph("QTD.", styles["BodyBold"]),
        Paragraph("DESCRIÇÃO", styles["BodyBold"]),
        Paragraph("LOCAL", styles["BodyBold"]),
        Paragraph("TIPO", styles["BodyBold"]),
        Paragraph("VALOR UNITÁRIO", styles["BodyBold"]),
        Paragraph("VALOR TOTAL", styles["BodyBold"]),
    ]]
    for idx, item in enumerate(contexto["itens"], start=1):
        codigo_produto = getattr(item["obj"].produto, "codigo", "") if getattr(item["obj"], "produto", None) else ""
        descricao = item["obj"].descricao or "-"
        if codigo_produto:
            descricao = f"{descricao}<br/><font color='#5f6b7a'>{codigo_produto}</font>"
        item_rows.append([
            Paragraph(f"#{idx}", styles["Body"]),
            Paragraph(str(item["obj"].quantidade), styles["Body"]),
            Paragraph(descricao, styles["Body"]),
            Paragraph(contexto["local_execucao"], styles["Body"]),
            Paragraph(item["obj"].produto.get_tipo_display() if getattr(item["obj"], "produto", None) else "-", styles["Body"]),
            Paragraph(item["valor_unitario"], styles["Body"]),
            Paragraph(item["valor_total"], styles["Body"]),
        ])

    item_table = Table(item_rows, colWidths=[10 * mm, 10 * mm, 66 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm], repeatRows=1)
    item_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE_SOFT),
        ("BACKGROUND", (0, 0), (-1, 0), SOFT),
        ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN", (0, 0), (1, -1), "CENTER"),
        ("ALIGN", (5, 1), (6, -1), "RIGHT"),
    ]))
    story.append(item_table)
    story.append(Spacer(1, 3 * mm))

    if contexto.get("historico_itens"):
        story.append(section_title(f'{contexto["secao_historico_numero"]}. HISTORICO DOS ITENS DA PROPOSTA'))
        historico_rows = [[
            Paragraph("DATA", styles["BodyBold"]),
            Paragraph("REVISAO", styles["BodyBold"]),
            Paragraph("USUARIO", styles["BodyBold"]),
            Paragraph("MOVIMENTACAO", styles["BodyBold"]),
        ]]
        for movimento in contexto["historico_itens"]:
            usuario = movimento.usuario.get_full_name() or movimento.usuario.username if movimento.usuario_id else "-"
            historico_rows.append([
                Paragraph(movimento.data.strftime("%d/%m/%Y %H:%M"), styles["Body"]),
                Paragraph(movimento.revisao or "00", styles["Body"]),
                Paragraph(usuario, styles["Body"]),
                Paragraph(movimento.descricao or "-", styles["Body"]),
            ])

        historico_table = Table(historico_rows, colWidths=[28 * mm, 18 * mm, 34 * mm, 102 * mm], repeatRows=1)
        historico_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.8, LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE_SOFT),
            ("BACKGROUND", (0, 0), (-1, 0), SOFT),
            ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(historico_table)
        story.append(Spacer(1, 3 * mm))

    story.append(section_title(f'{contexto["secao_despesas_numero"]}. DESPESAS E TOTAIS'))
    totals_left = Paragraph("Valores expressos em reais. Tributos e demais condições seguem o cadastro desta proposta.", styles["Body"])
    totals_right = Table([
        [Paragraph("SUBTOTAL", styles["BodyBold"]), Paragraph(contexto["subtotal"], styles["Body"])],
        [Paragraph("DESCONTO ITENS", styles["BodyBold"]), Paragraph(contexto["desconto_itens"], styles["Body"])],
        [Paragraph("DESCONTO GERAL", styles["BodyBold"]), Paragraph(contexto["desconto_geral"], styles["Body"])],
        [Paragraph("FRETE", styles["BodyBold"]), Paragraph(contexto["frete_valor"], styles["Body"])],
        [Paragraph("OUTRAS DESPESAS", styles["BodyBold"]), Paragraph(contexto["outras_despesas"], styles["Body"])],
        [Paragraph("SEGURO", styles["BodyBold"]), Paragraph(contexto["seguro_valor"], styles["Body"])],
        [Paragraph("TOTAL", styles["BodyBold"]), Paragraph(contexto["total"], styles["BodyBold"])],
    ], colWidths=[34 * mm, 24 * mm])
    totals_right.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE_SOFT),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BACKGROUND", (0, 6), (-1, 6), PRIMARY),
        ("TEXTCOLOR", (0, 6), (-1, 6), colors.white),
    ]))
    total_layout = Table([[totals_left, totals_right]], colWidths=[124 * mm, 58 * mm])
    total_layout.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(total_layout)
    story.append(Spacer(1, 3 * mm))

    story.append(section_title(f'{contexto["secao_observacoes_numero"]}. OBSERVAÇÕES'))
    story.append(info_table([[Paragraph(contexto["proposta"].observacoes or "Conforme condições comerciais descritas nesta proposta.", styles["Body"])]], [182 * mm]))
    story.append(Spacer(1, 3 * mm))

    story.append(section_title("CONDIÇÕES GERAIS DA PROPOSTA"))
    story.append(Paragraph(contexto["condicoes_gerais_proposta"].replace("\n", "<br/>"), styles["Body"]))

    doc.build(story)
    buffer.seek(0)
    return buffer
