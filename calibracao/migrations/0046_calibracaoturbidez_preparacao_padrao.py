from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("calibracao", "0045_ordemservico_ordem_servico_unica_por_proposta"),
    ]

    operations = [
        migrations.AddField(
            model_name="calibracaoturbidez",
            name="preparacao_padrao",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Selecione uma preparação de Turbidez aprovada. Ao salvar, o padrão mãe e "
                    "os padrões preparados serão copiados para a aba Padrões."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="calibracoes_turbidez",
                to="calibracao.preparacaopadrao",
                verbose_name="Preparação de padrão utilizada",
            ),
        ),
    ]
