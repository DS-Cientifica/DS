from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("calibracao", "0052_calibracaoturbidez_motivo_revisao_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="calibracao",
            name="origem_certificado",
            field=models.CharField(
                choices=[
                    ("nao_classificado", "Não classificado"),
                    ("emitido_ds", "Emitido pela DS Científica"),
                    ("emitido_terceiro", "Emitido por laboratório externo"),
                ],
                default="nao_classificado",
                help_text=(
                    "Classifique a autoria do PDF. Somente certificados emitidos pela DS "
                    "Científica podem receber a assinatura digital A1 da empresa."
                ),
                max_length=30,
                verbose_name="Responsabilidade pela emissão",
            ),
        ),
    ]
