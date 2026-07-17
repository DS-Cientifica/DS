from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calibracao", "0027_calibracaocolorimetro_padrao_referencia"),
    ]

    operations = [
        migrations.AddField(
            model_name="colorimetrocalibracaoponto",
            name="criterio_tipo",
            field=models.CharField(
                blank=True,
                choices=[("numerico", "Numérico"), ("percentual", "Percentual (%)")],
                default="numerico",
                max_length=20,
                verbose_name="Tipo do critério",
            ),
        ),
        migrations.AddField(
            model_name="colorimetroverificacaoponto",
            name="criterio_tipo",
            field=models.CharField(
                blank=True,
                choices=[("numerico", "Numérico"), ("percentual", "Percentual (%)")],
                default="numerico",
                max_length=20,
                verbose_name="Tipo do critério",
            ),
        ),
    ]
