from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("qualidade", "0004_documento_campos_rascunho_opcionais"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentoAnexo",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("titulo", models.CharField(blank=True, max_length=150)),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("foto", "Foto"),
                            ("video", "Vídeo"),
                            ("lista_presenca", "Lista de presença"),
                            ("certificado", "Certificado"),
                            ("material", "Material do treinamento"),
                            ("avaliacao", "Avaliação"),
                            ("outro", "Outro documento"),
                        ],
                        default="outro",
                        max_length=30,
                    ),
                ),
                ("arquivo", models.FileField(upload_to="documentos/anexos/")),
                ("data_documento", models.DateField(blank=True, null=True)),
                ("descricao", models.TextField(blank=True)),
                (
                    "created_at",
                    models.DateTimeField(default=django.utils.timezone.now, editable=False),
                ),
                (
                    "documento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="anexos",
                        to="qualidade.documento",
                    ),
                ),
            ],
            options={
                "verbose_name": "Anexo do documento",
                "verbose_name_plural": "Anexos complementares",
                "ordering": ("-created_at", "titulo"),
            },
        ),
        migrations.AlterField(
            model_name="documento",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("procedimento", "Procedimento"),
                    ("instrucao", "Instrução"),
                    ("norma", "Norma"),
                    ("metodo", "Método"),
                    ("formulario", "Formulário"),
                    ("treinamento", "Treinamento de cliente"),
                    ("outros", "Outros"),
                ],
                max_length=30,
            ),
        ),
    ]
