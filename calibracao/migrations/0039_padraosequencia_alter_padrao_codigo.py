from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("calibracao", "0038_calibracao_ordem_servico"),
    ]

    operations = [
        migrations.CreateModel(
            name="PadraoSequencia",
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
                ("ultimo_numero", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name": "Sequência de padrão",
                "verbose_name_plural": "Sequências de padrões",
            },
        ),
        migrations.AlterField(
            model_name="padrao",
            name="codigo",
            field=models.CharField(
                blank=True,
                editable=False,
                help_text="Gerado automaticamente no formato DSP-001.",
                max_length=50,
                unique=True,
            ),
        ),
    ]
