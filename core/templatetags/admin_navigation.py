from django import template


register = template.Library()


MODELOS_CALIBRACAO = {
    "calibracao",
    "calibracaoturbidez",
    "calibracaocolorimetro",
    "calibracaopressao",
    "calibracaocondutividade",
    "calibracaoph",
    "calibracaobalanca",
    "calibracaodispositivosegurancapressao",
    "calibracaoesfigmomanometro",
}


@register.filter
def is_calibration_model(opts):
    return bool(
        opts
        and opts.app_label == "calibracao"
        and opts.model_name in MODELOS_CALIBRACAO
    )
