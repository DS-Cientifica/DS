from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("planejamento", "0009_planejamentoservico_resposta_cliente"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="planejamentoservico",
            name="token_resposta_cliente",
        ),
        migrations.RemoveField(
            model_name="planejamentoservico",
            name="resposta_cliente",
        ),
        migrations.RemoveField(
            model_name="planejamentoservico",
            name="resposta_cliente_em",
        ),
        migrations.RemoveField(
            model_name="planejamentoservico",
            name="resposta_cliente_motivo",
        ),
    ]
