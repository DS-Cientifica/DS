# Generated manually for maintenance module.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("clientes", "0002_alter_perfilusuario_empresa"),
        ("calibracao", "0023_calibracaocondutividade"),
    ]

    operations = [
        migrations.CreateModel(
            name="Manutencao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero_relatorio", models.CharField(blank=True, max_length=40, unique=True)),
                ("ordem_servico", models.CharField(blank=True, max_length=40)),
                ("tipo_manutencao", models.CharField(choices=[("preventiva", "Preventiva"), ("corretiva", "Corretiva"), ("ajuste", "Ajuste"), ("diagnostico", "Diagnóstico")], default="preventiva", max_length=20)),
                ("data_recepcao", models.DateField(blank=True, null=True)),
                ("data_servico", models.DateField()),
                ("data_saida", models.DateField(blank=True, null=True)),
                ("condicao_recebida", models.TextField(blank=True)),
                ("condicao_saida", models.TextField(blank=True)),
                ("diagnostico", models.TextField(blank=True)),
                ("parecer_tecnico", models.TextField(blank=True)),
                ("criterio_aceitacao", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("conforme", "Conforme"), ("nao_conforme", "Não conforme"), ("bloqueado", "Bloqueado")], default="conforme", max_length=20)),
                ("responsavel_tecnico", models.CharField(blank=True, max_length=120)),
                ("observacoes", models.TextField(blank=True)),
                ("proxima_manutencao", models.DateField(blank=True, null=True)),
                ("intervencoes", models.JSONField(blank=True, default=list)),
                ("materiais", models.JSONField(blank=True, default=list)),
                ("verificacoes", models.JSONField(blank=True, default=list)),
                ("rastreabilidade", models.JSONField(blank=True, default=list)),
                ("resultados", models.JSONField(blank=True, default=list)),
                ("aprovado_por", models.CharField(blank=True, max_length=120)),
                ("aprovado_cargo", models.CharField(blank=True, max_length=120)),
                ("aprovado_em", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("cliente", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manutencoes", to="clientes.cliente")),
                ("instrumento", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manutencoes", to="calibracao.instrumento")),
            ],
            options={
                "verbose_name": "Manutenção",
                "verbose_name_plural": "Manutenções",
                "ordering": ["-data_servico", "-id"],
            },
        ),
    ]
