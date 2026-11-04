import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("documentos", "0002_documentovinculo_backend_media"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AssinaturaDigitalDocumento",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("object_id", models.CharField(db_index=True, max_length=64)),
                ("formato", models.CharField(default="PAdES", max_length=20)),
                ("revisao_referencia", models.CharField(blank=True, max_length=30)),
                ("motivo", models.CharField(blank=True, max_length=255)),
                ("signatario_nome", models.CharField(max_length=255)),
                ("certificado_numero_serie", models.CharField(max_length=160)),
                ("certificado_emissor", models.TextField()),
                ("certificado_fingerprint_sha256", models.CharField(max_length=64)),
                ("certificado_valido_de", models.DateTimeField()),
                ("certificado_valido_ate", models.DateTimeField()),
                ("assinado_em", models.DateTimeField()),
                ("integridade_verificada", models.BooleanField(default=False)),
                ("status", models.CharField(choices=[("valida", "Válida"), ("substituida", "Substituída"), ("cancelada", "Cancelada")], db_index=True, default="valida", max_length=20)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("autorizado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="assinaturas_digitais_autorizadas", to=settings.AUTH_USER_MODEL)),
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="assinaturas_digitais", to="contenttypes.contenttype")),
                ("documento_assinado", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="assinatura_digital", to="documentos.documentoarquivo")),
                ("documento_original", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="assinaturas_como_original", to="documentos.documentoarquivo")),
            ],
            options={
                "verbose_name": "Assinatura digital",
                "verbose_name_plural": "Assinaturas digitais",
                "ordering": ("-criado_em",),
                "indexes": [models.Index(fields=["content_type", "object_id", "status"], name="doc_assin_obj_status_idx")],
            },
        ),
    ]
