from datetime import date

from dateutil.relativedelta import relativedelta
from django.db import models
from django.utils import timezone


class Documento(models.Model):
    TIPO_CHOICES = (
        ("procedimento", "Procedimento"),
        ("instrucao", "Instrução"),
        ("norma", "Norma"),
        ("metodo", "Método"),
        ("formulario", "Formulário"),
        ("treinamento", "Treinamento de cliente"),
        ("outros", "Outros"),
    )

    STATUS_CHOICES = (
        ("em_elaboracao", "Em elaboração"),
        ("em_revisao", "Em revisão"),
        ("vigente", "Vigente"),
        ("obsoleto", "Obsoleto"),
    )

    codigo = models.CharField(max_length=50, blank=True, default="")
    titulo = models.CharField(max_length=200)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    revisao = models.CharField(max_length=10, default="REV.01")
    data_emissao = models.DateField(blank=True, null=True, default=None)
    data_ultima_revisao = models.DateField(blank=True, null=True, default=None)
    prazo_revisao_meses = models.PositiveIntegerField(default=12)
    aprovado_por = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="vigente")
    responsavel = models.CharField(max_length=100, blank=True, default="")
    area = models.CharField(max_length=100, blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    obsoleto_motivo = models.TextField(blank=True, default="")
    arquivo = models.FileField(upload_to="documentos/")
    arquivo_rascunho_pdf = models.FileField(upload_to="documentos/rascunhos/", blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ("titulo", "codigo")

    def __str__(self):
        if self.codigo:
            return f"{self.codigo} - {self.titulo}"
        return self.titulo

    def save(self, *args, **kwargs):
        creating = self.pk is None
        revisao_anterior = None

        if not self.codigo:
            self.codigo = ""
        if not self.revisao:
            self.revisao = "REV.01"
        if not self.data_ultima_revisao and self.data_emissao:
            self.data_ultima_revisao = self.data_emissao
        if not self.status:
            self.status = "vigente"

        if not creating:
            revisao_anterior = (
                Documento.objects.filter(pk=self.pk).values_list("revisao", flat=True).first()
            )

        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

        if creating:
            DocumentoRevisao.objects.get_or_create(
                documento=self,
                revisao=self.revisao,
                defaults={
                    "data": self.data_ultima_revisao or date.today(),
                    "alteracao": (
                        "Documento cadastrado em elaboração"
                        if self.status == "em_elaboracao"
                        else "Documento criado"
                    ),
                    "responsavel": self.aprovado_por or self.responsavel or "DS Científica",
                    "status": self.status,
                },
            )
        elif revisao_anterior and revisao_anterior != self.revisao:
            DocumentoRevisao.objects.create(
                documento=self,
                revisao=self.revisao,
                data=self.data_ultima_revisao,
                alteracao=f"Revisão alterada de {revisao_anterior} para {self.revisao}",
                responsavel=self.aprovado_por,
                status=self.status,
            )

    @property
    def data_proxima_revisao(self):
        if not self.data_ultima_revisao:
            return None
        return self.data_ultima_revisao + relativedelta(months=self.prazo_revisao_meses)

    @property
    def vencimento_em_30_dias(self):
        if not self.data_proxima_revisao:
            return False
        hoje = date.today()
        limite = hoje + relativedelta(days=30)
        return hoje <= self.data_proxima_revisao <= limite

    @property
    def vencido(self):
        if not self.data_proxima_revisao:
            return False
        return self.data_proxima_revisao < date.today()


class DocumentoRevisao(models.Model):
    documento = models.ForeignKey(
        Documento,
        on_delete=models.CASCADE,
        related_name="historico_revisoes",
    )
    revisao = models.CharField(max_length=10)
    data = models.DateField(default=date(2026, 1, 1))
    alteracao = models.TextField()
    responsavel = models.CharField(max_length=100, default="DS Científica")
    status = models.CharField(max_length=20, choices=Documento.STATUS_CHOICES, default="vigente")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Histórico de revisão"
        verbose_name_plural = "Históricos de revisão"
        ordering = ("-data", "-created_at")

    def __str__(self):
        return f"{self.documento} - {self.revisao}"


class DocumentoAnexo(models.Model):
    TIPO_CHOICES = (
        ("foto", "Foto"),
        ("video", "Vídeo"),
        ("lista_presenca", "Lista de presença"),
        ("certificado", "Certificado"),
        ("material", "Material do treinamento"),
        ("avaliacao", "Avaliação"),
        ("outro", "Outro documento"),
    )

    documento = models.ForeignKey(
        Documento,
        on_delete=models.CASCADE,
        related_name="anexos",
    )
    titulo = models.CharField(max_length=150, blank=True)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default="outro")
    arquivo = models.FileField(upload_to="documentos/anexos/")
    data_documento = models.DateField(null=True, blank=True)
    descricao = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Anexo do documento"
        verbose_name_plural = "Anexos complementares"
        ordering = ("-created_at", "titulo")

    def __str__(self):
        return self.titulo or self.arquivo.name
