from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("comercial", "0026_prospeccaosequencia"),
    ]

    operations = [
        migrations.AddField(
            model_name="prospeccaointeracao",
            name="proxima_acao_tipo",
            field=models.CharField(
                blank=True,
                choices=[
                    ("ligacao", "Ligação"),
                    ("email", "E-mail"),
                    ("whatsapp", "WhatsApp"),
                    ("reuniao", "Reunião"),
                    ("visita", "Visita"),
                    ("outro", "Outro"),
                ],
                help_text=(
                    "Informe se o próximo contato será ligação, e-mail, WhatsApp, "
                    "reunião ou visita."
                ),
                max_length=20,
                verbose_name="Tipo do próximo passo",
            ),
        ),
    ]
