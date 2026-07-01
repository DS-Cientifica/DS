import uuid
from decimal import Decimal

from django.db import models

from qualidade.models import Documento


class CargoFuncao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=20, unique=True, blank=True)
    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "RH - Cargo e fun\u00e7\u00e3o"
        verbose_name_plural = "RH - Cargos e fun\u00e7\u00f5es"
        ordering = ("nome",)

    def __str__(self):
        return self.nome

    def gerar_codigo(self):
        numero = CargoFuncao.objects.exclude(codigo="").count() + 1
        return f"CAR-{numero:04d}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.gerar_codigo()
        super().save(*args, **kwargs)


class Colaborador(models.Model):
    TIPO_CHOICES = (
        ("socio", "S\u00f3cio"),
        ("clt", "CLT"),
        ("pj", "PJ"),
        ("terceiro", "Terceiro"),
        ("autonomo", "Aut\u00f4nomo"),
    )

    STATUS_CHOICES = (
        ("ativo", "Ativo"),
        ("inativo", "Inativo"),
        ("afastado", "Afastado"),
        ("ferias", "F\u00e9rias"),
        ("bloqueado", "Bloqueado"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=20, unique=True, blank=True)
    nome = models.CharField(max_length=150)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="clt")
    cargo = models.ForeignKey(
        CargoFuncao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="colaboradores",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ativo")
    telefone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    cidade_base = models.CharField(max_length=120, blank=True)
    valor_hora_interna = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    valor_hora_venda = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    custo_diaria = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    disponivel_campo = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "RH - Colaborador"
        verbose_name_plural = "RH - Colaboradores"
        ordering = ("nome",)

    def __str__(self):
        return self.nome

    def gerar_codigo(self):
        numero = Colaborador.objects.exclude(codigo="").count() + 1
        return f"COL-{numero:04d}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.gerar_codigo()
        super().save(*args, **kwargs)


class ColaboradorAnexo(models.Model):
    TIPO_CHOICES = (
        ("documento_pessoal", "Documento pessoal"),
        ("aso", "ASO"),
        ("contrato", "Contrato"),
        ("certificado", "Certificado"),
        ("treinamento", "Evidencia de treinamento"),
        ("comprovante", "Comprovante"),
        ("foto", "Foto"),
        ("outro", "Outro"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    colaborador = models.ForeignKey(Colaborador, on_delete=models.CASCADE, related_name="anexos")
    titulo = models.CharField(max_length=150)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default="outro")
    arquivo = models.FileField(upload_to="gestao/colaboradores/anexos/")
    descricao = models.TextField(blank=True)
    data_documento = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "RH - Anexo do colaborador"
        verbose_name_plural = "RH - Anexos do colaborador"
        ordering = ("-created_at", "titulo")

    def __str__(self):
        return f"{self.colaborador.nome} - {self.titulo}"


class CompetenciaTecnica(models.Model):
    NIVEL_CHOICES = (
        ("basico", "B\u00e1sico"),
        ("intermediario", "Intermedi\u00e1rio"),
        ("avancado", "Avan\u00e7ado"),
        ("especialista", "Especialista"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    colaborador = models.ForeignKey(Colaborador, on_delete=models.CASCADE, related_name="competencias")
    grandeza = models.CharField(max_length=120)
    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES, default="basico")
    autorizado_executar = models.BooleanField(default=True)
    necessita_supervisao = models.BooleanField(default=False)
    data_habilitacao = models.DateField(null=True, blank=True)
    validade_habilitacao = models.DateField(null=True, blank=True)
    documento_vinculado = models.ForeignKey(
        Documento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="competencias_tecnicas",
    )
    observacoes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "RH - Compet\u00eancia t\u00e9cnica"
        verbose_name_plural = "RH - Compet\u00eancias t\u00e9cnicas"
        ordering = ("colaborador__nome", "grandeza")
        constraints = [
            models.UniqueConstraint(fields=("colaborador", "grandeza"), name="unique_competencia_por_colaborador")
        ]

    def __str__(self):
        return f"{self.colaborador.nome} - {self.grandeza}"


class Treinamento(models.Model):
    TIPO_CHOICES = (
        ("interno", "Interno"),
        ("externo", "Externo"),
    )

    STATUS_CHOICES = (
        ("planejado", "Planejado"),
        ("em_andamento", "Em andamento"),
        ("concluido", "Conclu\u00eddo"),
        ("vencido", "Vencido"),
        ("cancelado", "Cancelado"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=20, unique=True, blank=True)
    colaborador = models.ForeignKey(Colaborador, on_delete=models.CASCADE, related_name="treinamentos")
    treinamento = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="interno")
    instrutor = models.CharField(max_length=150, blank=True)
    carga_horaria = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    data = models.DateField(null=True, blank=True)
    validade = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planejado")
    evidencia = models.FileField(upload_to="gestao/treinamentos/", blank=True, null=True)
    observacoes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "RH - Treinamento"
        verbose_name_plural = "RH - Treinamentos"
        ordering = ("-data", "treinamento")

    def __str__(self):
        return f"{self.codigo} - {self.treinamento}"

    def gerar_codigo(self):
        numero = Treinamento.objects.exclude(codigo="").count() + 1
        return f"TRE-{numero:04d}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.gerar_codigo()
        super().save(*args, **kwargs)
