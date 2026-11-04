from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("calibracao", "0053_calibracao_origem_certificado"),
    ]

    operations = [
        migrations.AlterField(
            model_name="calibracao",
            name="resultado",
            field=models.CharField(
                choices=[
                    ("nao_declarado", "Não declarado no certificado"),
                    ("aprovado", "Aprovado"),
                    ("ressalva", "Aprovado com ressalva"),
                    ("reprovado", "Reprovado"),
                ],
                default="aprovado",
                max_length=20,
            ),
        ),
    ]
