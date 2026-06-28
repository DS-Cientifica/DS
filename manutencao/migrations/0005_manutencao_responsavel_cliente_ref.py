from django.db import migrations, models
import django.db.models.deletion


def preencher_responsavel_cliente(apps, schema_editor):
    Manutencao = apps.get_model("manutencao", "Manutencao")

    for manutencao in Manutencao.objects.select_related("cliente").all():
        if manutencao.responsavel_cliente_ref_id:
            continue
        contato = manutencao.cliente.contatos.filter(principal=True).order_by("nome").first()
        if contato is None:
            contato = manutencao.cliente.contatos.order_by("nome").first()
        if contato:
            manutencao.responsavel_cliente_ref = contato
            manutencao.save(update_fields=["responsavel_cliente_ref", "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0001_initial"),
        ("manutencao", "0004_normalizar_campos_responsavel"),
    ]

    operations = [
        migrations.AddField(
            model_name="manutencao",
            name="responsavel_cliente_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="manutencoes_como_responsavel",
                to="clientes.contatocliente",
            ),
        ),
        migrations.RunPython(preencher_responsavel_cliente, migrations.RunPython.noop),
    ]
