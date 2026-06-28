from django.db import migrations


def normalizar_campos_responsavel(apps, schema_editor):
    Manutencao = apps.get_model("manutencao", "Manutencao")

    for manutencao in Manutencao.objects.select_related("responsavel_tecnico_ref").all():
        if manutencao.responsavel_tecnico_ref_id:
            manutencao.responsavel_tecnico = manutencao.responsavel_tecnico_ref.nome
            manutencao.aprovado_por = manutencao.responsavel_tecnico_ref.nome
            manutencao.aprovado_cargo = manutencao.responsavel_tecnico_ref.cargo or manutencao.aprovado_cargo
            manutencao.save(
                update_fields=[
                    "responsavel_tecnico",
                    "aprovado_por",
                    "aprovado_cargo",
                    "updated_at",
                ]
            )


class Migration(migrations.Migration):

    dependencies = [
        ("manutencao", "0003_manutencao_responsavel_tecnico_ref"),
    ]

    operations = [
        migrations.RunPython(normalizar_campos_responsavel, migrations.RunPython.noop),
    ]
