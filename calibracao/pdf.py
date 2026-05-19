from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def gerar_pdf_calibracao(calibracao):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    largura, altura = A4
    y = altura - 50

    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y, "CERTIFICADO DE CALIBRAÇÃO")

    y -= 40
    p.setFont("Helvetica", 10)

    p.drawString(50, y, f"Instrumento: {calibracao.instrumento.descricao}")
    y -= 20
    p.drawString(50, y, f"Código: {calibracao.instrumento.codigo}")
    y -= 20
    p.drawString(50, y, f"Cliente: {calibracao.instrumento.cliente.razao_social}")
    y -= 20
    p.drawString(50, y, f"Data da Calibração: {calibracao.data_calibracao}")
    y -= 20
    p.drawString(50, y, f"Validade: {calibracao.validade}")
    y -= 20
    p.drawString(50, y, f"Status: {calibracao.get_status_display()}")

    p.showPage()
    p.save()

    buffer.seek(0)
    return buffer

