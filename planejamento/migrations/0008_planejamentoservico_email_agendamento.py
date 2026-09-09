from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("planejamento", "0007_alter_envioequipamentosemnota_empresa_destinataria"),
    ]

    operations = [
        migrations.AddField(
            model_name="planejamentoservico",
            name="notificar_cliente_email",
            field=models.BooleanField(
                default=True,
                help_text="Envia ao e-mail do contato quando o agendamento for salvo. Rascunhos e registros cancelados não são enviados.",
                verbose_name="Enviar e-mail do agendamento ao cliente",
            ),
        ),
        migrations.AddField(
            model_name="planejamentoservico",
            name="email_agendamento_enviado_em",
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Último e-mail enviado em"),
        ),
        migrations.AddField(
            model_name="planejamentoservico",
            name="email_agendamento_destinatario",
            field=models.EmailField(blank=True, editable=False, max_length=254, verbose_name="Último destinatário"),
        ),
        migrations.AddField(
            model_name="planejamentoservico",
            name="email_agendamento_hash",
            field=models.CharField(blank=True, editable=False, max_length=64),
        ),
        migrations.AddField(
            model_name="planejamentoservico",
            name="email_agendamento_erro",
            field=models.TextField(blank=True, editable=False, verbose_name="Falha no último envio"),
        ),
    ]
