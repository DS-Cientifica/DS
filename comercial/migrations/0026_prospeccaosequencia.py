from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("comercial", "0025_prospecto_marketing_autorizado_por_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProspeccaoSequencia",
            fields=[
                (
                    "ano",
                    models.PositiveSmallIntegerField(primary_key=True, serialize=False),
                ),
                ("ultimo_numero", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name": "Sequência de prospecção",
                "verbose_name_plural": "Sequências de prospecção",
            },
        ),
    ]
