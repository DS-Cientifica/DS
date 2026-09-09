import uuid

from django.db import migrations, models


def preencher_tokens_resposta(apps, schema_editor):
    PlanejamentoServico = apps.get_model("planejamento", "PlanejamentoServico")
    for planejamento in PlanejamentoServico.objects.filter(token_resposta_cliente__isnull=True).iterator():
        planejamento.token_resposta_cliente = uuid.uuid4()
        planejamento.save(update_fields=("token_resposta_cliente",))


class Migration(migrations.Migration):

    dependencies = [
        ("planejamento", "0008_planejamentoservico_email_agendamento"),
    ]

    operations = [
        migrations.AddField(
            model_name="planejamentoservico",
            name="email_agendamento_sequencia",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="planejamentoservico",
            name="token_resposta_cliente",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(preencher_tokens_resposta, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="planejamentoservico",
            name="token_resposta_cliente",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name="planejamentoservico",
            name="resposta_cliente",
            field=models.CharField(
                choices=[
                    ("pendente", "Aguardando resposta"),
                    ("sim", "Confirmado pelo cliente"),
                    ("nao", "Não confirmado pelo cliente"),
                ],
                default="pendente",
                editable=False,
                max_length=10,
                verbose_name="Resposta do cliente",
            ),
        ),
        migrations.AddField(
            model_name="planejamentoservico",
            name="resposta_cliente_em",
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Resposta recebida em"),
        ),
        migrations.AddField(
            model_name="planejamentoservico",
            name="resposta_cliente_motivo",
            field=models.TextField(blank=True, editable=False, verbose_name="Motivo informado pelo cliente"),
        ),
    ]
