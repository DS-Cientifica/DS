from reportlab.graphics import renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing


def gerar_qr_svg(conteudo, *, tamanho=180):
    # Nível M tolera danos moderados na etiqueta sem comprometer em excesso
    # o tamanho dos módulos em um QR impresso com 20 mm.
    qr = QrCodeWidget(conteudo, barLevel="M", barBorder=4)
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
