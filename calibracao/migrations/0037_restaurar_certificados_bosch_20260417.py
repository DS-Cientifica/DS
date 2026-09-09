from datetime import date

from django.db import migrations


MOTIVO_REVERSAO = (
    " Reversão autorizada: certificados B.BOSCH de 17/04/2026 mantidos "
    "na identificação original DSC-K6U1K4."
)


def _historicos_alvo(apps):
    Historico = apps.get_model("calibracao", "HistoricoNumeroCertificado")
    Calibracao = apps.get_model("calibracao", "Calibracao")

    for historico in Historico.objects.filter(
        app_label="calibracao",
        modelo="calibracao",
        numero_anterior__startswith="DSC-K6U1K4-",
    ).order_by("numero_anterior"):
        calibracao = (
            Calibracao.objects.select_related("instrumento__cliente")
            .filter(pk=historico.objeto_id, data_calibracao=date(2026, 4, 17))
            .first()
        )
        if calibracao is None:
            continue
        cliente = calibracao.instrumento.cliente
        identificacao = " ".join(
            filter(None, (cliente.razao_social, cliente.nome_empresa))
        ).upper()
        if "BOSCH" in identificacao:
            yield historico, calibracao


def restaurar_identificacao_original(apps, schema_editor):
    Registro = apps.get_model("calibracao", "NumeroCertificadoEmitido")
    for historico, calibracao in _historicos_alvo(apps):
        type(calibracao).objects.filter(pk=calibracao.pk).update(
            certificado_numero=historico.numero_anterior
        )
        Registro.objects.filter(
            app_label=historico.app_label,
            modelo=historico.modelo,
            objeto_id=historico.objeto_id,
            codigo=historico.numero_novo,
        ).update(codigo=historico.numero_anterior, historico=True)
        if MOTIVO_REVERSAO not in historico.motivo:
            historico.motivo += MOTIVO_REVERSAO
            historico.save(update_fields=("motivo",))


def reaplicar_identificacao_nova(apps, schema_editor):
    Registro = apps.get_model("calibracao", "NumeroCertificadoEmitido")
    for historico, calibracao in _historicos_alvo(apps):
        type(calibracao).objects.filter(pk=calibracao.pk).update(
            certificado_numero=historico.numero_novo
        )
        Registro.objects.filter(
            app_label=historico.app_label,
            modelo=historico.modelo,
            objeto_id=historico.objeto_id,
            codigo=historico.numero_anterior,
        ).update(codigo=historico.numero_novo, historico=False)
        historico.motivo = historico.motivo.replace(MOTIVO_REVERSAO, "")
        historico.save(update_fields=("motivo",))


class Migration(migrations.Migration):
    dependencies = [
        ("calibracao", "0036_historiconumerocertificado_renumerar_existentes"),
    ]

    operations = [
        migrations.RunPython(
            restaurar_identificacao_original,
            reaplicar_identificacao_nova,
        ),
    ]
