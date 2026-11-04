from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documentos", "0003_assinaturadigitaldocumento"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="assinaturadigitaldocumento",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "valida")),
                fields=("content_type", "object_id"),
                name="doc_uma_assinatura_valida_obj",
            ),
        ),
    ]
