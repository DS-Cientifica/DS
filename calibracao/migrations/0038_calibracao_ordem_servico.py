from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("calibracao", "0037_restaurar_certificados_bosch_20260417"),
    ]

    operations = [
        migrations.AddField(
            model_name="calibracao",
            name="ordem_servico",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
