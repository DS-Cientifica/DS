from reportlab.graphics import renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing


def gerar_qr_svg(conteudo, *, tamanho=180):
    qr = QrCodeWidget(conteudo)
    x1, y1, x2, y2 = qr.getBounds()
    largura = x2 - x1
    altura = y2 - y1
    desenho = Drawing(
        tamanho,
        tamanho,
        transform=[tamanho / largura, 0, 0, tamanho / altura, 0, 0],
    )
    desenho.add(qr)
    svg = renderSVG.drawToString(desenho)
    return svg.decode("utf-8") if isinstance(svg, bytes) else svg
