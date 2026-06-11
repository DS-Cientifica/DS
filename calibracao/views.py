from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404, render

from .models import Calibracao, CalibracaoColorimetro, CalibracaoPressao, CalibracaoTurbidez, _converter_pressao
from .pdf import gerar_pdf_calibracao

EMPRESA_CERTIFICADO = {
    "nome": "DS Científica",
    "site": "www.dscientifica.com.br",
    "telefone": "(11) 98859-9577",
    "cnpj": "63.669.660/0001-80",
    "cidade": "Jundiaí / SP",
    "email": "contato@dscientifica.com.br",
    "codigo_documento": "CCDS-0001 Rev.00",
}


@login_required
def pdf_calibracao(request, calibracao_id):
    calibracao = get_object_or_404(Calibracao, id=calibracao_id)
    buffer = gerar_pdf_calibracao(calibracao)
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"calibracao_{calibracao.instrumento.codigo}.pdf",
    )


def _formatar_decimal(valor, casas=4):
    if valor in (None, ""):
        return "-"
    return f"{valor:.{casas}f}".replace(".", ",")


def _valor_ou_traco(valor, casas=6):
    if valor in (None, ""):
        return "------"
    try:
        return f"{Decimal(str(valor)):.{casas}f}".replace(".", ",")
    except Exception:
        return str(valor)


def _pressao_leitura_pdf(ponto, campo, calibracao, usar_media_fallback=False):
    valor = getattr(ponto, campo, None)
    if valor not in (None, ""):
        return _valor_ou_traco(valor)
    if usar_media_fallback and ponto.media not in (None, ""):
        media_indicacao = _converter_pressao(
            ponto.media,
            calibracao.unidade_padrao,
            calibracao.unidade_indicacao,
        )
        return _valor_ou_traco(media_indicacao)
    return "------"


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
        resultados_calibracao.append(
            {
                "ordem": ponto.ordem,
                "valor_referencia": ponto.valor_referencia,
                "leitura_equipamento": ponto.media,
                "erro": ponto.erro,
                "incerteza_expandida": getattr(incerteza, "incerteza_expandida", None),
                "fator_k": getattr(incerteza, "fator_k", None),
                "graus_liberdade": getattr(incerteza, "graus_liberdade", None),
                "ema": ponto.ema,
            }
        )

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


@login_required
def pdf_calibracao_colorimetro(request, pk):
    calibracao = get_object_or_404(
        CalibracaoColorimetro.objects.select_related("instrumento", "cliente").prefetch_related(
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
        resultados_calibracao.append(
            {
                "ordem": ponto.ordem,
                "valor_referencia": ponto.valor_referencia,
                "leitura_equipamento": ponto.media,
                "erro": ponto.erro,
                "incerteza_expandida": getattr(incerteza, "incerteza_expandida", None),
                "fator_k": getattr(incerteza, "fator_k", None),
                "graus_liberdade": getattr(incerteza, "graus_liberdade", None),
                "ema": ponto.ema,
            }
        )

    context = {
        "empresa": {
            **EMPRESA_CERTIFICADO,
            "codigo_documento": calibracao.codigo_documento,
        },
        "calibracao": calibracao,
        "padroes_por_tipo": padroes_por_tipo,
        "verificacoes": calibracao.pontos_verificacao.all(),
        "resultados_calibracao": resultados_calibracao,
        "pontos_incerteza": pontos_incerteza,
        "fator_k_certificado": fator_k_certificado,
        "graus_liberdade_certificado": graus_liberdade_certificado,
        "formatar_decimal": _formatar_decimal,
        "document_title": "Certificado de Calibração",
        "document_subtitle": calibracao.titulo_certificado,
        "unit_label": calibracao.unidade_leitura or "mg/L",
        "procedure_text": (
            "Os padrões utilizados na calibração são preparados a partir de materiais de referência "
            "adequados à aplicação. Todos os materiais e equipamentos utilizados são calibrados em "
            "laboratórios acreditados ou rastreáveis à RBC."
        ),
    }
    return render(request, "calibracao/colorimetro_pdf.html", context)


@login_required
def pdf_calibracao_pressao(request, pk):
    calibracao = get_object_or_404(
        CalibracaoPressao.objects.select_related("instrumento", "cliente").prefetch_related(
            "padroes_utilizados",
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
    pontos = list(calibracao.pontos_calibracao.all())
    for ponto in pontos:
        incerteza = pontos_incerteza_por_ordem.get(ponto.ordem)
        graus_liberdade = getattr(incerteza, "graus_liberdade", None)
        if graus_liberdade is not None and Decimal(str(graus_liberdade)) >= Decimal("999999"):
            graus_liberdade_fmt = "Infinito"
        else:
            graus_liberdade_fmt = _valor_ou_traco(graus_liberdade, 2)
        valor_referencia = ponto.valor_referencia_convertido if ponto.valor_referencia_convertido is not None else ponto.valor_referencia
        tem_leitura_individual = any(
            leitura not in (None, "")
            for leitura in (ponto.leitura_1, ponto.leitura_2, ponto.leitura_3, ponto.leitura_4)
        )
        resultados_calibracao.append(
            {
                "ordem": ponto.ordem,
                "valor_referencia": valor_referencia,
                "valor_referencia_fmt": _valor_ou_traco(valor_referencia),
                "leitura_crescente_1": ponto.leitura_1,
                "leitura_crescente_2": ponto.leitura_2,
                "leitura_decrescente_1": ponto.leitura_3,
                "leitura_decrescente_2": ponto.leitura_4,
                "leitura_crescente_1_fmt": _pressao_leitura_pdf(
                    ponto,
                    "leitura_1",
                    calibracao,
                    usar_media_fallback=not tem_leitura_individual,
                ),
                "leitura_crescente_2_fmt": _pressao_leitura_pdf(ponto, "leitura_2", calibracao),
                "leitura_decrescente_1_fmt": _pressao_leitura_pdf(ponto, "leitura_3", calibracao),
                "leitura_decrescente_2_fmt": _pressao_leitura_pdf(ponto, "leitura_4", calibracao),
                "leitura_equipamento": ponto.media,
                "erro": ponto.erro,
                "erro_percentual": ponto.erro_percentual,
                "erro_fmt": _valor_ou_traco(ponto.erro),
                "incerteza_expandida": getattr(incerteza, "incerteza_expandida", None),
                "incerteza_expandida_fmt": _valor_ou_traco(getattr(incerteza, "incerteza_expandida", None)),
                "fator_k": getattr(incerteza, "fator_k", None),
                "fator_k_fmt": _valor_ou_traco(getattr(incerteza, "fator_k", None), 3),
                "graus_liberdade": getattr(incerteza, "graus_liberdade", None),
                "graus_liberdade_fmt": graus_liberdade_fmt,
                "ema": ponto.ema,
                "ema_fmt": _valor_ou_traco(ponto.ema),
                "resultado": ponto.get_resultado_display() if ponto.resultado else "",
                "criterio": ponto.criterio,
                "criterio_origem": ponto.get_criterio_origem_display() if getattr(ponto, "criterio_origem", "") else "",
                "criterio_referencia": getattr(ponto, "criterio_referencia", ""),
            }
        )

    erro_fiducial = None
    histerese = None
    repetibilidade = None
    curva_calibracao = "Não calculada"

    referencias = [Decimal(str(item["valor_referencia"])) for item in resultados_calibracao if item["valor_referencia"] not in (None, "")]
    erros = [abs(Decimal(str(item["erro"]))) for item in resultados_calibracao if item["erro"] not in (None, "")]
    if referencias and erros:
        amplitude = max(referencias) - min(referencias)
        if amplitude != 0:
            erro_fiducial = (max(erros) / amplitude) * Decimal("100")

    histereses = []
    for item in resultados_calibracao:
        if item["leitura_crescente_1"] is not None and item["leitura_decrescente_1"] is not None:
            histereses.append(abs(Decimal(str(item["leitura_crescente_1"])) - Decimal(str(item["leitura_decrescente_1"]))))
        if item["leitura_crescente_2"] is not None and item["leitura_decrescente_2"] is not None:
            histereses.append(abs(Decimal(str(item["leitura_crescente_2"])) - Decimal(str(item["leitura_decrescente_2"]))))
    if histereses and referencias:
        amplitude = max(referencias) - min(referencias)
        if amplitude != 0:
            histerese = (max(histereses) / amplitude) * Decimal("100")

    repetibilidades = [ponto.desvio_padrao for ponto in pontos if ponto.desvio_padrao is not None]
    if repetibilidades:
        repetibilidade = max(repetibilidades)

    context = {
        "empresa": {
            **EMPRESA_CERTIFICADO,
            "codigo_documento": calibracao.codigo_documento,
        },
        "calibracao": calibracao,
        "padroes_por_tipo": padroes_por_tipo,
        "resultados_calibracao": resultados_calibracao,
        "pontos_incerteza": pontos_incerteza,
        "fator_k_certificado": fator_k_certificado,
        "graus_liberdade_certificado": graus_liberdade_certificado,
        "formatar_decimal": _formatar_decimal,
        "valor_ou_traco": _valor_ou_traco,
        "document_title": "Certificado de Pressão",
        "document_subtitle": calibracao.titulo_certificado,
        "unit_label": calibracao.unidade_padrao or "bar",
        "procedure_text": calibracao.metodo_utilizado_texto(),
        "pendencias_certificado": calibracao.pendencias_certificado(),
        "erro_fiducial": erro_fiducial,
        "erro_fiducial_fmt": _valor_ou_traco(erro_fiducial),
        "histerese": histerese,
        "histerese_fmt": _valor_ou_traco(histerese),
        "repetibilidade": repetibilidade,
        "repetibilidade_fmt": _valor_ou_traco(repetibilidade),
        "curva_calibracao": curva_calibracao,
    }
    return render(request, "calibracao/pressao_pdf.html", context)
