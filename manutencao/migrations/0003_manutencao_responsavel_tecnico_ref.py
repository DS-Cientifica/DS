from django.db import migrations, models
import django.db.models.deletion


def preencher_responsavel_padrao(apps, schema_editor):
    Manutencao = apps.get_model("manutencao", "Manutencao")
    ResponsavelCertificado = apps.get_model("calibracao", "ResponsavelCertificado")

    responsavel = (
        ResponsavelCertificado.objects.filter(ativo=True).order_by("nome").first()
    )
    if responsavel is None:
        responsavel, _ = ResponsavelCertificado.objects.get_or_create(
            nome="Diego Henrique Alves Saldanha",
            defaults={"cargo": "Responsável técnico", "ativo": True},
        )

    Manutencao.objects.filter(responsavel_tecnico_ref__isnull=True).update(
        responsavel_tecnico_ref=responsavel
    )


class Migration(migrations.Migration):

    dependencies = [
        ("calibracao", "0014_responsavelcertificado_and_more"),
        ("manutencao", "0002_alter_text_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="manutencao",
            name="responsavel_tecnico_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="manutencoes_como_responsavel",
                to="calibracao.responsavelcertificado",
            ),
        ),
        migrations.RunPython(preencher_responsavel_padrao, migrations.RunPython.noop),
    ]
