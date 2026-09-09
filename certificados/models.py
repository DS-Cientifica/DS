import secrets
import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models


ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def gerar_codigo_curto():
    valor = "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(8))
    return f"{valor[:4]}-{valor[4:]}"


class CertificadoCalibracao(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        EM_REVISAO = "em_revisao", "Em revisão"
        APROVADO = "aprovado", "Aprovado"
        VALIDO = "valido", "Válido"
        VENCIDO = "vencido", "Vencido"
        CANCELADO = "cancelado", "Cancelado"
        SUBSTITUIDO = "substituido", "Substituído"
        SUSPENSO = "suspenso", "Suspenso"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero = models.CharField(max_length=100, unique=True)
    uuid_publico = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    codigo_curto = models.CharField(max_length=9, default=gerar_codigo_curto, unique=True, editable=False)
    calibracao_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="certificados_calibracao")
    calibracao_object_id = models.CharField(max_length=64, db_index=True)
    calibracao = GenericForeignKey("calibracao_content_type", "calibracao_object_id")
    instrumento = models.ForeignKey("calibracao.Instrumento", on_delete=models.PROTECT, related_name="certificados_publicos")
    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.PROTECT, related_name="certificados_publicos")
    documento = models.ForeignKey("documentos.DocumentoArquivo", on_delete=models.PROTECT, null=True, blank=True, related_name="certificados_publicos")
    data_calibracao = models.DateField()
    data_emissao = models.DateField(null=True, blank=True)
    proxima_calibracao = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RASCUNHO, db_index=True)
    revisao = models.PositiveIntegerField(default=0)
    certificado_anterior = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True, related_name="certificado_substituto")
    motivo_status = models.TextField(blank=True)
    publicado = models.BooleanField(default=False)
    permitir_download_publico = models.BooleanField(default=False)
    exibir_cliente = models.BooleanField(default=False)
    exibir_numero_serie = models.BooleanField(default=True)
    exibir_padroes = models.BooleanField(default=True)
    aprovado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="certificados_aprovados")
    aprovado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-criado_em",)
        verbose_name = "Certificado para consulta pública"
        verbose_name_plural = "Certificados para consulta pública"
        indexes = [models.Index(fields=("calibracao_content_type", "calibracao_object_id"), name="cert_calibracao_idx")]
        permissions = [("substituir_certificado", "Pode substituir certificado")]

    def __str__(self):
        return f"{self.numero} - revisão {self.revisao}"

    def clean(self):
        super().clean()
        if self.certificado_anterior_id == self.pk:
            raise ValidationError("Um certificado não pode substituir a si próprio.")
        if self.status == self.Status.SUBSTITUIDO and self.permitir_download_publico:
            raise ValidationError("Certificado substituído não pode permitir download público.")

    @property
    def pode_baixar_publicamente(self):
        return bool(
            self.publicado
            and self.permitir_download_publico
            and self.documento_id
            and self.status in {self.Status.APROVADO, self.Status.VALIDO, self.Status.VENCIDO}
        )


class PadraoUtilizado(models.Model):
    class Situacao(models.TextChoices):
        VALIDO = "valido_na_data", "Válido na data de uso"
        VENCIDO = "vencido_na_data", "Vencido na data de uso"
        SEM_CERTIFICADO = "sem_certificado", "Certificado não localizado"
        SUSPENSO = "suspenso", "Padrão suspenso"

    certificado = models.ForeignKey(CertificadoCalibracao, on_delete=models.PROTECT, related_name="padroes_utilizados")
    padrao = models.ForeignKey("calibracao.Padrao", on_delete=models.PROTECT, related_name="usos_em_certificados")
    documento = models.ForeignKey("documentos.DocumentoArquivo", on_delete=models.PROTECT, null=True, blank=True, related_name="usos_como_padrao")
    data_utilizacao = models.DateField()
    codigo = models.CharField(max_length=50)
    descricao = models.CharField(max_length=255)
    numero_certificado = models.CharField(max_length=100, blank=True)
    laboratorio_emitente = models.CharField(max_length=150, blank=True)
    data_calibracao = models.DateField(null=True, blank=True)
    validade = models.DateField(null=True, blank=True)
    situacao_na_data = models.CharField(max_length=30, choices=Situacao.choices)
    registrado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("codigo",)
        constraints = [models.UniqueConstraint(fields=("certificado", "padrao"), name="cert_padrao_unico")]
        verbose_name = "Padrão utilizado no certificado"
        verbose_name_plural = "Padrões utilizados nos certificados"

    def __str__(self):
        return f"{self.certificado.numero} - {self.codigo}"


class RevisaoCertificado(models.Model):
    certificado = models.ForeignKey(CertificadoCalibracao, on_delete=models.PROTECT, related_name="historico")
    acao = models.CharField(max_length=30)
    justificativa = models.TextField()
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-criado_em",)
        verbose_name = "Histórico do certificado"
        verbose_name_plural = "Históricos dos certificados"
