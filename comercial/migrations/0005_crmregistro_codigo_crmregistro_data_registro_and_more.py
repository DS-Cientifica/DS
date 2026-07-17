from django.db import migrations, models
from django.utils import timezone


def preencher_codigos_crm(apps, schema_editor):
    CRMRegistro = apps.get_model("comercial", "CRMRegistro")
    CRMTicket = apps.get_model("comercial", "CRMTicket")

    for indice, registro in enumerate(CRMRegistro.objects.order_by("id"), start=1):
        if not registro.codigo:
            ano = (
                registro.data_registro.strftime("%y")
                if getattr(registro, "data_registro", None)
                else timezone.now().strftime("%y")
            )
            registro.codigo = f"CRM-{indice:04d}/{ano}"
            registro.save(update_fields=["codigo"])

    for indice, ticket in enumerate(CRMTicket.objects.order_by("id"), start=1):
        if not ticket.codigo:
            ano = (
                ticket.data_abertura.strftime("%y")
                if getattr(ticket, "data_abertura", None)
                else timezone.now().strftime("%y")
            )
            ticket.codigo = f"TKT-{indice:04d}/{ano}"
            ticket.save(update_fields=["codigo"])


class Migration(migrations.Migration):

    dependencies = [
        ("comercial", "0004_propostaanexo_tipo"),
    ]

    operations = [
        migrations.AddField(
            model_name="crmregistro",
            name="codigo",
            field=models.CharField(blank=True, max_length=30, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="crmregistro",
            name="data_registro",
            field=models.DateTimeField(default=timezone.now),
        ),
        migrations.AddField(
            model_name="crmticket",
            name="codigo",
            field=models.CharField(blank=True, max_length=30, null=True, unique=True),
        ),
        migrations.RunPython(preencher_codigos_crm, migrations.RunPython.noop),
    ]
