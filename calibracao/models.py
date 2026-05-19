import uuid
from datetime import date
from django.core.exceptions import ValidationError
from django.db import models
from dateutil.relativedelta import relativedelta
from clientes.models import Cliente


# =========================
# INSTRUMENTO
# =========================
class Instrumento(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = (
        ("ativo", "Ativo"),
        ("inativo", "Inativo"),
        ("manutencao", "Em Manutenção"),
    )

    codigo = models.CharField(max_length=50, unique=True)
    descricao = models.CharField(max_length=255)

    marca = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    local_instalacao = models.CharField(max_length=200, blank=True)

    numero_serie = models.CharField(max_length=100, blank=True, null=True)

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="instrumentos"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ativo"
    )

    proxima_calibracao = models.DateField(blank=True, null=True)
    ativo = models.BooleanField(default=True)

    # 📎 ANEXO
    nome_anexo = models.CharField(max_length=200, blank=True)

    anexo = models.FileField(
        upload_to='instrumentos/',
        null=True,
        blank=True
    )

    # 🔬 METROLOGIA
    metodo_calibracao = models.ForeignKey(
        "qualidade.Documento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instrumentos"
    )

    padroes = models.ManyToManyField(
        "calibracao.Padrao",
        blank=True,
        related_name="instrumentos"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.codigo} - {self.descricao}"


# =========================
# INSTRUMENTO TÉCNICO
# =========================
class InstrumentoTecnico(models.Model):

    instrumento = models.OneToOneField(
        Instrumento,
        on_delete=models.CASCADE,
        related_name="tecnico"
    )

    faixa_medicao = models.CharField(max_length=100, blank=True)
    unidade = models.CharField(max_length=50, blank=True)
    classe = models.CharField(max_length=50, blank=True)
    observacoes = models.TextField(blank=True)

    def __str__(self):
        return f"Técnico - {self.instrumento.codigo}"


# =========================
# ORDEM DE SERVIÇO
# =========================
class OrdemServico(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = (
        ("aberta", "Aberta"),
        ("em_andamento", "Em andamento"),
        ("concluida", "Concluída"),
        ("cancelada", "Cancelada"),
    )

    numero = models.CharField("Número", max_length=50)

    proposta = models.ForeignKey(
        "comercial.Proposta",
        verbose_name="Proposta",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ordens_servico"
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="ordens_servico",
        blank=True
    )

    instrumentos = models.ManyToManyField(
        Instrumento,
        verbose_name="Equipamentos",
        blank=True,
        related_name="ordens_servico"
    )

    data_abertura = models.DateField("Data de abertura", auto_now_add=True)
    data_conclusao = models.DateField("Data de conclusão", blank=True, null=True)

    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default="aberta"
    )

    anexo = models.FileField(
        upload_to='ordens_servico/',
        null=True,
        blank=True
    )

    def clean(self):
        if not self.cliente_id and not self.proposta_id:
            raise ValidationError("Informe um cliente ou uma proposta.")

    def save(self, *args, **kwargs):
        if self.proposta_id and not self.cliente_id:
            self.cliente = self.proposta.cliente

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Ordem de Serviço"
        verbose_name_plural = "Ordens de Serviço"

    def __str__(self):
        return f"OS {self.numero} - {self.cliente.razao_social}"


# =========================
# PADRÃO
# =========================
class Padrao(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = (
        ("valido", "Válido"),
        ("vencido", "Vencido"),
        ("suspenso", "Suspenso"),
    )

    codigo = models.CharField(max_length=50, unique=True)
    descricao = models.CharField(max_length=255)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="valido")

    vencimento = models.DateField()

    certificado = models.FileField(
        upload_to='padroes/',
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.codigo} - {self.descricao}"


# =========================
# PERIODICIDADE
# =========================
class Periodicidade(models.Model):

    TIPO_CHOICES = (
        ("calibracao", "Calibração"),
        ("manutencao", "Manutenção"),
    )

    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.CASCADE,
        related_name="periodicidades"
    )

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)

    intervalo_meses = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.instrumento.codigo} - {self.get_tipo_display()}"


# =========================
# CALIBRAÇÃO
# =========================
class Calibracao(models.Model):

    STATUS_CHOICES = (
        ("aberta", "Aberta"),
        ("concluida", "Concluída"),
        ("cancelada", "Cancelada"),
    )

    RESULTADO_CHOICES = (
        ("aprovado", "Aprovado"),
        ("ressalva", "Aprovado com ressalva"),
        ("reprovado", "Reprovado"),
    )

    LOCAL_CHOICES = (
        ("laboratorio", "DS Científica"),
        ("in_loco", "In Loco"),
    )

    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.PROTECT,
        related_name="calibracoes"
    )

    data_calibracao = models.DateField()
    validade = models.DateField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="aberta")
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES, default="aprovado")

    # 📎 CERTIFICADO
    certificado_numero = models.CharField(max_length=100, blank=True)
    certificado_arquivo = models.FileField(upload_to='calibracoes/', null=True, blank=True)
    empresa_emissora = models.CharField(max_length=200, blank=True)

    # 📏 METODOLOGIA
    metodo = models.TextField(blank=True)
    padroes = models.TextField(blank=True)

    # 🌡 AMBIENTE
    temperatura = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    umidade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # 📍 EXECUÇÃO
    local_calibracao = models.CharField(max_length=20, choices=LOCAL_CHOICES, default="laboratorio")
    equipamentos_auxiliares = models.TextField(blank=True)

    observacoes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):

        # CALCULAR VALIDADE AUTOMÁTICA
        periodicidade = self.instrumento.periodicidades.filter(
            tipo="calibracao"
        ).first()

        if periodicidade and self.data_calibracao:
            self.validade = (
                self.data_calibracao +
                relativedelta(months=periodicidade.intervalo_meses)
            )

        # PUXAR MÉTODO E PADRÕES
        if self.instrumento:

            if not self.metodo and self.instrumento.metodo_calibracao:
                self.metodo = self.instrumento.metodo_calibracao.titulo

            if not self.padroes:
                padroes = self.instrumento.padroes.all()
                self.padroes = ", ".join([p.codigo for p in padroes])

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.instrumento.codigo} - {self.data_calibracao}"

# =========================
# ANEXOS DA CALIBRAÇÃO
# =========================
class CalibracaoAnexo(models.Model):

    calibracao = models.ForeignKey(
        'Calibracao',
        on_delete=models.CASCADE,
        related_name='anexos'
    )

    arquivo = models.FileField(
        upload_to='calibracao/anexos/'
    )

    descricao = models.CharField(
        max_length=200,
        blank=True
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Anexo - {self.calibracao}"
