import uuid
from datetime import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from calibracao.models import Instrumento, OrdemServico, Padrao
from clientes.models import Cliente, ContatoCliente
from comercial.models import Proposta


class PlanejamentoServico(models.Model):
    TIPO_CHOICES = (
        ("servico", "Servico agendado"),
        ("visita_tecnica", "Agendamento de visita"),
        ("retirada", "Retirada de equipamento"),
        ("entrega", "Entrega de equipamento"),
        ("coleta", "Coleta externa"),
        ("outro", "Outro"),
    )

    STATUS_CHOICES = (
        ("rascunho", "Rascunho"),
        ("agendado", "Agendado"),
        ("confirmado", "Confirmado"),
        ("em_execucao", "Em execucao"),
        ("concluido", "Concluido"),
        ("cancelado", "Cancelado"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField("Codigo", max_length=30, unique=True, blank=True)
    titulo = models.CharField("Titulo do planejamento", max_length=200, blank=True)
    tipo_agendamento = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES, default="servico")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="agendado")

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="planejamentos_servico",
        verbose_name="Cliente",
    )
    contato = models.ForeignKey(
        ContatoCliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planejamentos_servico",
        verbose_name="Contato",
    )
    telefone_contato = models.CharField("Telefone do contato", max_length=30, blank=True)
    email_contato = models.EmailField("E-mail do contato", blank=True)

    proposta = models.ForeignKey(
        Proposta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planejamentos_servico",
        verbose_name="Proposta",
    )
    ordem_servico = models.ForeignKey(
        OrdemServico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planejamentos_servico",
        verbose_name="Ordem de Servico",
    )

    instrumentos = models.ManyToManyField(
        Instrumento,
        blank=True,
        related_name="planejamentos_servico",
        verbose_name="Equipamentos previstos",
    )
    padroes = models.ManyToManyField(
        Padrao,
        blank=True,
        related_name="planejamentos_servico",
        verbose_name="Padroes necessarios",
    )

    data_inicio = models.DateField("Data inicial", default=timezone.localdate)
    data_fim = models.DateField("Data final", blank=True, null=True)
    hora_inicio = models.TimeField("Hora inicial", blank=True, null=True)
    hora_fim = models.TimeField("Hora final", blank=True, null=True)
    dia_inteiro = models.BooleanField("Dia inteiro", default=False)

    confirmado_cliente = models.BooleanField("Cliente confirmado", default=False)
    local_servico = models.CharField("Local do servico", max_length=255, blank=True)
    necessita_veiculo = models.BooleanField("Necessita carro", default=False)
    veiculo_descricao = models.CharField("Veiculo previsto", max_length=120, blank=True)

    responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planejamentos_responsavel",
        verbose_name="Responsavel pelo planejamento",
    )
    tecnicos = models.ManyToManyField(
        User,
        blank=True,
        related_name="planejamentos_tecnicos",
        verbose_name="Equipe tecnica",
    )

    recursos_necessarios = models.TextField(
        "Recursos necessarios",
        blank=True,
        help_text="Ex.: notebook, EPI, ferramental, etiquetas, formulario, impressora.",
    )
    retirada_equipamentos = models.TextField(
        "Retirada/entrega de equipamentos",
        blank=True,
        help_text="Descreva o que sera retirado, entregue ou movimentado.",
    )
    observacoes = models.TextField("Observacoes", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Agenda t\u00e9cnica"
        verbose_name_plural = "Agendas t\u00e9cnicas"
        ordering = ("data_inicio", "hora_inicio", "cliente__razao_social")

    def __str__(self):
        return f"{self.codigo} - {self.cliente.razao_social}"

    def clean(self):
        if self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError({"data_fim": "A data final nao pode ser menor que a data inicial."})

    def gerar_codigo(self):
        ano = datetime.now().strftime("%y")
        numero = PlanejamentoServico.objects.exclude(codigo="").count() + 1
        return f"PLAN-{numero:04d}/{ano}"

    def intervalo_resumido(self):
        data_final = self.data_fim or self.data_inicio
        if self.dia_inteiro:
            if data_final != self.data_inicio:
                return f"{self.data_inicio:%d/%m/%Y} a {data_final:%d/%m/%Y}"
            return f"{self.data_inicio:%d/%m/%Y} - Dia inteiro"

        inicio = self.hora_inicio.strftime("%H:%M") if self.hora_inicio else "--:--"
        fim = self.hora_fim.strftime("%H:%M") if self.hora_fim else "--:--"
        if data_final != self.data_inicio:
            return f"{self.data_inicio:%d/%m/%Y} {inicio} ate {data_final:%d/%m/%Y} {fim}"
        return f"{self.data_inicio:%d/%m/%Y} {inicio} - {fim}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.gerar_codigo()

        if not self.data_fim:
            self.data_fim = self.data_inicio

        if self.proposta_id and not self.cliente_id:
            self.cliente = self.proposta.cliente

        if self.ordem_servico_id and not self.cliente_id:
            self.cliente = self.ordem_servico.cliente

        if self.cliente_id and not self.contato_id:
            self.contato = self.cliente.contatos.order_by("-principal", "nome").first()

        if self.contato_id:
            if not self.telefone_contato:
                self.telefone_contato = self.contato.telefone
            if not self.email_contato:
                self.email_contato = self.contato.email
        elif self.cliente_id:
            if not self.telefone_contato:
                self.telefone_contato = self.cliente.telefone or self.cliente.telefone2
            if not self.email_contato:
                self.email_contato = self.cliente.email

        if self.cliente_id and not self.local_servico:
            partes = [
                self.cliente.endereco,
                self.cliente.numero,
                self.cliente.bairro,
                self.cliente.cidade,
                self.cliente.uf,
            ]
            self.local_servico = ", ".join([parte for parte in partes if parte])

        if not self.titulo and self.cliente_id:
            self.titulo = f"{self.get_tipo_agendamento_display()} - {self.cliente.razao_social}"

        super().save(*args, **kwargs)

    def possui_alerta_padroes(self):
        return self.situacao_padroes_codigo() != "ok"

    def situacao_padroes_codigo(self):
        if not self.exige_padroes():
            return "nao_aplicavel"

        padroes = list(self.padroes.all())
        if not padroes:
            return "faltando"

        data_limite = self.data_inicio or timezone.localdate()
        for padrao in padroes:
            if padrao.status == "vencido":
                return "vencido"
            if padrao.vencimento and padrao.vencimento < data_limite:
                return "vencido"
        return "ok"

    def situacao_padroes_label(self):
        mapa = {
            "nao_aplicavel": "Nao se aplica",
            "faltando": "Padroes nao informados",
            "vencido": "Padrao vencido",
            "ok": "Padroes em dia",
        }
        return mapa.get(self.situacao_padroes_codigo(), "Padroes em dia")

    def exige_padroes(self):
        return self.tipo_agendamento == "servico"

    def nome_responsavel_cliente(self):
        if self.contato_id:
            return self.contato.nome
        return ""

    def cargo_responsavel_cliente(self):
        if self.contato_id:
            return self.contato.cargo
        return ""

    def nomes_tecnicos(self):
        nomes = []
        vistos = set()
        for tecnico in self.tecnicos.all():
            nome = tecnico.get_full_name() or tecnico.username
            chave = nome.strip().lower()
            if chave and chave not in vistos:
                vistos.add(chave)
                nomes.append(nome)
        return nomes


class EnvioEquipamentoSemNota(models.Model):
    TIPO_FORMULARIO_CHOICES = (
        ("envio", "Envio"),
        ("recebimento", "Recebimento"),
    )

    FINALIDADE_CHOICES = (
        ("calibracao", "Calibracao"),
        ("manutencao_preventiva", "Manutencao preventiva"),
        ("manutencao_corretiva", "Manutencao corretiva"),
        ("avaliacao_tecnica", "Avaliacao tecnica / diagnostico"),
        ("orcamento", "Orcamento"),
        ("outro", "Outro"),
    )

    FUNCIONAMENTO_CHOICES = (
        ("funcionando", "Equipamento funcionando normalmente"),
        ("defeito", "Equipamento com defeito"),
        ("liga_falha", "Equipamento liga, mas apresenta falha"),
        ("nao_liga", "Equipamento nao liga"),
    )

    ACESSORIOS_CHOICES = (
        ("com_acessorios", "Equipamento enviado com acessorios"),
        ("sem_acessorios", "Equipamento enviado sem acessorios"),
    )

    EMBALAGEM_ENVIO_CHOICES = (
        ("integra", "Embalagem integra"),
        ("danificada", "Embalagem danificada"),
    )

    FRETE_CHOICES = (
        ("remetente", "Remetente"),
        ("destinatario", "Destinatario"),
        ("combinar", "A combinar"),
    )

    EMBALAGEM_RECEBIMENTO_CHOICES = (
        ("integra", "Integra"),
        ("danificada", "Danificada"),
        ("violada", "Violada"),
        ("molhada", "Molhada"),
        ("amassada", "Amassada"),
        ("outro", "Outro"),
    )

    CONDICAO_RECEBIMENTO_CHOICES = (
        ("sem_avarias", "Sem avarias aparentes"),
        ("com_avarias", "Com avarias aparentes"),
        ("divergente", "Divergente da descricao informada"),
        ("aguardando_avaliacao", "Aguardando avaliacao tecnica"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField("Codigo", max_length=30, unique=True, blank=True)
    tipo_formulario = models.CharField(
        "Tipo do formulario",
        max_length=20,
        choices=TIPO_FORMULARIO_CHOICES,
        default="envio",
    )
    data_envio_formulario = models.DateField("Data de envio", default=timezone.localdate)

    cliente_remetente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envios_sem_nota",
        verbose_name="Cliente remetente",
    )
    empresa_remetente = models.CharField("Empresa remetente", max_length=255, blank=True)
    cnpj_cpf_remetente = models.CharField("CNPJ/CPF", max_length=20, blank=True)
    endereco_remetente = models.CharField("Endereco", max_length=255, blank=True)
    cidade_uf_remetente = models.CharField("Cidade/UF", max_length=120, blank=True)
    responsavel_envio = models.CharField("Responsavel pelo envio", max_length=120, blank=True)
    telefone_whatsapp = models.CharField("Telefone/WhatsApp", max_length=30, blank=True)
    email_remetente = models.EmailField("E-mail", blank=True)

    empresa_destinataria = models.CharField("Empresa destinataria", max_length=255, blank=True)
    cnpj_destinatario = models.CharField("CNPJ destinatario", max_length=20, blank=True)
    endereco_destinatario = models.CharField("Endereco destinatario", max_length=255, blank=True)
    cidade_uf_destinatario = models.CharField("Cidade/UF destinatario", max_length=120, blank=True)
    responsavel_recebimento_destino = models.CharField(
        "Responsavel pelo recebimento",
        max_length=120,
        blank=True,
    )

    finalidade = models.CharField("Finalidade do envio", max_length=30, choices=FINALIDADE_CHOICES)
    finalidade_outro = models.CharField("Outro motivo", max_length=255, blank=True)
    descricao_solicitacao = models.TextField(
        "Descricao da solicitacao",
        blank=True,
        help_text="Descreva o servico solicitado, pontos de calibracao, faixa de uso, defeito apresentado ou informacoes relevantes.",
    )

    condicao_funcionamento = models.CharField(
        "Condicao de funcionamento",
        max_length=20,
        choices=FUNCIONAMENTO_CHOICES,
        blank=True,
    )
    condicao_acessorios = models.CharField(
        "Acessorios",
        max_length=20,
        choices=ACESSORIOS_CHOICES,
        blank=True,
    )
    condicao_embalagem_envio = models.CharField(
        "Condicao da embalagem",
        max_length=20,
        choices=EMBALAGEM_ENVIO_CHOICES,
        blank=True,
    )
    acessorios_enviados = models.TextField("Acessorios enviados", blank=True)
    observacoes_estado = models.TextField("Observacoes sobre o estado do equipamento", blank=True)

    transportadora = models.CharField("Transportadora / Correios / Portador", max_length=255, blank=True)
    codigo_rastreamento = models.CharField("Codigo de rastreamento", max_length=120, blank=True)
    data_envio_transporte = models.DateField("Data do envio no transporte", blank=True, null=True)
    responsavel_frete = models.CharField(
        "Responsavel pelo frete",
        max_length=20,
        choices=FRETE_CHOICES,
        default="remetente",
    )

    nome_declarante = models.CharField("Nome do responsavel", max_length=120, blank=True)
    cargo_declarante = models.CharField("Cargo", max_length=120, blank=True)
    cpf_declarante = models.CharField("CPF", max_length=20, blank=True)
    assinatura_declarante = models.CharField(
        "Assinatura",
        max_length=255,
        blank=True,
        help_text="Campo textual para identificacao do assinante no PDF.",
    )
    data_declaracao = models.DateField("Data da declaracao", blank=True, null=True)

    data_recebimento = models.DateField("Data de recebimento", blank=True, null=True)
    recebido_por = models.CharField("Recebido por", max_length=120, blank=True)
    condicao_embalagem_recebimento = models.CharField(
        "Condicao da embalagem no recebimento",
        max_length=20,
        choices=EMBALAGEM_RECEBIMENTO_CHOICES,
        blank=True,
    )
    condicao_embalagem_recebimento_outro = models.CharField("Outro detalhe da embalagem", max_length=255, blank=True)
    condicao_aparente_recebimento = models.CharField(
        "Condicao aparente do equipamento no recebimento",
        max_length=25,
        choices=CONDICAO_RECEBIMENTO_CHOICES,
        blank=True,
    )
    observacoes_recebimento = models.TextField("Observacoes do recebimento", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Formulario logistico sem NF"
        verbose_name_plural = "Formularios logisticos sem NF"
        ordering = ("-data_envio_formulario", "-created_at")

    def __str__(self):
        return f"{self.codigo} - {self.get_tipo_formulario_display()} - {self.empresa_remetente or self.cliente_remetente or 'Sem remetente'}"

    def gerar_codigo(self):
        ano = datetime.now().strftime("%y")
        numero = EnvioEquipamentoSemNota.objects.exclude(codigo="").count() + 1
        prefixo = "ENV" if self.tipo_formulario == "envio" else "REC"
        return f"LOG-{prefixo}-{numero:04d}/{ano}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.gerar_codigo()

        if self.cliente_remetente_id:
            cliente = self.cliente_remetente
            if not self.empresa_remetente:
                self.empresa_remetente = cliente.razao_social
            if not self.cnpj_cpf_remetente:
                self.cnpj_cpf_remetente = cliente.cnpj
            if not self.endereco_remetente:
                partes = [cliente.endereco, cliente.numero, cliente.bairro]
                self.endereco_remetente = ", ".join([parte for parte in partes if parte])
            if not self.cidade_uf_remetente:
                cidade_uf = " / ".join([parte for parte in [cliente.cidade, cliente.uf] if parte])
                self.cidade_uf_remetente = cidade_uf
            if not self.telefone_whatsapp:
                self.telefone_whatsapp = cliente.telefone or cliente.telefone2
            if not self.email_remetente:
                self.email_remetente = cliente.email

        if not self.data_declaracao:
            self.data_declaracao = self.data_envio_formulario
        if not self.data_envio_transporte:
            self.data_envio_transporte = self.data_envio_formulario

        super().save(*args, **kwargs)


class EnvioEquipamentoSemNotaItem(models.Model):
    envio = models.ForeignKey(
        EnvioEquipamentoSemNota,
        on_delete=models.CASCADE,
        related_name="itens",
        verbose_name="Formulario",
    )
    ordem = models.PositiveIntegerField("Item", default=1)
    equipamento = models.CharField("Equipamento", max_length=255)
    marca = models.CharField("Marca", max_length=120, blank=True)
    modelo = models.CharField("Modelo", max_length=120, blank=True)
    numero_serie_patrimonio = models.CharField("N de serie / patrimonio", max_length=120, blank=True)
    quantidade = models.PositiveIntegerField("Quantidade", default=1)

    class Meta:
        verbose_name = "Item do envio sem NF"
        verbose_name_plural = "Itens do envio sem NF"
        ordering = ("ordem", "equipamento")

    def __str__(self):
        return f"{self.ordem} - {self.equipamento}"
