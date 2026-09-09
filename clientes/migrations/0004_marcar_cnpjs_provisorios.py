from django.db import migrations
from django.db.models import Q


def marcar_cnpjs_provisorios(apps, schema_editor):
    Cliente = apps.get_model("clientes", "Cliente")
    Cliente.objects.filter(
        Q(cnpj__startswith="PROS-") | Q(cnpj__startswith="PROSPECT-")
    ).update(cnpj_provisorio=True)


class Migration(migrations.Migration):
    dependencies = [
        ("clientes", "0003_cliente_cnpj_provisorio"),
    ]

    operations = [
        migrations.RunPython(marcar_cnpjs_provisorios, migrations.RunPython.noop),
    ]
