from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404, render

from .models import Calibracao, CalibracaoColorimetro, CalibracaoPressao, CalibracaoTurbidez, _converter_pressao
from .ph_models import CalibracaoPH
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


def _alerta_ou_valor(valor, vazio="ALERTA"):
    if valor in (None, ""):
        return vazio
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


@login_required
def pdf_calibracao_ph(request, pk):
    calibracao = get_object_or_404(
        CalibracaoPH.objects.select_related(
            "instrumento",
            "cliente",
            "procedimento_documento",
            "responsavel_tecnico_ref",
            "tecnico_executante_ref",
        ).prefetch_related(
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
    for ponto in calibracao.pontos_calibracao.all():
        incerteza = pontos_incerteza_por_ordem.get(ponto.ordem)
        referencia = ponto.valor_padrao_ph if ponto.valor_padrao_ph is not None else ponto.valor_padrao_mv
        resultados_calibracao.append(
            {
                "ordem": ponto.ordem,
                "tipo": ponto.get_tipo_display(),
                "referencia": referencia,
                "leitura_equipamento": ponto.media,
                "erro": ponto.erro,
                "incerteza_expandida": getattr(incerteza, "incerteza_expandida", None),
                "fator_k": getattr(incerteza, "fator_k", None),
                "graus_liberdade": getattr(incerteza, "graus_liberdade", None),
                "ema": ponto.ema,
                "resultado": ponto.resultado,
            }
        )

    resultados_eletrica = [
        item for item in resultados_calibracao
        if str(item["tipo"]).lower().startswith("eletrica")
    ]
    resultados_mrc = [
        item for item in resultados_calibracao
        if item not in resultados_eletrica
    ]

    context = {
        "empresa": {
            **EMPRESA_CERTIFICADO,
            "codigo_documento": calibracao.procedimento_documento.codigo if calibracao.procedimento_documento else EMPRESA_CERTIFICADO["codigo_documento"],
        },
        "calibracao": calibracao,
        "padroes_por_tipo": padroes_por_tipo,
        "resultados_calibracao": resultados_calibracao,
        "resultados_eletrica": resultados_eletrica,
        "resultados_mrc": resultados_mrc,
        "pontos_incerteza": pontos_incerteza,
        "fator_k_certificado": fator_k_certificado,
        "graus_liberdade_certificado": graus_liberdade_certificado,
        "formatar_decimal": _formatar_decimal,
        "valor_ou_traco": _valor_ou_traco,
        "document_title": "Certificado de Calibracao de Medidor de pH",
        "document_subtitle": calibracao.get_tipo_calibracao_display(),
        "unit_label": calibracao.unidade_leitura or "pH",
        "resultado_final": calibracao.resultado_final_resolvido,
        "descricao_equipamento": _alerta_ou_valor(calibracao.equipamento_calibrado or calibracao.instrumento.descricao),
        "numero_identificacao": _alerta_ou_valor(calibracao.numero_identificacao or calibracao.instrumento.codigo),
        "marca": _alerta_ou_valor(calibracao.marca or calibracao.instrumento.marca),
        "numero_serie": _alerta_ou_valor(calibracao.numero_serie or calibracao.instrumento.numero_serie),
        "capacidade_ph": _alerta_ou_valor(calibracao.capacidade_total or "0 a 14 pH"),
        "capacidade_mv": _alerta_ou_valor("-500 a 500 mV"),
        "resolucao_ph": _alerta_ou_valor(calibracao.resolucao_ph or "0,01 pH"),
        "resolucao_mv": _alerta_ou_valor(calibracao.resolucao_mv or "0,1 mV"),
        "temperatura_referencia": _alerta_ou_valor(calibracao.temperatura_referencia or "25 °C", vazio="-"),
        "tipo_sensor_temperatura": _alerta_ou_valor(calibracao.tipo_sensor_temperatura),
        "identificacao_sensor_temperatura": _alerta_ou_valor(calibracao.id_sensor_temperatura),
        "identificacao_eletrodo": _alerta_ou_valor(calibracao.identificacao_eletrodo),
        "calibracao_canal": "NÃO APLICÁVEL",
        "local_calibracao_label": _alerta_ou_valor(calibracao.get_local_calibracao_display()),
        "ordem_servico_label": _alerta_ou_valor(calibracao.ordem_servico or "0", vazio="0"),
        "slope_real": calibracao.calculo_inclinacao_real(),
        "slope_indicado": calibracao.slope_indicado,
        "slope_teorico": calibracao.slope_teorico(),
        "ph0": calibracao.calculo_pH0(),
        "eficiencia_eletromotriz": calibracao.eficiencia_eletromotriz(),
        "slope_relativo": calibracao.slope_relativo(),
    }
    return render(request, "calibracao/ph_pdf.html", context)
