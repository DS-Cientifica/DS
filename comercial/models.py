import uuid

from datetime import datetime
from datetime import timedelta
import re

from django.db import models, transaction
from django.utils import timezone

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
        choices=(
            ("imagem", "Imagem"),
            ("documento", "Documento"),
            ("outro", "Outro"),
        ),
        default="imagem"
    )

    tipo = models.CharField(
        max_length=20,
        choices=(
            ("imagem", "Imagem"),
            ("documento", "Documento"),
            ("outro", "Outro"),
        ),
        default="imagem"
    )


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

    class Meta:
        verbose_name = "Produto/Serviço"
        verbose_name_plural = "Produtos/Serviços"
    



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

    RESULTADO_CHOICES = (
        ("", "Não definido"),
        ("positivo", "Positivo"),
        ("negativo", "Negativo"),
    )

    MOTIVO_PERDA_CHOICES = (
        ("", "Não definido"),
        ("preco", "Preço"),
        ("prazo", "Prazo"),
        ("escopo", "Escopo técnico"),
        ("concorrencia", "Concorrência"),
        ("sem_retorno", "Sem retorno do cliente"),
        ("orcamento_cancelado", "Orçamento cancelado pelo cliente"),
        ("outro", "Outro"),
    )


    LOCAL_CHOICES = (

        ("in_loco", "IN LOCO"),

        ("laboratorio", "DS Cient\u00edfica"),

    )


    FRETE_CHOICES = (

        ("CIF", "CIF"),

        ("FOB", "FOB"),

        ("NA", "N\u00e3o aplic\u00e1vel"),

    )

    TIPO_FATURAMENTO_CHOICES = (
        ("imediato", "Imediato na aprovação"),
        ("apos_execucao", "Após execução"),
        ("parcelado", "Parcelado"),
    )


    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="propostas"
    )

    responsavel = models.ForeignKey(
        "clientes.ContatoCliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    crm_registro = models.ForeignKey(
        "comercial.CRMRegistro",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="propostas_vinculadas",
    )

    codigo = models.CharField(max_length=50, unique=True, blank=True)
    revisao = models.CharField(max_length=10, default="00", blank=True)
    data_emissao = models.DateField(auto_now_add=True)
    validade = models.DateField(null=True, blank=True)
    prazo_execucao = models.CharField("Prazo para atendimento", max_length=200, blank=True, default="10 dias úteis")
    prazo_pagamento = models.CharField(max_length=200, blank=True)
    gera_conta_receber_automaticamente = models.BooleanField(default=False)
    tipo_faturamento = models.CharField(
        max_length=20,
        choices=TIPO_FATURAMENTO_CHOICES,
        default="imediato",
    )
    local_execucao = models.CharField(max_length=20, choices=LOCAL_CHOICES, default="laboratorio")
    frete = models.CharField(max_length=10, choices=FRETE_CHOICES, default="NA")
    desconto_geral = models.DecimalField("Desconto geral", max_digits=12, decimal_places=2, default=0)
    frete_valor = models.DecimalField("Frete", max_digits=12, decimal_places=2, default=0)
    outras_despesas = models.DecimalField("Outras despesas", max_digits=12, decimal_places=2, default=0)
    seguro_valor = models.DecimalField("Seguro", max_digits=12, decimal_places=2, default=0)
    margem_percentual = models.DecimalField("Margem", max_digits=5, decimal_places=2, default=0, help_text="%")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="rascunho")
    resultado_fechamento = models.CharField(max_length=20, choices=RESULTADO_CHOICES, blank=True, default="")
    motivo_perda = models.CharField(max_length=30, choices=MOTIVO_PERDA_CHOICES, blank=True, default="")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    metodo = models.TextField(blank=True)
    padroes_utilizados = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)

    def gerar_codigo(self):
        ano = datetime.now().strftime("%y")
        numero = Proposta.objects.count() + 1
        return f"PROP-{numero:04d}/{ano}"

    def resumo_financeiro(self):
        subtotal_base = Decimal("0")
        subtotal = Decimal("0")
        desconto_itens = Decimal("0")

        for item in self.itens.all():
            quantidade = Decimal(item.quantidade or 0)
            valor_unitario = Decimal(item.valor_unitario or 0)
            desconto = Decimal(item.desconto or 0)
            subtotal_base += quantidade * valor_unitario
            subtotal += item.valor_bruto_com_margem()
            desconto_itens += desconto

        subtotal_liquido = subtotal - desconto_itens
        desconto_geral = Decimal(self.desconto_geral or 0)
        base_apos_desconto = subtotal_liquido - desconto_geral
        if base_apos_desconto < Decimal("0"):
            base_apos_desconto = Decimal("0")

        margem_percentual = Decimal(self.margem_percentual or 0)
        margem_valor = (subtotal - subtotal_base).quantize(Decimal("0.01"))

        frete_valor = Decimal(self.frete_valor or 0)
        outras_despesas = Decimal(self.outras_despesas or 0)
        seguro_valor = Decimal(self.seguro_valor or 0)

        total = base_apos_desconto + frete_valor + outras_despesas + seguro_valor
        return {
            "subtotal_base": subtotal_base,
            "subtotal": subtotal,
            "desconto_itens": desconto_itens,
            "subtotal_liquido": subtotal_liquido,
            "desconto_geral": desconto_geral,
            "base_apos_desconto": base_apos_desconto,
            "margem_percentual": margem_percentual,
            "margem_valor": margem_valor,
            "frete_valor": frete_valor,
            "outras_despesas": outras_despesas,
            "seguro_valor": seguro_valor,
            "total": total,
        }

    def atualizar_total(self):
        resumo = self.resumo_financeiro()
        self.total = resumo["total"]
        super().save(update_fields=["total"])
        self.sincronizar_crm()

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

    def _titulo_crm(self):
        return f"{self.codigo} - {self.cliente.razao_social}"

    @staticmethod
    def _fechamento_positivo(status, resultado_fechamento):
        return status == "aprovado" or resultado_fechamento == "positivo"

    def deve_criar_conta_receber_automaticamente(self):
        return (
            self.gera_conta_receber_automaticamente
            and self.tipo_faturamento == "imediato"
            and self._fechamento_positivo(self.status, self.resultado_fechamento)
        )

    def _calcular_vencimento_conta_receber(self):
        base = self.data_emissao or timezone.localdate()
        prazo_texto = (self.prazo_pagamento or "").strip()
        dias_match = re.search(r"(\d+)", prazo_texto)
        if dias_match:
            return base + timedelta(days=int(dias_match.group(1)))
        return base

    def criar_conta_receber_pendente(self):
        from financeiro.models import ContaReceber

        if not self.pk or not self.deve_criar_conta_receber_automaticamente():
            return None

        conta_existente = self.contas_receber.exclude(status="cancelado").first()
        if conta_existente:
            return conta_existente

        return ContaReceber.objects.create(
            proposta=self,
            cliente=self.cliente,
            descricao=f"Proposta {self.codigo}",
            valor=self.total,
            vencimento=self._calcular_vencimento_conta_receber(),
            status="pendente",
        )

    def sincronizar_crm(self):
        if not self.pk:
            return

        update_fields = []
        crm = self.crm_registro

        if crm is None:
            crm = CRMRegistro.objects.filter(proposta=self).first()
            if crm:
                self.crm_registro = crm
                update_fields.append("crm_registro")

        if crm is None and self.status != "rascunho":
            crm = CRMRegistro.objects.create(
                cliente=self.cliente,
                proposta=self,
                titulo=self._titulo_crm(),
                etapa_funil="proposta",
                valor_estimado=self.total,
            )
            self.crm_registro = crm
            update_fields.append("crm_registro")

        if crm:
            crm.cliente = self.cliente
            crm.proposta = self
            crm.titulo = self._titulo_crm()
            crm.valor_estimado = self.total
            if self.resultado_fechamento == "positivo" or self.status == "aprovado":
                crm.etapa_funil = "fechado_ganho"
            elif self.resultado_fechamento == "negativo" or self.status == "recusado":
                crm.etapa_funil = "fechado_perdido"
            else:
                crm.etapa_funil = "proposta"
            crm.save()

        if update_fields:
            super().save(update_fields=update_fields)

    def save(self, *args, **kwargs):
        status_anterior = None
        resultado_anterior = ""
        if self.pk:
            proposta_anterior = (
                Proposta.objects.filter(pk=self.pk)
                .values("status", "resultado_fechamento")
                .first()
            )
            if proposta_anterior:
                status_anterior = proposta_anterior["status"]
                resultado_anterior = proposta_anterior["resultado_fechamento"] or ""

        if not self.codigo:
            self.codigo = self.gerar_codigo()
        if self.status == "aprovado" and not self.resultado_fechamento:
            self.resultado_fechamento = "positivo"
        elif self.status == "recusado" and not self.resultado_fechamento:
            self.resultado_fechamento = "negativo"
        if self.resultado_fechamento != "negativo":
            self.motivo_perda = ""
        with transaction.atomic():
            super().save(*args, **kwargs)
            self.sincronizar_crm()
            if self.deve_criar_conta_receber_automaticamente() and not self._fechamento_positivo(
                status_anterior,
                resultado_anterior,
            ):
                self.criar_conta_receber_pendente()

    def __str__(self):
        return self.codigo

    def criar_revisao(self, usuario=None, descricao="Revisao criada manualmente."):
        try:
            numero_revisao = int(self.revisao or "00") + 1
        except ValueError:
            numero_revisao = 1

        self.revisao = f"{numero_revisao:02d}"
        super().save(update_fields=["revisao"])
        return self.revisao


class PropostaMovimentacao(models.Model):
    TIPO_CHOICES = (
        ("criacao", "Criacao"),
        ("alteracao", "Alteracao"),
        ("revisao", "Revisao"),
        ("financeiro", "Financeiro"),
        ("crm", "CRM"),
        ("outro", "Outro"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposta = models.ForeignKey(
        Proposta,
        on_delete=models.CASCADE,
        related_name="movimentacoes",
        verbose_name="Proposta",
    )
    data = models.DateTimeField("Data", auto_now_add=True)
    usuario = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposta_movimentacoes",
        verbose_name="Usuario",
    )
    tipo = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES, default="alteracao")
    revisao = models.CharField("Revisao", max_length=10, blank=True)
    descricao = models.TextField("Movimentacao")

    class Meta:
        verbose_name = "Movimentacao da Proposta"
        verbose_name_plural = "Movimentacoes da Proposta"
        ordering = ("-data",)

    @classmethod
    def registrar(cls, proposta, usuario, tipo, descricao):
        if not proposta or not proposta.pk or not descricao:
            return None
        return cls.objects.create(
            proposta=proposta,
            usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
            tipo=tipo,
            revisao=proposta.revisao or "00",
            descricao=descricao,
        )

    def __str__(self):
        return f"{self.proposta.codigo} - {self.get_tipo_display()} - {self.data:%d/%m/%Y %H:%M}"


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



    tipo = models.CharField(
        max_length=20,
        choices=(
            ("imagem", "Imagem"),
            ("documento", "Documento"),
            ("outro", "Outro"),
        ),
        default="imagem"
    )

    arquivo = models.FileField(upload_to="propostas/anexos/")

    legenda = models.CharField(max_length=255, blank=True)

    ordem = models.PositiveIntegerField(default=1)

    exibir_no_pdf = models.BooleanField(default=False)


    data_upload = models.DateTimeField(auto_now_add=True)



    def __str__(self):

        return f"{self.nome} - {self.proposta.codigo}"

    class Meta:
        ordering = ("ordem", "data_upload", "nome")




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

    def fator_margem(self):
        proposta = getattr(self, "proposta", None)
        margem_percentual = Decimal(getattr(proposta, "margem_percentual", 0) or 0)
        margem_decimal = margem_percentual / Decimal("100")
        if margem_decimal >= Decimal("1"):
            return Decimal("1")
        return (Decimal("1") / (Decimal("1") - margem_decimal)).quantize(Decimal("0.00000001"))

    def valor_unitario_com_margem(self):
        valor_unitario = Decimal(self.valor_unitario or 0)
        return (valor_unitario * self.fator_margem()).quantize(Decimal("0.01"))

    def valor_bruto_com_margem(self):
        quantidade = Decimal(self.quantidade or 0)
        return (quantidade * self.valor_unitario_com_margem()).quantize(Decimal("0.01"))

    def valor_total_com_margem(self):
        desconto = Decimal(self.desconto or 0)
        total = self.valor_bruto_com_margem() - desconto
        if total < Decimal("0"):
            total = Decimal("0")
        return total.quantize(Decimal("0.01"))



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

# PROSPECÇÃO COMERCIAL

# =========================



class ProspeccaoComercial(models.Model):

    STATUS_CHOICES = (
        ("novo", "Novo"),
        ("tentativa_contato", "Tentativa de contato"),
        ("sem_resposta", "Sem resposta"),
        ("em_contato", "Em contato"),
        ("interessado", "Interessado"),
        ("sem_interesse", "Sem interesse"),
        ("convertido", "Convertido em CRM"),
        ("perdido", "Perdido"),
    )

    ORIGEM_CHOICES = (
        ("indicacao", "Indicação"),
        ("site", "Site"),
        ("telefone", "Telefone"),
        ("email", "E-mail"),
        ("whatsapp", "WhatsApp"),
        ("linkedin", "LinkedIn"),
        ("visita", "Visita"),
        ("outro", "Outro"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.SET_NULL, null=True, blank=True)
    responsavel = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    convertido_por = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prospeccoes_convertidas",
    )
    crm_gerado = models.ForeignKey(
        "comercial.CRMRegistro",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prospeccoes_origem",
    )
    codigo = models.CharField(max_length=30, unique=True, blank=True, null=True)
    data_cadastro = models.DateTimeField(default=timezone.now)
    data_conversao = models.DateTimeField(null=True, blank=True)
    razao_social = models.CharField(max_length=255)
    contato_nome = models.CharField(max_length=120, blank=True)
    cargo = models.CharField(max_length=120, blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    origem_lead = models.CharField(max_length=20, choices=ORIGEM_CHOICES, default="outro")
    segmento = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="novo")
    observacoes = models.TextField(blank=True)

    def gerar_codigo(self):
        ano = datetime.now().strftime("%y")
        numero = ProspeccaoComercial.objects.filter(codigo__endswith=f"/{ano}").count() + 1
        return f"PSC-{numero:04d}/{ano}"

    def sincronizar_dados_cliente(self):
        if not self.cliente_id:
            return

        if not self.razao_social:
            self.razao_social = self.cliente.razao_social
        if not self.telefone:
            self.telefone = self.cliente.telefone or self.cliente.telefone2
        if not self.email:
            self.email = self.cliente.email

        contato = self.cliente.contatos.filter(principal=True).first() or self.cliente.contatos.first()
        if contato:
            if not self.contato_nome:
                self.contato_nome = contato.nome
            if not self.cargo:
                self.cargo = contato.cargo
            if not self.telefone:
                self.telefone = contato.telefone
            if not self.email:
                self.email = contato.email

    def converter_para_crm(self, usuario=None):
        if self.crm_gerado_id:
            return self.crm_gerado

        crm = CRMRegistro.objects.create(
            cliente=self.cliente if self.cliente_id else self._obter_ou_criar_cliente_minimo(),
            responsavel=self.responsavel,
            titulo=self.razao_social or self.contato_nome or self.codigo,
            etapa_funil="qualificacao",
            observacoes=self.observacoes,
        )
        self.crm_gerado = crm
        self.status = "convertido"
        self.data_conversao = timezone.now()
        if usuario and getattr(usuario, "pk", None):
            self.convertido_por = usuario
        self.save(update_fields=["crm_gerado", "status", "data_conversao", "convertido_por"])
        return crm

    def _obter_ou_criar_cliente_minimo(self):
        cliente = Cliente.objects.filter(razao_social=self.razao_social).first()
        if cliente:
            if not self.cliente_id:
                self.cliente = cliente
            return cliente

        cliente = Cliente.objects.create(
            razao_social=self.razao_social,
            nome_empresa=self.razao_social,
            cnpj=f"PROSPECT-{uuid.uuid4().hex[:8].upper()}",
            telefone=self.telefone,
            email=self.email,
        )
        self.cliente = cliente
        super().save(update_fields=["cliente"])
        return cliente

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.gerar_codigo()
        self.sincronizar_dados_cliente()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.razao_social}"

    class Meta:
        verbose_name = "Prospecção comercial"
        verbose_name_plural = "Prospecções comerciais"


class ProspeccaoInteracao(models.Model):

    TIPO_CHOICES = (
        ("ligacao", "Ligação"),
        ("email", "E-mail"),
        ("whatsapp", "WhatsApp"),
        ("reuniao", "Reunião"),
        ("visita", "Visita"),
        ("outro", "Outro"),
    )

    RESULTADO_CHOICES = (
        ("sem_resposta", "Sem resposta"),
        ("retornou", "Retornou"),
        ("reuniao_agendada", "Reunião agendada"),
        ("aguardando_retorno", "Aguardando retorno"),
        ("interessado", "Interessado"),
        ("sem_interesse", "Sem interesse"),
        ("convertido", "Convertido para CRM"),
    )

    prospeccao = models.ForeignKey(
        ProspeccaoComercial,
        on_delete=models.CASCADE,
        related_name="interacoes",
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="ligacao")
    resultado = models.CharField(max_length=30, choices=RESULTADO_CHOICES, default="sem_resposta")
    descricao = models.TextField()
    data = models.DateTimeField(default=timezone.now)
    proxima_acao = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Interação de prospecção - {self.prospeccao.codigo}"

    class Meta:
        verbose_name = "Interação de prospecção"
        verbose_name_plural = "Interações de prospecção"



# =========================

# CRM REGISTRO (UPGRADE)

# =========================



class CRMRegistro(models.Model):

    ETAPA_CHOICES = (
        ("lead", "Lead"),
        ("qualificacao", "Qualifica\u00e7\u00e3o"),
        ("proposta", "Proposta"),
        ("negociacao", "Negocia\u00e7\u00e3o"),
        ("fechado", "Fechado"),
        ("fechado_ganho", "Fechado ganho"),
        ("fechado_perdido", "Fechado perdido"),
    )

    PROBABILIDADE_CHOICES = (
        ("frio", "Frio (10%)"),
        ("morno", "Morno (30%)"),
        ("quente", "Quente (60%)"),
        ("muito_quente", "Muito quente (90%)"),
    )

    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.CASCADE)
    proposta = models.ForeignKey(Proposta, on_delete=models.SET_NULL, null=True, blank=True)
    responsavel = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    codigo = models.CharField(max_length=30, unique=True, blank=True, null=True)
    data_registro = models.DateTimeField(default=timezone.now)
    titulo = models.CharField(max_length=200)
    etapa_funil = models.CharField(max_length=20, choices=ETAPA_CHOICES, default="lead")
    valor_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    probabilidade = models.CharField(max_length=20, choices=PROBABILIDADE_CHOICES, default="frio")
    probabilidade_numero = models.IntegerField(default=10)
    proxima_acao = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)

    def gerar_codigo(self):
        ano = datetime.now().strftime("%y")
        maior_numero = 0
        for codigo in CRMRegistro.objects.filter(codigo__endswith=f"/{ano}").values_list("codigo", flat=True):
            match = re.match(r"^CRM-(\d+)/\d{2}$", codigo or "")
            if match:
                maior_numero = max(maior_numero, int(match.group(1)))
        return f"CRM-{maior_numero + 1:04d}/{ano}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.gerar_codigo()

        if self.proposta:
            self.valor_estimado = self.proposta.total

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

    class Meta:
        verbose_name = "Registro de CRM"
        verbose_name_plural = "Registros de CRM"


# =========================

# CRM INTERAÇÕES

# =========================



class CRMInteracao(models.Model):

    TIPO_CHOICES = (
        ("ligacao", "Liga\u00e7\u00e3o"),
        ("email", "E-mail"),
        ("whatsapp", "WhatsApp"),
        ("reuniao", "Reuni\u00e3o"),
        ("outro", "Outro"),
    )

    RESULTADO_CHOICES = (
        ("sem_resposta", "Sem resposta"),
        ("retornou", "Retornou"),
        ("reuniao_agendada", "Reuni\u00e3o agendada"),
        ("proposta_enviada", "Proposta enviada"),
        ("nao_interessado", "N\u00e3o interessado"),
        ("negociacao", "Em negocia\u00e7\u00e3o"),
        ("fechado", "Fechado"),
    )

    crm = models.ForeignKey(
        CRMRegistro,
        on_delete=models.CASCADE,
        related_name="interacoes"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="ligacao")
    resultado = models.CharField(max_length=30, choices=RESULTADO_CHOICES, default="sem_resposta")
    descricao = models.TextField()
    data = models.DateTimeField(default=timezone.now)
    proxima_acao = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Intera\u00e7\u00e3o - {self.crm.titulo}"

    class Meta:
        verbose_name = "Atividade comercial"
        verbose_name_plural = "Atividades comerciais"


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
        ("servico", "Servi\u00e7o"),
        ("produto", "Produto"),
    )

    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.CASCADE)
    proposta = models.ForeignKey(Proposta, on_delete=models.SET_NULL, null=True, blank=True)
    responsavel = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    codigo = models.CharField(max_length=30, unique=True, blank=True, null=True)
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="servico")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="aberto")
    prioridade = models.CharField(max_length=20, choices=PRIORIDADE_CHOICES, default="normal")
    prazo_resposta = models.DateField(null=True, blank=True)
    data_abertura = models.DateTimeField(auto_now_add=True)
    observacoes = models.TextField(blank=True)

    def gerar_codigo(self):
        ano = datetime.now().strftime("%y")
        numero = CRMTicket.objects.filter(codigo__endswith=f"/{ano}").count() + 1
        return f"TKT-{numero:04d}/{ano}"

    def save(self, *args, **kwargs):
        from datetime import timedelta

        if not self.codigo:
            self.codigo = self.gerar_codigo()

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

    class Meta:
        verbose_name = "Ticket de CRM"
        verbose_name_plural = "Tickets de CRM"


