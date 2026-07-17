from django.db import migrations

from calibracao.access_groups import apply_default_access_groups


def refresh_default_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    apply_default_access_groups(Group, Permission)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("gestao", "0003_documentoempresa"),
    ]

    operations = [
        migrations.RunPython(refresh_default_groups, noop_reverse),
    ]
