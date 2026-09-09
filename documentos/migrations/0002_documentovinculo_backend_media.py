import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("documentos", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="documentoarquivo",
            name="backend_primario",
            field=models.CharField(
                choices=[
                    ("local", "Local"),
                    ("media", "Mídia legada"),
                    ("r2", "Cloudflare R2"),
                ],
                db_index=True,
                default="local",
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name="DocumentoVinculo",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("object_id", models.CharField(db_index=True, max_length=64)),
                ("campo_origem", models.CharField(blank=True, max_length=100)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="documentos_vinculos", to="contenttypes.contenttype")),
                ("documento", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="vinculos", to="documentos.documentoarquivo")),
            ],
            options={
                "verbose_name": "Vínculo documental",
                "verbose_name_plural": "Vínculos documentais",
                "ordering": ("criado_em",),
                "indexes": [models.Index(fields=["content_type", "object_id"], name="doc_vinculo_obj_idx")],
                "constraints": [models.UniqueConstraint(fields=("documento", "content_type", "object_id", "campo_origem"), name="doc_vinculo_objeto_unico")],
            },
        ),
    ]
