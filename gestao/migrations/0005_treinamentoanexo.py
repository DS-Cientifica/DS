import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0004_update_access_groups_documentoempresa"),
    ]

    operations = [
        migrations.CreateModel(
            name="TreinamentoAnexo",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("titulo", models.CharField(blank=True, max_length=150)),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("foto", "Foto"),
                            ("video", "Vídeo"),
                            ("certificado", "Certificado"),
                            ("lista_presenca", "Lista de presença"),
                            ("material", "Material do treinamento"),
                            ("avaliacao", "Avaliação"),
                            ("outro", "Outro documento"),
                        ],
                        default="outro",
                        max_length=30,
                    ),
                ),
                (
                    "arquivo",
                    models.FileField(upload_to="gestao/treinamentos/anexos/"),
                ),
                ("data_documento", models.DateField(blank=True, null=True)),
                ("descricao", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "treinamento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="anexos",
                        to="gestao.treinamento",
                    ),
                ),
            ],
            options={
                "verbose_name": "RH - Anexo do treinamento",
                "verbose_name_plural": "RH - Anexos do treinamento",
                "ordering": ("-created_at", "titulo"),
            },
        ),
    ]
