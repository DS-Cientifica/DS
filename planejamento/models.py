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
