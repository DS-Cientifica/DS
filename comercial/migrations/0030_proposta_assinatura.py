import django.core.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("comercial", "0029_renomeia_base_contatos"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="proposta",
            name="assinatura_autorizada_em",
            field=models.DateTimeField(
                blank=True,
                editable=False,
                null=True,
                verbose_name="Assinatura autorizada em",
            ),
        ),
        migrations.AddField(
            model_name="proposta",
            name="assinatura_autorizada_por",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="propostas_com_assinatura_autorizada",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Assinatura autorizada por",
            ),
        ),
        migrations.AddField(
            model_name="proposta",
            name="assinatura_cargo",
            field=models.CharField(
                blank=True,
                default="DS Científica",
                max_length=150,
                verbose_name="Cargo/função do signatário",
            ),
        ),
        migrations.AddField(
            model_name="proposta",
            name="assinatura_imagem",
            field=models.FileField(
                blank=True,
                help_text="Envie uma imagem PNG ou JPG, preferencialmente com fundo transparente.",
                null=True,
                upload_to="propostas/assinaturas/",
                validators=[django.core.validators.FileExtensionValidator(("png", "jpg", "jpeg"))],
                verbose_name="Imagem da assinatura",
            ),
        ),
        migrations.AddField(
            model_name="proposta",
            name="assinatura_nome",
            field=models.CharField(
                blank=True,
                default="DIEGO H. A. SALDANHA",
                max_length=150,
                verbose_name="Nome do signatário",
            ),
        ),
        migrations.AddField(
            model_name="proposta",
            name="incluir_assinatura_pdf",
            field=models.BooleanField(
                default=False,
                help_text="Marque somente após autorizar o uso desta assinatura na proposta. A imagem será inserida na impressão, no download e no envio por e-mail.",
                verbose_name="Incluir assinatura nos PDFs",
            ),
        ),
    ]
