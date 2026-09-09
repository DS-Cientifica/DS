from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("calibracao", "0046_calibracaoturbidez_preparacao_padrao"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="preparacaopadrao",
            name="evidencia_registro_retroativo",
            field=models.FileField(
                blank=True,
                help_text="Anexe o registro original que comprova a preparação e a data informada.",
                null=True,
                upload_to="calibracao/preparacoes/evidencias_retroativas/",
            ),
        ),
        migrations.AddField(
            model_name="preparacaopadrao",
            name="justificativa_registro_retroativo",
            field=models.TextField(
                blank=True,
                help_text="Informe por que o registro não foi realizado na data da preparação.",
            ),
        ),
        migrations.AddField(
            model_name="preparacaopadrao",
            name="registrado_retroativamente_em",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="preparacaopadrao",
            name="registrado_retroativamente_por",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="preparacoes_padrao_registradas_retroativamente",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="preparacaopadrao",
            name="registro_retroativo",
            field=models.BooleanField(
                default=False,
                help_text="Marque quando o registro estiver sendo lançado após a data real da preparação.",
            ),
        ),
    ]
