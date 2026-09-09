import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentoArquivo",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tipo_documento", models.CharField(db_index=True, max_length=80)),
                ("nome_original", models.CharField(max_length=255)),
                ("chave_armazenamento", models.CharField(max_length=500, unique=True)),
                ("backend_primario", models.CharField(choices=[("local", "Local"), ("r2", "Cloudflare R2")], db_index=True, default="local", max_length=10)),
                ("sha256", models.CharField(db_index=True, max_length=64)),
                ("tamanho", models.PositiveBigIntegerField()),
                ("mime_type", models.CharField(default="application/octet-stream", max_length=150)),
                ("imutavel", models.BooleanField(default=False)),
                ("status", models.CharField(choices=[("ativo", "Ativo"), ("substituido", "Substituído"), ("cancelado", "Cancelado")], db_index=True, default="ativo", max_length=20)),
                ("object_id", models.CharField(blank=True, db_index=True, max_length=64, null=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("verificado_em", models.DateTimeField(blank=True, null=True)),
                ("content_type", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="documentos_arquivos", to="contenttypes.contenttype")),
                ("criado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="documentos_criados", to=settings.AUTH_USER_MODEL)),
                ("documento_anterior", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="substituicoes", to="documentos.documentoarquivo")),
            ],
            options={
                "verbose_name": "Arquivo documental",
                "verbose_name_plural": "Arquivos documentais",
                "ordering": ("-criado_em",),
                "indexes": [
                    models.Index(fields=["content_type", "object_id"], name="doc_objeto_idx"),
                    models.Index(fields=["tipo_documento", "status"], name="doc_tipo_status_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SincronizacaoDocumento",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("destino", models.CharField(choices=[("r2", "Cloudflare R2")], default="r2", max_length=10)),
                ("status", models.CharField(choices=[("pendente", "Pendente"), ("processando", "Processando"), ("sincronizado", "Sincronizado"), ("falha", "Falha")], db_index=True, default="pendente", max_length=20)),
                ("tentativas", models.PositiveIntegerField(default=0)),
                ("ultimo_erro", models.TextField(blank=True)),
                ("etag_remoto", models.CharField(blank=True, max_length=255)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("sincronizado_em", models.DateTimeField(blank=True, null=True)),
                ("documento", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sincronizacoes", to="documentos.documentoarquivo")),
            ],
            options={
                "verbose_name": "Sincronização documental",
                "verbose_name_plural": "Sincronizações documentais",
                "ordering": ("criado_em",),
                "constraints": [models.UniqueConstraint(fields=("documento", "destino"), name="doc_sync_destino_unico")],
            },
        ),
    ]
