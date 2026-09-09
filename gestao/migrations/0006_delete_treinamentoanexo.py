from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0005_treinamentoanexo"),
    ]

    operations = [
        migrations.DeleteModel(
            name="TreinamentoAnexo",
        ),
    ]
