from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calibracao", "0047_preparacaopadrao_registro_retroativo"),
    ]

    operations = [
        migrations.AddField(
            model_name="preparacaopadrao",
            name="codigo_anterior",
            field=models.CharField(
                blank=True,
                editable=False,
                help_text="Identificação preservada quando um registro retroativo é reidentificado.",
                max_length=50,
            ),
        ),
    ]
