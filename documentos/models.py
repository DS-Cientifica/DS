import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models


class DocumentoArquivo(models.Model):
    class Backend(models.TextChoices):
        LOCAL = "local", "Local"
        MEDIA = "media", "Mídia legada"
        R2 = "r2", "Cloudflare R2"

    class Status(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        SUBSTITUIDO = "substituido", "Substituído"
        CANCELADO = "cancelado", "Cancelado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo_documento = models.CharField(max_length=80, db_index=True)
    nome_original = models.CharField(max_length=255)
    chave_armazenamento = models.CharField(max_length=500, unique=True)
    backend_primario = models.CharField(
        max_length=10,
        choices=Backend.choices,
        default=Backend.LOCAL,
        db_index=True,
    )
    sha256 = models.CharField(max_length=64, db_index=True)
    tamanho = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=150, default="application/octet-stream")
    imutavel = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ATIVO,
        db_index=True,
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="documentos_arquivos",
    )
    object_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    objeto_relacionado = GenericForeignKey("content_type", "object_id")
    documento_anterior = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="substituicoes",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    verificado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-criado_em",)
        verbose_name = "Arquivo documental"
        verbose_name_plural = "Arquivos documentais"
        indexes = [
            models.Index(fields=("content_type", "object_id"), name="doc_objeto_idx"),
            models.Index(fields=("tipo_documento", "status"), name="doc_tipo_status_idx"),
        ]

    def __str__(self):
        return f"{self.tipo_documento} - {self.nome_original}"

    def clean(self):
        super().clean()
        if bool(self.content_type_id) != bool(self.object_id):
            raise ValidationError(
                "O tipo e o identificador do objeto relacionado devem ser informados juntos."
            )
        if self.documento_anterior_id == self.pk:
            raise ValidationError("Um documento não pode substituir a si próprio.")
        if len(self.sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.sha256.lower()
        ):
            raise ValidationError({"sha256": "Informe um hash SHA-256 hexadecimal válido."})

    def save(self, *args, **kwargs):
        if self.pk:
            anterior = type(self).objects.filter(pk=self.pk).first()
            if anterior and anterior.imutavel:
                campos_protegidos = (
                    "tipo_documento",
                    "nome_original",
                    "chave_armazenamento",
                    "backend_primario",
                    "sha256",
                    "tamanho",
                    "mime_type",
                    "content_type_id",
                    "object_id",
                    "documento_anterior_id",
                    "criado_por_id",
                )
                alterados = [
                    campo
                    for campo in campos_protegidos
                    if getattr(anterior, campo) != getattr(self, campo)
                ]
                if alterados:
                    raise ValidationError(
                        "Documento imutável não pode ter seu conteúdo ou identificação "
                        "alterados: " + ", ".join(alterados)
                    )
                if not self.imutavel:
                    raise ValidationError("A imutabilidade de um documento não pode ser removida.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.imutavel:
            raise ValidationError("Documento imutável não pode ser excluído.")
        return super().delete(*args, **kwargs)


class SincronizacaoDocumento(models.Model):
    class Destino(models.TextChoices):
        R2 = "r2", "Cloudflare R2"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PROCESSANDO = "processando", "Processando"
        SINCRONIZADO = "sincronizado", "Sincronizado"
        FALHA = "falha", "Falha"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    documento = models.ForeignKey(
        DocumentoArquivo,
        on_delete=models.PROTECT,
        related_name="sincronizacoes",
    )
    destino = models.CharField(max_length=10, choices=Destino.choices, default=Destino.R2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
        db_index=True,
    )
    tentativas = models.PositiveIntegerField(default=0)
    ultimo_erro = models.TextField(blank=True)
    etag_remoto = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    sincronizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("criado_em",)
        verbose_name = "Sincronização documental"
        verbose_name_plural = "Sincronizações documentais"
        constraints = [
            models.UniqueConstraint(
                fields=("documento", "destino"),
                name="doc_sync_destino_unico",
            )
        ]

    def __str__(self):
        return f"{self.documento} -> {self.get_destino_display()} ({self.get_status_display()})"


class DocumentoVinculo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    documento = models.ForeignKey(
        DocumentoArquivo,
        on_delete=models.PROTECT,
        related_name="vinculos",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="documentos_vinculos",
    )
    object_id = models.CharField(max_length=64, db_index=True)
    objeto_relacionado = GenericForeignKey("content_type", "object_id")
    campo_origem = models.CharField(max_length=100, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("criado_em",)
        verbose_name = "Vínculo documental"
        verbose_name_plural = "Vínculos documentais"
        constraints = [
            models.UniqueConstraint(
                fields=("documento", "content_type", "object_id", "campo_origem"),
                name="doc_vinculo_objeto_unico",
            )
        ]
        indexes = [
            models.Index(fields=("content_type", "object_id"), name="doc_vinculo_obj_idx")
        ]

    def __str__(self):
        return (
            f"{self.documento} -> {self.content_type.app_label}."
            f"{self.content_type.model}:{self.object_id}"
        )
