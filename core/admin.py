from django.contrib import admin
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse


_CALIBRACAO_MODEL_FAMILIES = (
    ("CalibracaoPH",),
    ("Calibracao",),
    (
        "CalibracaoBalanca",
        "BalancaPadraoUtilizado",
        "BalancaIncertezaPonto",
    ),
    ("CalibracaoColorimetro",),
    ("CalibracaoCondutividade",),
    ("CalibracaoPressao",),
    ("CalibracaoTurbidez",),
    (
        "CalibracaoDispositivoSegurancaPressao",
        "DispositivoSegurancaPadraoUtilizado",
        "DispositivoSegurancaPonto",
        "DispositivoSegurancaIncertezaPonto",
    ),
    (
        "CalibracaoEsfigmomanometro",
        "EsfigmomanometroPadraoUtilizado",
        "EsfigmomanometroPonto",
        "EsfigmomanometroIncertezaPonto",
        "EsfigmomanometroEnsaioVazamento",
    ),
)

_CALIBRACAO_FAMILY_LABELS = {
    "CalibracaoPH": "Calibração de pH",
    "Calibracao": "Calibrações gerais",
    "CalibracaoBalanca": "Calibração de balanças",
    "CalibracaoColorimetro": "Calibração de colorímetros",
    "CalibracaoCondutividade": "Calibração de condutividade",
    "CalibracaoPressao": "Calibração de pressão",
    "CalibracaoTurbidez": "Calibração de turbidez",
    "CalibracaoDispositivoSegurancaPressao": "Dispositivos de segurança — pressão",
    "CalibracaoEsfigmomanometro": "Esfigmomanômetros",
}

_CALIBRACAO_SUPPORT_LABEL = "Cadastros metrológicos e apoio"


def _agrupar_modelos_metrologicos(app_list):
    """Mantem juntas as telas que fazem parte da mesma familia metrologica."""
    for app in app_list:
        if app.get("app_label") != "calibracao":
            continue

        models = app.get("models", [])
        family_names = {
            object_name
            for family in _CALIBRACAO_MODEL_FAMILIES
            for object_name in family
        }
        family_positions = [
            index
            for index, model in enumerate(models)
            if model.get("object_name") in family_names
        ]
        for model in models:
            model["group_label"] = None

        if not family_positions:
            if models:
                models[0]["group_label"] = _CALIBRACAO_SUPPORT_LABEL
            continue

        models_by_name = {model.get("object_name"): model for model in models}
        grouped_models = [
            models_by_name[object_name]
            for family in _CALIBRACAO_MODEL_FAMILIES
            for object_name in family
            if object_name in models_by_name
        ]
        remaining_models = [
            model for model in models if model.get("object_name") not in family_names
        ]
        insert_at = min(family_positions)
        app["models"] = (
            remaining_models[:insert_at]
            + grouped_models
            + remaining_models[insert_at:]
        )
        for model in app["models"]:
            model["group_label"] = _CALIBRACAO_FAMILY_LABELS.get(
                model.get("object_name")
            )
        if remaining_models:
            remaining_models[0]["group_label"] = _CALIBRACAO_SUPPORT_LABEL

    return app_list


def _separar_calibracoes_da_gestao(app_list):
    family_names = {
        object_name
        for family in _CALIBRACAO_MODEL_FAMILIES
        for object_name in family
    }
    separated_apps = []

    for app in app_list:
        if app.get("app_label") != "calibracao":
            separated_apps.append(app)
            continue

        calibration_models = [
            model
            for model in app.get("models", [])
            if model.get("object_name") in family_names
        ]
        support_models = [
            model
            for model in app.get("models", [])
            if model.get("object_name") not in family_names
        ]

        if calibration_models:
            separated_apps.append(
                {
                    **app,
                    "name": "Calibrações",
                    "app_label": "calibracoes",
                    "app_url": reverse("admin:calibracoes_index"),
                    "models": calibration_models,
                }
            )
        if support_models:
            support_models[0]["group_label"] = None
            separated_apps.append(
                {
                    **app,
                    "name": "Gestão Metrológica",
                    "models": support_models,
                }
            )

    return separated_apps


_default_get_app_list = admin.site.get_app_list


def _get_grouped_app_list(request, app_label=None):
    source_app_label = "calibracao" if app_label == "calibracoes" else app_label
    app_list = _separar_calibracoes_da_gestao(
        _agrupar_modelos_metrologicos(
            _default_get_app_list(request, app_label=source_app_label)
        )
    )
    if app_label == "calibracoes":
        return [app for app in app_list if app.get("app_label") == "calibracoes"]
    if app_label == "calibracao":
        return [app for app in app_list if app.get("app_label") == "calibracao"]
    return app_list


admin.site.get_app_list = _get_grouped_app_list


def _calibracoes_index(request):
    app_list = admin.site.get_app_list(request, app_label="calibracoes")
    context = {
        **admin.site.each_context(request),
        "title": "Calibrações",
        "subtitle": None,
        "app_list": app_list,
        "app_label": "calibracoes",
        "has_permission": admin.site.has_permission(request),
    }
    request.current_app = admin.site.name
    return TemplateResponse(request, "admin/app_index.html", context)


_default_get_urls = admin.site.get_urls


def _get_urls():
    custom_urls = [
        path(
            "calibracoes/",
            admin.site.admin_view(_calibracoes_index),
            name="calibracoes_index",
        )
    ]
    return custom_urls + _default_get_urls()


admin.site.get_urls = _get_urls

admin.site.site_header = "DS Científica"
admin.site.site_title = "Sistema DS Científica"
admin.site.index_title = "Área de Desenvolvimento"
admin.site.index_template = "admin/development_index.html"


_default_admin_index = admin.site.index


def _development_index(request, extra_context=None):
    if not request.user.is_superuser:
        return redirect("inicio")
    context = {
        "development_area": True,
        **(extra_context or {}),
    }
    return _default_admin_index(request, extra_context=context)


admin.site.index = _development_index
