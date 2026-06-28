# Generated to make maintenance fields user-friendly in admin.

from django.db import migrations, models


def clear_null_text_fields(apps, schema_editor):
    Manutencao = apps.get_model("manutencao", "Manutencao")
    for field in ("intervencoes", "materiais", "verificacoes", "rastreabilidade", "resultados"):
        Manutencao.objects.filter(**{f"{field}__isnull": True}).update(**{field: ""})


class Migration(migrations.Migration):

    dependencies = [
        ("manutencao", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(clear_null_text_fields, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="manutencao",
            name="intervencoes",
            field=models.TextField(blank=True, default="", help_text="Descreva as intervenções realizadas."),
        ),
        migrations.AlterField(
            model_name="manutencao",
            name="materiais",
            field=models.TextField(blank=True, default="", help_text="Liste materiais, peças ou consumíveis."),
        ),
        migrations.AlterField(
            model_name="manutencao",
            name="verificacoes",
            field=models.TextField(blank=True, default="", help_text="Descreva verificações e testes executados."),
        ),
        migrations.AlterField(
            model_name="manutencao",
            name="rastreabilidade",
            field=models.TextField(blank=True, default="", help_text="Descreva padrões, certificados e rastreabilidade."),
        ),
        migrations.AlterField(
            model_name="manutencao",
            name="resultados",
            field=models.TextField(blank=True, default="", help_text="Descreva resultados e evidências relevantes."),
        ),
    ]
