import uuid
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from clientes.models import Cliente


# =========================
# CATEGORIA FINANCEIRA
# =========================
class CategoriaFinanceira(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField("Código", max_length=20, unique=True, blank=True, null=True)
    nome = models.CharField("Nome", max_length=100, unique=True)
    descricao = models.TextField("Descrição", blank=True)

    def gerar_codigo(self):
        ultimo = CategoriaFinanceira.objects.exclude(codigo__isnull=True).exclude(codigo="").order_by("-codigo").first()

        if ultimo and ultimo.codigo:
            try:
                numero = int(ultimo.codigo.split("-")[1]) + 1
            except (IndexError, ValueError):
                numero = CategoriaFinanceira.objects.exclude(pk=self.pk).count() + 1
        else:
            numero = 1

        return f"CAT-{numero:04d}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            while True:
                codigo = self.gerar_codigo()
                if not CategoriaFinanceira.objects.filter(codigo=codigo).exclude(pk=self.pk).exists():
                    self.codigo = codigo
                    break

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Categoria Financeira"
        verbose_name_plural = "Categorias Financeiras"
        ordering = ("codigo", "nome")

    def __str__(self):
        return f"{self.codigo} - {self.nome}" if self.codigo else self.nome


# =========================
# CONTAS A PAGAR
# =========================
class ContaPagar(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    descricao = models.CharField(max_length=200)
    fornecedor = models.CharField(max_length=200)

    categoria = models.ForeignKey(
        CategoriaFinanceira,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contas_pagar"
    )

    valor = models.DecimalField(max_digits=12, decimal_places=2)
    vencimento = models.DateField()
    data_pagamento = models.DateField(null=True, blank=True)

    comprovante = models.FileField(
        upload_to="financeiro/contas_pagar/",
        null=True,
        blank=True
    )

    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("pago", "Pago"),
        ("atrasado", "Atrasado"),
        ("cancelado", "Cancelado"),
    ]

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="pendente"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conta a Pagar"
        verbose_name_plural = "Contas a Pagar"
        ordering = ("vencimento",)

    def save(self, *args, **kwargs):
        if self.status not in ("pago", "cancelado") and self.vencimento < timezone.now().date():
            self.status = "atrasado"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.descricao} - {self.fornecedor}"


# =========================
# CONTAS A RECEBER
# =========================
class ContaReceber(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    proposta = models.ForeignKey(
        "comercial.Proposta",
        verbose_name="Proposta aprovada",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contas_receber"
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="contas_receber",
        blank=True
    )

    descricao = models.CharField("Descrição", max_length=200, blank=True)

    valor = models.DecimalField("Valor", max_digits=12, decimal_places=2, default=0, blank=True)
    vencimento = models.DateField("Vencimento")
    data_recebimento = models.DateField("Data de recebimento", null=True, blank=True)

    comprovante = models.FileField(
        upload_to="financeiro/contas_receber/",
        null=True,
        blank=True
    )

    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("recebido", "Recebido"),
        ("atrasado", "Atrasado"),
        ("cancelado", "Cancelado"),
    ]

    status = models.CharField(
        "Status",
        max_length=10,
        choices=STATUS_CHOICES,
        default="pendente"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conta a Receber"
        verbose_name_plural = "Contas a Receber"
        ordering = ("vencimento",)

    def clean(self):
        if not self.cliente_id and not self.proposta_id:
            raise ValidationError("Informe um cliente ou uma proposta aprovada.")

        if not self.proposta_id and self.valor in (None, Decimal("0")):
            raise ValidationError("Informe o valor da conta a receber.")

    def save(self, *args, **kwargs):
        if self.proposta_id:
            self.cliente = self.proposta.cliente
            self.valor = self.proposta.total

            if not self.descricao:
                self.descricao = f"Proposta {self.proposta.codigo}"

        if self.status not in ("recebido", "cancelado") and self.vencimento < timezone.now().date():
            self.status = "atrasado"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente.razao_social} - R$ {self.valor}"


# =========================
# IMPOSTOS
# =========================
class Imposto(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    nome = models.CharField(max_length=100)

    competencia = models.CharField(
        max_length=7,
        help_text="Formato MM/AAAA (ex: 01/2026)"
    )

    valor = models.DecimalField(max_digits=12, decimal_places=2)
    vencimento = models.DateField()

    comprovante = models.FileField(
        upload_to="financeiro/impostos/",
        null=True,
        blank=True
    )

    pago = models.BooleanField(default=False)
    data_pagamento = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Imposto"
        verbose_name_plural = "Impostos"
        ordering = ("-vencimento",)

    def __str__(self):
        return f"{self.nome} - {self.competencia}"
