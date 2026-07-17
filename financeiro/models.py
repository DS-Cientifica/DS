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

    pedido_compra = models.OneToOneField(
        "financeiro.PedidoCompra",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="conta_pagar_gerada",
        verbose_name="Pedido de compra",
    )



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
    vencimento_pagamento = models.DateField("Vencimento da conta a pagar", null=True, blank=True)
    condicao_pagamento = models.CharField("Condição de pagamento", max_length=200, blank=True)
    observacoes = models.TextField("Observações", blank=True)
    anexo = models.FileField(
        "Anexo",
        upload_to="financeiro/pedidos_compra/",
        null=True,
        blank=True,
    )
    incluir_nome_anexo_pdf = models.BooleanField(
        "Incluir nome do anexo no PDF",
        default=False,
    )

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
        self.sincronizar_conta_pagar()

    def _descricao_conta_pagar(self):
        return f"Pedido de Compra {self.numero_pedido}"

    def _fornecedor_conta_pagar(self):
        return self.fornecedor.razao_social or self.fornecedor.nome_empresa or str(self.fornecedor)

    def _vencimento_conta_pagar(self):
        return self.vencimento_pagamento or self.prazo_entrega or self.data_emissao or timezone.now().date()

    def sincronizar_conta_pagar(self):
        conta = getattr(self, "conta_pagar_gerada", None)
        if self.total <= Decimal("0"):
            if conta and conta.status in {"pendente", "atrasado", "cancelado"} and not conta.data_pagamento:
                conta.delete()
            return

        defaults = {
            "descricao": self._descricao_conta_pagar(),
            "fornecedor": self._fornecedor_conta_pagar(),
            "valor": self.total,
            "vencimento": self._vencimento_conta_pagar(),
        }

        if conta:
            for field, value in defaults.items():
                setattr(conta, field, value)
            conta.save()
            return

        ContaPagar.objects.create(
            pedido_compra=self,
            status="pendente",
            **defaults,
        )

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


class NotaFiscal(models.Model):
    TIPO_NOTA_CHOICES = (
        ("venda_produto", "Venda de Produto"),
        ("prestacao_servico", "Prestacao de Servico"),
        ("venda_produto_servico", "Venda de Produto + Servico"),
        ("entrada_compra", "Entrada / Compra"),
        ("devolucao_compra", "Devolucao de Compra"),
        ("devolucao_venda", "Devolucao de Venda"),
        ("remessa_conserto", "Remessa para Conserto"),
        ("retorno_conserto", "Retorno de Conserto"),
        ("remessa_calibracao", "Remessa para Calibracao"),
        ("retorno_calibracao", "Retorno de Calibracao"),
        ("simples_remessa", "Simples Remessa"),
        ("entrada_equipamento_cliente", "Entrada de Equipamento de Cliente"),
        ("saida_devolucao_equipamento_cliente", "Saida / Devolucao de Equipamento ao Cliente"),
        ("documento_interno_sem_nf", "Documento Interno sem Nota Fiscal"),
        ("outro", "Outro"),
    )

    STATUS_CHOICES = (
        ("rascunho", "Rascunho"),
        ("cadastrada", "Cadastrada"),
        ("emitida_externa", "Emitida em plataforma externa"),
        ("recebida", "Recebida"),
        ("cancelada", "Cancelada"),
        ("substituida", "Substituida"),
        ("aguardando_pdf", "Aguardando PDF"),
        ("aguardando_xml", "Aguardando XML"),
        ("finalizada", "Finalizada"),
    )

    STATUS_OPERACIONAL_CHOICES = (
        ("nao_aplicavel", "Nao aplicavel"),
        ("aguardando_envio", "Aguardando envio"),
        ("em_transito", "Em transito"),
        ("recebido", "Recebido"),
        ("em_analise", "Em analise"),
        ("em_manutencao", "Em manutencao"),
        ("em_calibracao", "Em calibracao"),
        ("aguardando_retorno", "Aguardando retorno"),
        ("retornado", "Retornado"),
        ("finalizado", "Finalizado"),
        ("cancelado", "Cancelado"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo_nota = models.CharField("Tipo da nota", max_length=50, choices=TIPO_NOTA_CHOICES)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notas_fiscais",
        verbose_name="Cliente",
    )
    fornecedor_nome = models.CharField("Fornecedor", max_length=255, blank=True)
    fornecedor_cnpj = models.CharField("CNPJ do fornecedor", max_length=20, blank=True)
    numero = models.CharField("Numero", max_length=50, blank=True)
    serie = models.CharField("Serie", max_length=50, blank=True)
    chave_acesso = models.CharField("Chave de acesso", max_length=80, blank=True)
    natureza_operacao = models.CharField("Natureza da operacao", max_length=255, blank=True)
    cfop = models.CharField("CFOP", max_length=20, blank=True)
    codigo_servico = models.CharField("Codigo do servico", max_length=50, blank=True)
    municipio_emissao = models.CharField("Municipio de emissao", max_length=120, blank=True)
    data_emissao = models.DateField("Data de emissao", null=True, blank=True)
    data_entrada_saida = models.DateField("Data de entrada/saida", null=True, blank=True)
    data_vencimento = models.DateField("Data de vencimento", null=True, blank=True)
    valor_total = models.DecimalField("Valor total", max_digits=12, decimal_places=2, default=0)
    status = models.CharField("Status", max_length=30, choices=STATUS_CHOICES, default="rascunho")
    status_operacional = models.CharField(
        "Status operacional",
        max_length=30,
        choices=STATUS_OPERACIONAL_CHOICES,
        default="nao_aplicavel",
    )
    proposta = models.ForeignKey(
        "comercial.Proposta",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notas_fiscais",
        verbose_name="Proposta",
    )
    pedido_compra = models.ForeignKey(
        "financeiro.PedidoCompra",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notas_fiscais",
        verbose_name="Pedido de compra",
    )
    conta_receber = models.ForeignKey(
        "financeiro.ContaReceber",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notas_fiscais",
        verbose_name="Conta a receber",
    )
    conta_pagar = models.ForeignKey(
        "financeiro.ContaPagar",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notas_fiscais",
        verbose_name="Conta a pagar",
    )
    calibracao = models.ForeignKey(
        "calibracao.Calibracao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notas_fiscais",
        verbose_name="Calibracao",
    )
    nota_referenciada = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notas_relacionadas",
        verbose_name="Nota referenciada",
    )
    motivo = models.TextField("Motivo", blank=True)
    observacoes = models.TextField("Observacoes", blank=True)
    pdf = models.FileField("PDF / DANFE", upload_to="financeiro/notas_fiscais/pdf/", null=True, blank=True)
    xml = models.FileField("XML", upload_to="financeiro/notas_fiscais/xml/", null=True, blank=True)
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notas_fiscais_criadas",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Nota Fiscal"
        verbose_name_plural = "Notas Fiscais"
        ordering = ("-data_emissao", "-criado_em")

    def __str__(self):
        referencia = self.cliente.razao_social if self.cliente_id else (self.fornecedor_nome or "Sem vinculo")
        numero = self.numero or "S/N"
        return f"NF {numero} - {referencia} - {self.get_tipo_nota_display()} - R$ {self.valor_total}"

    @property
    def tem_pdf(self):
        return bool(self.pdf)

    @property
    def tem_xml(self):
        return bool(self.xml)

    @property
    def esta_pendente_arquivo(self):
        return not self.tem_pdf or not self.tem_xml

    @property
    def eh_remessa(self):
        return self.tipo_nota in {"remessa_conserto", "remessa_calibracao", "simples_remessa"}

    @property
    def eh_retorno(self):
        return self.tipo_nota in {"retorno_conserto", "retorno_calibracao"}

    @property
    def eh_devolucao(self):
        return self.tipo_nota in {"devolucao_compra", "devolucao_venda"}

    def atualizar_valor_total(self):
        total_itens = self.itens.aggregate(total=Sum("valor_total"))["total"]
        self.valor_total = _money(total_itens or 0)
        super().save(update_fields=["valor_total", "atualizado_em"])


class ItemNotaFiscal(models.Model):
    TIPO_ITEM_CHOICES = (
        ("produto", "Produto"),
        ("servico", "Servico"),
        ("equipamento_cliente", "Equipamento de Cliente"),
        ("peca", "Peca"),
        ("insumo", "Insumo"),
        ("outro", "Outro"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nota_fiscal = models.ForeignKey(
        NotaFiscal,
        on_delete=models.CASCADE,
        related_name="itens",
        verbose_name="Nota fiscal",
    )
    tipo_item = models.CharField("Tipo do item", max_length=30, choices=TIPO_ITEM_CHOICES, default="produto")
    descricao = models.CharField("Descricao", max_length=255)
    codigo_interno = models.CharField("Codigo interno", max_length=80, blank=True)
    quantidade = models.DecimalField("Quantidade", max_digits=12, decimal_places=2, default=1)
    unidade = models.CharField("Unidade", max_length=20, default="UN")
    valor_unitario = models.DecimalField("Valor unitario", max_digits=12, decimal_places=2, default=0)
    valor_total = models.DecimalField("Valor total", max_digits=12, decimal_places=2, default=0)
    cfop = models.CharField("CFOP", max_length=20, blank=True)
    ncm = models.CharField("NCM", max_length=30, blank=True)
    codigo_servico = models.CharField("Codigo do servico", max_length=50, blank=True)
    marca = models.CharField("Marca", max_length=120, blank=True)
    modelo = models.CharField("Modelo", max_length=120, blank=True)
    numero_serie = models.CharField("Numero de serie", max_length=120, blank=True)
    patrimonio = models.CharField("Patrimonio", max_length=120, blank=True)
    observacoes = models.TextField("Observacoes", blank=True)

    class Meta:
        verbose_name = "Item da Nota Fiscal"
        verbose_name_plural = "Itens da Nota Fiscal"
        ordering = ("id",)

    def save(self, *args, **kwargs):
        self.valor_total = _money(_money(self.quantidade) * _money(self.valor_unitario))
        super().save(*args, **kwargs)
        if self.nota_fiscal_id:
            self.nota_fiscal.atualizar_valor_total()

    def delete(self, *args, **kwargs):
        nota_fiscal = self.nota_fiscal
        super().delete(*args, **kwargs)
        if nota_fiscal:
            nota_fiscal.atualizar_valor_total()

    def __str__(self):
        return self.descricao


class AnexoNotaFiscal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nota_fiscal = models.ForeignKey(
        NotaFiscal,
        on_delete=models.CASCADE,
        related_name="anexos",
        verbose_name="Nota fiscal",
    )
    arquivo = models.FileField("Arquivo", upload_to="financeiro/notas_fiscais/anexos/")
    descricao = models.CharField("Descricao", max_length=255, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Anexo da Nota Fiscal"
        verbose_name_plural = "Anexos da Nota Fiscal"
        ordering = ("-criado_em",)

    def __str__(self):
        return self.descricao or str(self.arquivo)
