from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404, render

from .models import Calibracao, CalibracaoTurbidez
from .pdf import gerar_pdf_calibracao

EMPRESA_CERTIFICADO = {
    "nome": "DS Científica",
    "site": "www.dscientifica.com.br",
    "telefone": "(11) 98859-9577",
    "cnpj": "63.669.660/0001-80",
    "cidade": "Jundiaí / SP",
    "email": "contato@dscientifica.com.br",
}


@login_required
def pdf_calibracao(request, calibracao_id):
    calibracao = get_object_or_404(Calibracao, id=calibracao_id)

    buffer = gerar_pdf_calibracao(calibracao)

    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"calibracao_{calibracao.instrumento.codigo}.pdf"
    )


def _formatar_decimal(valor, casas=4):
    if valor in (None, ""):
        return "—"
    return f"{valor:.{casas}f}".replace(".", ",")


@login_required
def pdf_calibracao_turbidez(request, pk):
    calibracao = get_object_or_404(
        CalibracaoTurbidez.objects.select_related("instrumento", "cliente").prefetch_related(
            "padroes_utilizados",
            "pontos_verificacao",
            "pontos_calibracao",
            "pontos_incerteza",
        ),
        pk=pk,
    )

    padroes_por_tipo = {}
    for padrao in calibracao.padroes_utilizados.all():
        padroes_por_tipo.setdefault(padrao.get_tipo_display(), []).append(padrao)

    pontos_incerteza = list(calibracao.pontos_incerteza.all())
    pontos_incerteza_por_ordem = {ponto.ordem: ponto for ponto in pontos_incerteza}
    fator_k_certificado = next(
        (ponto.fator_k for ponto in pontos_incerteza if ponto.fator_k not in (None, "")),
        None,
    )
    graus_liberdade_certificado = next(
        (ponto.graus_liberdade for ponto in pontos_incerteza if ponto.graus_liberdade not in (None, "")),
        None,
    )

    resultados_calibracao = []
    for ponto in calibracao.pontos_calibracao.all():
        incerteza = pontos_incerteza_por_ordem.get(ponto.ordem)
        resultados_calibracao.append({
            "ordem": ponto.ordem,
            "valor_referencia": ponto.valor_referencia,
            "leitura_equipamento": ponto.media,
            "erro": ponto.erro,
            "incerteza_expandida": getattr(incerteza, "incerteza_expandida", None),
            "fator_k": getattr(incerteza, "fator_k", None),
            "graus_liberdade": getattr(incerteza, "graus_liberdade", None),
            "ema": ponto.ema,
        })

    context = {
        "empresa": EMPRESA_CERTIFICADO,
        "calibracao": calibracao,
        "padroes_por_tipo": padroes_por_tipo,
        "verificacoes": calibracao.pontos_verificacao.all(),
        "resultados_calibracao": resultados_calibracao,
        "pontos_incerteza": pontos_incerteza,
        "fator_k_certificado": fator_k_certificado,
        "graus_liberdade_certificado": graus_liberdade_certificado,
        "formatar_decimal": _formatar_decimal,
    }
    return render(request, "calibracao/turbidez_pdf.html", context)
