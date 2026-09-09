from django.db import migrations, models
import django.db.models.deletion


def preencher_snapshots(apps, schema_editor):
    PedidoCompra = apps.get_model("financeiro", "PedidoCompra")
    ContatoCliente = apps.get_model("clientes", "ContatoCliente")
    for pedido in PedidoCompra.objects.select_related("fornecedor").all().iterator():
        fornecedor = pedido.fornecedor
        contato = (
            ContatoCliente.objects.filter(cliente_id=fornecedor.pk)
            .order_by("-principal", "id")
            .first()
        )
        partes_endereco = [
            fornecedor.endereco,
            fornecedor.numero,
            fornecedor.bairro,
            fornecedor.cidade,
            fornecedor.uf,
            fornecedor.cep,
        ]
        pedido.fornecedor_codigo_snapshot = fornecedor.codigo
        pedido.fornecedor_razao_social_snapshot = fornecedor.razao_social
        pedido.fornecedor_nome_fantasia_snapshot = fornecedor.nome_empresa
        pedido.fornecedor_cnpj_snapshot = fornecedor.cnpj
        pedido.fornecedor_ie_snapshot = fornecedor.ie
        pedido.fornecedor_contato_snapshot = contato.nome if contato else ""
        pedido.fornecedor_telefone_snapshot = (
            contato.telefone if contato and contato.telefone else fornecedor.telefone
        )
        pedido.fornecedor_email_snapshot = (
            contato.email if contato and contato.email else fornecedor.email
        )
        pedido.fornecedor_endereco_snapshot = ", ".join(
            str(parte).strip() for parte in partes_endereco if parte and str(parte).strip()
        )
        pedido.save(
            update_fields=(
                "fornecedor_codigo_snapshot",
                "fornecedor_razao_social_snapshot",
                "fornecedor_nome_fantasia_snapshot",
                "fornecedor_cnpj_snapshot",
                "fornecedor_ie_snapshot",
                "fornecedor_contato_snapshot",
                "fornecedor_telefone_snapshot",
                "fornecedor_email_snapshot",
                "fornecedor_endereco_snapshot",
            )
        )


class Migration(migrations.Migration):
    dependencies = [
        ("financeiro", "0006_contapagar_numero_ocorrencia_and_more"),
        ("clientes", "0004_marcar_cnpjs_provisorios"),
    ]

    operations = [
        migrations.AddField(model_name="pedidocompra", name="fornecedor_codigo_snapshot", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="pedidocompra", name="fornecedor_razao_social_snapshot", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="pedidocompra", name="fornecedor_nome_fantasia_snapshot", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="pedidocompra", name="fornecedor_cnpj_snapshot", field=models.CharField(blank=True, max_length=18)),
        migrations.AddField(model_name="pedidocompra", name="fornecedor_ie_snapshot", field=models.CharField(blank=True, max_length=30)),
        migrations.AddField(model_name="pedidocompra", name="fornecedor_contato_snapshot", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="pedidocompra", name="fornecedor_telefone_snapshot", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="pedidocompra", name="fornecedor_email_snapshot", field=models.EmailField(blank=True, max_length=254)),
        migrations.AddField(model_name="pedidocompra", name="fornecedor_endereco_snapshot", field=models.CharField(blank=True, max_length=500)),
        migrations.RunPython(preencher_snapshots, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pedidocompra",
            name="fornecedor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pedidos_compra",
                to="clientes.cliente",
                verbose_name="Fornecedor",
            ),
        ),
    ]
