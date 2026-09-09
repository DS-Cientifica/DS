from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("qualidade", "0003_documento_arquivo_rascunho_pdf"),
    ]

    operations = [
        migrations.AlterField(
            model_name="documento",
            name="aprovado_por",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AlterField(
            model_name="documento",
            name="data_emissao",
            field=models.DateField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name="documento",
            name="data_ultima_revisao",
            field=models.DateField(blank=True, default=None, null=True),
        ),
    ]
