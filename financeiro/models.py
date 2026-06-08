import uuid

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
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

        help_text="Formato MM/AAAA (ex.: 01/2026)"

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



# =========================
# PEDIDO DE COMPRA
# =========================


def _money(value):
    return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class PedidoCompra(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    fornecedor = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="pedidos_compra",
        verbose_name="Fornecedor",
    )

    responsavel_compra = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedidos_compra",
        verbose_name="Responsável pela compra",
    )

    numero_pedido = models.CharField(
        "Número do pedido",
        max_length=50,
        unique=True,
        blank=True,
    )

    data_emissao = models.DateField("Data de emissão", auto_now_add=True)
    prazo_entrega = models.DateField("Prazo de entrega", null=True, blank=True)
    condicao_pagamento = models.CharField("Condição de pagamento", max_length=200, blank=True)
    observacoes = models.TextField("Observações", blank=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    desconto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    frete = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outros_custos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "purchase_orders"
        verbose_name = "Pedido de Compra"
        verbose_name_plural = "Pedidos de Compra"
        ordering = ("-data_emissao", "-created_at")

    def gerar_numero(self):
        ano = datetime.now().strftime("%y")
        numero = PedidoCompra.objects.count() + 1
        return f"PC-{numero:04d}/{ano}"

    def atualizar_totais(self):
        subtotal = Decimal("0")
        desconto = Decimal("0")

        for item in self.itens.all():
            bruto = _money(item.quantidade) * _money(item.valor_unitario)
            subtotal += bruto
            desconto += bruto - _money(item.valor_total)

        self.subtotal = _money(subtotal)
        self.desconto = _money(desconto)
        self.total = _money(self.subtotal - self.desconto + _money(self.frete) + _money(self.outros_custos))
        super().save(update_fields=["subtotal", "desconto", "frete", "outros_custos", "total", "updated_at"])

    def save(self, *args, **kwargs):
        if not self.numero_pedido:
            self.numero_pedido = self.gerar_numero()
        super().save(*args, **kwargs)
        self.atualizar_totais()

    def __str__(self):
        return self.numero_pedido


class PedidoCompraItem(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    pedido = models.ForeignKey(
        PedidoCompra,
        on_delete=models.CASCADE,
        related_name="itens",
        verbose_name="Pedido",
    )

    produto = models.ForeignKey(
        "comercial.ProdutoServico",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedidos_compra_itens",
        verbose_name="Produto/Serviço",
    )

    codigo = models.CharField("Código", max_length=50, blank=True)
    descricao = models.CharField("Descrição", max_length=255)
    quantidade = models.DecimalField("Quantidade", max_digits=12, decimal_places=2, default=1)
    unidade = models.CharField("Unidade", max_length=20, default="UN")
    valor_unitario = models.DecimalField("Valor unitário", max_digits=12, decimal_places=2, default=0)
    desconto = models.DecimalField("Desconto (%)", max_digits=5, decimal_places=2, default=0)
    valor_total = models.DecimalField("Valor total", max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = "purchase_order_items"
        ordering = ("id",)
        verbose_name = "Item do Pedido de Compra"
        verbose_name_plural = "Itens do Pedido de Compra"

    def save(self, *args, **kwargs):
        if self.produto:
            if not self.codigo:
                self.codigo = self.produto.codigo
            if not self.descricao:
                self.descricao = self.produto.nome
            if not self.valor_unitario:
                self.valor_unitario = self.produto.preco_venda

        bruto = _money(self.quantidade) * _money(self.valor_unitario)
        desconto_valor = bruto * (_money(self.desconto) / Decimal("100"))
        self.valor_total = _money(bruto - desconto_valor)

        super().save(*args, **kwargs)

        if self.pedido_id:
            self.pedido.atualizar_totais()

    def delete(self, *args, **kwargs):
        pedido = self.pedido
        super().delete(*args, **kwargs)
        if pedido:
            pedido.atualizar_totais()

    def __str__(self):
        return self.descricao
