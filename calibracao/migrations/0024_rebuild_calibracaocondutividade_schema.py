from django.db import migrations


def rebuild_calibracaocondutividade(apps, schema_editor):
    CalibracaoCondutividade = apps.get_model("calibracao", "CalibracaoCondutividade")
    connection = schema_editor.connection
    table_name = CalibracaoCondutividade._meta.db_table

    existing_tables = set(connection.introspection.table_names())
    if table_name in existing_tables:
        schema_editor.delete_model(CalibracaoCondutividade)

    schema_editor.create_model(CalibracaoCondutividade)


class Migration(migrations.Migration):

    dependencies = [
        ("calibracao", "0023_calibracaocondutividade"),
    ]

    operations = [
        migrations.RunPython(rebuild_calibracaocondutividade, migrations.RunPython.noop),
    ]
