import hashlib
import re

from django.db import migrations, models


CALIBRACOES_COM_CERTIFICADO = (
    ("Calibracao", "certificado_numero"),
    ("CalibracaoTurbidez", "numero_certificado"),
    ("CalibracaoColorimetro", "numero_certificado"),
    ("CalibracaoPressao", "numero_certificado"),
    ("CalibracaoCondutividade", "numero_certificado"),
    ("CalibracaoPH", "numero_certificado"),
    ("CalibracaoBalanca", "numero_certificado"),
    ("CalibracaoDispositivoSegurancaPressao", "numero_certificado"),
    ("CalibracaoEsfigmomanometro", "numero_certificado"),
)
FORMATO_NOVO = re.compile(r"^(?=(?:.*[A-Z]){3})(?=(?:.*\d){3})[A-Z0-9]{6}DS$")
MOTIVO = "Padronização global dos números de certificados de calibração."


def _codigo_deterministico(chave, tentativa):
    digest = hashlib.sha256(
        f"AXION-CERTIFICADO-DS|{chave}|{tentativa}".encode("utf-8")
    ).digest()
    caracteres = [
        *(chr(ord("A") + digest[indice] % 26) for indice in range(3)),
        *(str(digest[indice] % 10) for indice in range(3, 6)),
    ]
    ordem = sorted(range(6), key=lambda indice: digest[6 + indice])
    return "".join(caracteres[indice] for indice in ordem) + "DS"


def renumerar_certificados_existentes(apps, schema_editor):
    Registro = apps.get_model("calibracao", "NumeroCertificadoEmitido")
    Historico = apps.get_model("calibracao", "HistoricoNumeroCertificado")
    usados = set(Registro.objects.values_list("codigo", flat=True))

    for nome_modelo, campo in CALIBRACOES_COM_CERTIFICADO:
        Modelo = apps.get_model("calibracao", nome_modelo)
        objetos = Modelo.objects.exclude(**{campo: ""}).order_by("pk").values_list("pk", campo)
        for objeto_id, numero_anterior in objetos:
            numero_anterior = (numero_anterior or "").strip().upper()
            if not numero_anterior or FORMATO_NOVO.fullmatch(numero_anterior):
                continue

            identidade = f"calibracao|{Modelo._meta.model_name}|{objeto_id}|{numero_anterior}"
            tentativa = 0
            while True:
                numero_novo = _codigo_deterministico(identidade, tentativa)
                if numero_novo not in usados:
                    break
                tentativa += 1

            Modelo.objects.filter(pk=objeto_id).update(**{campo: numero_novo})
            Registro.objects.filter(
                app_label="calibracao",
                modelo=Modelo._meta.model_name,
                objeto_id=str(objeto_id),
                codigo=numero_anterior,
            ).update(codigo=numero_novo, historico=False)
            Historico.objects.create(
                numero_anterior=numero_anterior,
                numero_novo=numero_novo,
                app_label="calibracao",
                modelo=Modelo._meta.model_name,
                objeto_id=str(objeto_id),
                motivo=MOTIVO,
            )
            usados.add(numero_novo)


def restaurar_numeros_anteriores(apps, schema_editor):
    Registro = apps.get_model("calibracao", "NumeroCertificadoEmitido")
    Historico = apps.get_model("calibracao", "HistoricoNumeroCertificado")
    campos = {
        apps.get_model("calibracao", nome)._meta.model_name: (nome, campo)
        for nome, campo in CALIBRACOES_COM_CERTIFICADO
    }
    for item in Historico.objects.filter(motivo=MOTIVO).order_by("pk"):
        nome_modelo, campo = campos[item.modelo]
        Modelo = apps.get_model("calibracao", nome_modelo)
        Modelo.objects.filter(pk=item.objeto_id).update(**{campo: item.numero_anterior})
        Registro.objects.filter(
            app_label=item.app_label,
            modelo=item.modelo,
            objeto_id=item.objeto_id,
            codigo=item.numero_novo,
        ).update(codigo=item.numero_anterior, historico=True)
    Historico.objects.filter(motivo=MOTIVO).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("calibracao", "0035_numerocertificadoemitido"),
    ]

    operations = [
        migrations.CreateModel(
            name="HistoricoNumeroCertificado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero_anterior", models.CharField(max_length=100, unique=True)),
                ("numero_novo", models.CharField(max_length=100, unique=True)),
                ("app_label", models.CharField(max_length=50)),
                ("modelo", models.CharField(max_length=100)),
                ("objeto_id", models.CharField(max_length=64)),
                ("motivo", models.CharField(max_length=255)),
                ("alterado_em", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Histórico de número de certificado",
                "verbose_name_plural": "Históricos de números de certificados",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("app_label", "modelo", "objeto_id"),
                        name="historico_numero_certificado_por_objeto_unico",
                    )
                ],
            },
        ),
        migrations.RunPython(
            renumerar_certificados_existentes,
            restaurar_numeros_anteriores,
        ),
    ]
