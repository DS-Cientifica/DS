from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calibracao", "0033_esfigmomanometroincertezaponto_incluir_deriva_padrao_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrdemServicoSequencia",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ano", models.PositiveSmallIntegerField(unique=True)),
                ("ultimo_numero", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name": "Sequência anual de ordem de serviço",
                "verbose_name_plural": "Sequências anuais de ordens de serviço",
            },
        ),
        migrations.AlterField(
            model_name="ordemservico",
            name="numero",
            field=models.CharField(
                blank=True,
                editable=False,
                help_text="Gerado automaticamente no formato 0001/26.",
                max_length=50,
                unique=True,
                verbose_name="Número",
            ),
        ),
    ]
