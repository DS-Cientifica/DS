import uuid
from datetime import datetime
from django.db import models
from django.db.models import Sum
from clientes.models import Cliente

# =========================
# PRODUTO / SERVIÇO
# =========================

class ProdutoServico(models.Model):

    TIPO_CHOICES = (
        ("calibracao", "Calibração"),
        ("produto", "Produto"),
        ("manutencao", "Manutenção"),
        ("qualificacao", "Qualificação"),
    )

    codigo = models.CharField(
        max_length=20,
        unique=True,
        blank=True
    )

    nome = models.CharField(max_length=200)

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES
    )

    descricao = models.TextField(blank=True)

    preco_venda = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    ativo = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # =========================
    # SAVE
    # =========================
    def save(self, *args, **kwargs):

        if not self.codigo:

            prefixos = {
                "calibracao": "CL",
                "produto": "PRD",
                "manutencao": "MAN",
                "qualificacao": "QUA",
            }

            prefixo = prefixos.get(self.tipo, "GEN")

            ultimo = ProdutoServico.objects.filter(
                codigo__startswith=prefixo
            ).count() + 1

            self.codigo = f"{prefixo}-{ultimo:04d}"

        super().save(*args, **kwargs)

    def __str__(self):

        return f"{self.codigo} - {self.nome}"
    

from decimal import Decimal


# =========================
# COMPOSIÇÃO DE PREÇO
# =========================

class ComposicaoPreco(models.Model):

    produto = models.OneToOneField(
        ProdutoServico,
        on_delete=models.CASCADE,
        related_name="composicao"
    )

    hora_tecnica = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="R$/hora"
    )

    tempo_execucao = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Horas"
    )

    custo_logistica = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="R$"
    )

    custo_insumos = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="R$"
    )

    outros_custos = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="R$"
    )

    impostos_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="%"
    )

    margem_lucro = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="%"
    )

    preco_calculado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="R$"
    )

    # =========================
    # CALCULAR PREÇO
    # =========================
    def calcular_preco(self):

        custo_total = (
            (self.hora_tecnica * self.tempo_execucao)
            + self.custo_logistica
            + self.custo_insumos
            + self.outros_custos
        )

        impostos = custo_total * (
            self.impostos_percentual / Decimal("100")
        )

        subtotal = custo_total + impostos

        # EVITAR DIVISÃO INVÁLIDA
        if self.margem_lucro >= Decimal("100"):
            return subtotal

        margem = self.margem_lucro / Decimal("100")

        # MARGEM REAL
        preco_final = subtotal / (
            Decimal("1") - margem
        )

        return round(preco_final, 2)

    # =========================
    # SAVE
    # =========================
    def save(self, *args, **kwargs):

        self.preco_calculado = self.calcular_preco()

        super().save(*args, **kwargs)

        self.produto.preco_venda = self.preco_calculado

        self.produto.save(update_fields=["preco_venda"])

    def __str__(self):

        return f"Composição de preço - {self.produto.nome}"
    

# =========================
# DADOS TÉCNICOS
# =========================

class DadosTecnicos(models.Model):

    produto = models.OneToOneField(
        ProdutoServico,
        on_delete=models.CASCADE,
        related_name="dados_tecnicos"
    )

    metodo = models.TextField(blank=True)
    padroes = models.TextField(blank=True)
    solucoes = models.TextField(blank=True)
    tempo_medio = models.CharField(max_length=100, blank=True)
    equipamentos_auxiliares = models.TextField(blank=True)

    def __str__(self):
        return f"Dados técnicos - {self.produto.nome}"


# =========================
# ANEXOS PRODUTO
# =========================

class ProdutoAnexo(models.Model):

    produto = models.ForeignKey(
        ProdutoServico,
        on_delete=models.CASCADE,
        related_name="anexos"
    )

    nome = models.CharField(max_length=200)
    arquivo = models.FileField(upload_to="produtos/anexos/")

    def __str__(self):
        return self.nome


# =========================
# PROPOSTA
# =========================

class Proposta(models.Model):

    STATUS_CHOICES = (
        ("rascunho", "Rascunho"),
        ("enviado", "Enviado"),
        ("pendente", "Pendente"),
        ("aprovado", "Aprovado"),
        ("recusado", "Recusado"),
    )

    LOCAL_CHOICES = (
        ("in_loco", "IN LOCO"),
        ("laboratorio", "DS Científica"),
    )

    FRETE_CHOICES = (
        ("CIF", "CIF"),
        ("FOB", "FOB"),
        ("NA", "Não aplicável"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="propostas"
    )

    # 🔹 RESPONSÁVEL (CONTATO DO CLIENTE)
    responsavel = models.ForeignKey(
        "clientes.ContatoCliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    codigo = models.CharField(max_length=50, unique=True, blank=True)

    data_emissao = models.DateField(auto_now_add=True)
    validade = models.DateField(null=True, blank=True)

    prazo_pagamento = models.CharField(max_length=200, blank=True)

    local_execucao = models.CharField(
        max_length=20,
        choices=LOCAL_CHOICES,
        default="laboratorio"
    )

    frete = models.CharField(
        max_length=10,
        choices=FRETE_CHOICES,
        default="NA"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="rascunho"
    )

    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    metodo = models.TextField(blank=True)
    padroes_utilizados = models.TextField(blank=True)

    observacoes = models.TextField(blank=True)

    def gerar_codigo(self):
        ano = datetime.now().strftime("%y")
        numero = Proposta.objects.count() + 1
        return f"PROP-{numero:04d}/{ano}"

    def atualizar_total(self):
        total = self.itens.aggregate(total=Sum("valor_total"))["total"] or 0
        self.total = total
        super().save(update_fields=["total"])

    def atualizar_metodos_e_padroes(self):

        metodos_set = set()
        padroes_set = set()

        for item in self.itens.all():
            produto = item.produto

            if not produto:
                continue

            if hasattr(produto, "dados_tecnicos") and produto.dados_tecnicos:

                if produto.dados_tecnicos.metodo:
                    for m in produto.dados_tecnicos.metodo.split(";"):
                        metodos_set.add(m.strip())

                if produto.dados_tecnicos.padroes:
                    for p in produto.dados_tecnicos.padroes.split(";"):
                        padroes_set.add(p.strip())

        self.metodo = "\n".join(sorted(metodos_set))
        self.padroes_utilizados = "\n".join(sorted(padroes_set))

        super().save(update_fields=["metodo", "padroes_utilizados"])

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.gerar_codigo()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.codigo

# =========================
# ANEXO DE PROPOSTA
# =========================

class PropostaAnexo(models.Model):

    proposta = models.ForeignKey(
        Proposta,
        on_delete=models.CASCADE,
        related_name="anexos"
    )

    nome = models.CharField(max_length=200)

    arquivo = models.FileField(upload_to="propostas/anexos/")

    data_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} - {self.proposta.codigo}"


# =========================
# ITEM PROPOSTA
# =========================

class ItemProposta(models.Model):

    proposta = models.ForeignKey(
        Proposta,
        on_delete=models.CASCADE,
        related_name="itens"
    )

    produto = models.ForeignKey(
        ProdutoServico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    descricao = models.CharField(max_length=255, blank=True)
    quantidade = models.PositiveIntegerField(default=1)

    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):

        if self.produto:
            self.descricao = self.produto.nome
            self.valor_unitario = self.produto.preco_venda

        self.valor_total = (self.quantidade * self.valor_unitario) - self.desconto

        super().save(*args, **kwargs)

        if self.proposta:
            self.proposta.atualizar_total()
            self.proposta.atualizar_metodos_e_padroes()

    def delete(self, *args, **kwargs):
        proposta = self.proposta
        super().delete(*args, **kwargs)

        if proposta:
            proposta.atualizar_total()
            self.proposta.atualizar_metodos_e_padroes()

    def __str__(self):
        return self.descricao or f"Item {self.id}"

# =========================
# CRM REGISTRO (UPGRADE)
# =========================

class CRMRegistro(models.Model):

    ETAPA_CHOICES = (
        ("lead", "Lead"),
        ("qualificacao", "Qualificação"),
        ("proposta", "Proposta"),
        ("negociacao", "Negociação"),
        ("fechado", "Fechado"),
    )

    PROBABILIDADE_CHOICES = (
        ("frio", "Frio (10%)"),
        ("morno", "Morno (30%)"),
        ("quente", "Quente (60%)"),
        ("muito_quente", "Muito quente (90%)"),
    )

    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.CASCADE)

    proposta = models.ForeignKey(
        Proposta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    responsavel = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    titulo = models.CharField(max_length=200)

    etapa_funil = models.CharField(
        max_length=20,
        choices=ETAPA_CHOICES,
        default="lead"
    )

    valor_estimado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    probabilidade = models.CharField(
        max_length=20,
        choices=PROBABILIDADE_CHOICES,
        default="frio"
    )

    probabilidade_numero = models.IntegerField(default=10)

    proxima_acao = models.DateField(null=True, blank=True)

    observacoes = models.TextField(blank=True)

    def save(self, *args, **kwargs):

        # 🔹 puxar valor da proposta
        if self.proposta:
            self.valor_estimado = self.proposta.total

        # 🔹 mapear probabilidade
        mapa = {
            "frio": 10,
            "morno": 30,
            "quente": 60,
            "muito_quente": 90,
        }

        self.probabilidade_numero = mapa.get(self.probabilidade, 10)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.titulo


# =========================
# CRM INTERAÇÕES
# =========================

class CRMInteracao(models.Model):

    crm = models.ForeignKey(
        CRMRegistro,
        on_delete=models.CASCADE,
        related_name="interacoes"
    )

    descricao = models.TextField()

    data = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Interação - {self.crm.titulo}"


# =========================
# CRM TICKET (UPGRADE)
# =========================

class CRMTicket(models.Model):

    STATUS_CHOICES = (
        ("aberto", "Aberto"),
        ("andamento", "Em andamento"),
        ("aguardando", "Aguardando cliente"),
        ("resolvido", "Resolvido"),
        ("fechado", "Fechado"),
    )

    PRIORIDADE_CHOICES = (
        ("baixa", "Baixa"),
        ("normal", "Normal"),
        ("alta", "Alta"),
        ("urgente", "Urgente"),
    )

    TIPO_CHOICES = (
        ("servico", "Serviço"),
        ("produto", "Produto"),
    )

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.CASCADE
    )

    proposta = models.ForeignKey(
        Proposta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    responsavel = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    titulo = models.CharField(max_length=200)

    descricao = models.TextField()

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="servico"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="aberto"
    )

    prioridade = models.CharField(
        max_length=20,
        choices=PRIORIDADE_CHOICES,
        default="normal"
    )

    prazo_resposta = models.DateField(null=True, blank=True)

    data_abertura = models.DateTimeField(auto_now_add=True)

    observacoes = models.TextField(blank=True)

    def save(self, *args, **kwargs):

        from datetime import timedelta

        # 🔹 SLA automático
        mapa = {
            "urgente": 1,
            "alta": 2,
            "normal": 3,
            "baixa": 5,
        }

        if self.prioridade and not self.prazo_resposta:
            dias = mapa.get(self.prioridade, 3)
            self.prazo_resposta = datetime.now().date() + timedelta(days=dias)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.titulo
