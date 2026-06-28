import re

from django.core.exceptions import ValidationError
from django.db import models

from calibracao.models import (
    Instrumento,
    ResponsavelCertificado,
    _obter_ou_criar_responsavel_padrao,
)
from clientes.models import Cliente, ContatoCliente


class Manutencao(models.Model):
    class TipoManutencao(models.TextChoices):
        PREVENTIVA = "preventiva", "Preventiva"
        CORRETIVA = "corretiva", "Corretiva"
        AJUSTE = "ajuste", "Ajuste"
        DIAGNOSTICO = "diagnostico", "Diagnóstico"

    class Status(models.TextChoices):
        CONFORME = "conforme", "Conforme"
        NAO_CONFORME = "nao_conforme", "Não conforme"
        BLOQUEADO = "bloqueado", "Bloqueado"

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="manutencoes")
    instrumento = models.ForeignKey(Instrumento, on_delete=models.PROTECT, related_name="manutencoes")
    responsavel_cliente_ref = models.ForeignKey(
        ContatoCliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manutencoes_como_responsavel",
    )
    responsavel_tecnico_ref = models.ForeignKey(
        ResponsavelCertificado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manutencoes_como_responsavel",
    )
    numero_relatorio = models.CharField(max_length=40, unique=True, blank=True)
    ordem_servico = models.CharField(max_length=40, blank=True)
    tipo_manutencao = models.CharField(max_length=20, choices=TipoManutencao.choices, default=TipoManutencao.PREVENTIVA)
    data_recepcao = models.DateField(null=True, blank=True)
    data_servico = models.DateField()
    data_saida = models.DateField(null=True, blank=True)
    condicao_recebida = models.TextField(blank=True)
    condicao_saida = models.TextField(blank=True)
    diagnostico = models.TextField(blank=True)
    parecer_tecnico = models.TextField(blank=True)
    criterio_aceitacao = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFORME)
    responsavel_tecnico = models.CharField(max_length=120, blank=True)
    observacoes = models.TextField(blank=True)
    proxima_manutencao = models.DateField(null=True, blank=True)
    intervencoes = models.TextField(blank=True, default="", help_text="Descreva as intervenções realizadas.")
    materiais = models.TextField(blank=True, default="", help_text="Liste materiais, peças ou consumíveis.")
    verificacoes = models.TextField(blank=True, default="", help_text="Descreva verificações e testes executados.")
    rastreabilidade = models.TextField(blank=True, default="", help_text="Descreva padrões, certificados e rastreabilidade.")
    resultados = models.TextField(blank=True, default="", help_text="Descreva resultados e evidências relevantes.")
    aprovado_por = models.CharField(max_length=120, blank=True)
    aprovado_cargo = models.CharField(max_length=120, blank=True)
    aprovado_em = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_servico", "-id"]
        verbose_name = "Manutenção"
        verbose_name_plural = "Manutenções"

    def clean(self):
        if self.instrumento_id and self.instrumento.cliente_id:
            self.cliente_id = self.instrumento.cliente_id
        if self.instrumento_id and self.cliente_id and self.instrumento.cliente_id != self.cliente_id:
            raise ValidationError("O instrumento selecionado não pertence ao cliente informado.")

        if self.responsavel_cliente_ref_id:
            if self.responsavel_cliente_ref.cliente_id != self.cliente_id:
                raise ValidationError("O responsável do cliente selecionado não pertence ao mesmo cliente.")
        elif self.cliente_id:
            contato_principal = self.cliente.contatos.filter(principal=True).order_by("nome").first()
            if contato_principal is None:
                contato_principal = self.cliente.contatos.order_by("nome").first()
            if contato_principal:
                self.responsavel_cliente_ref = contato_principal

        if not self.responsavel_tecnico_ref_id:
            self.responsavel_tecnico_ref = _obter_ou_criar_responsavel_padrao()
        if self.responsavel_tecnico_ref_id:
            self.responsavel_tecnico = self.responsavel_tecnico_ref.nome
            if not self.aprovado_por:
                self.aprovado_por = self.responsavel_tecnico_ref.nome
            if self.responsavel_tecnico_ref.cargo and not self.aprovado_cargo:
                self.aprovado_cargo = self.responsavel_tecnico_ref.cargo

    @classmethod
    def proximo_numero_relatorio(cls):
        numeros = []
        for numero in cls.objects.exclude(numero_relatorio="").values_list("numero_relatorio", flat=True):
            match = re.search(r"(\d+)$", numero or "")
            if match:
                numeros.append(int(match.group(1)))
        if not numeros:
            return "MAN-0001"
        return f"MAN-{max(numeros) + 1:04d}"

    def save(self, *args, **kwargs):
        if not self.numero_relatorio:
            self.numero_relatorio = self.proximo_numero_relatorio()
        if not self.responsavel_cliente_ref_id and self.cliente_id:
            contato_principal = self.cliente.contatos.filter(principal=True).order_by("nome").first()
            if contato_principal is None:
                contato_principal = self.cliente.contatos.order_by("nome").first()
            if contato_principal:
                self.responsavel_cliente_ref = contato_principal
        if not self.responsavel_tecnico_ref_id:
            self.responsavel_tecnico_ref = _obter_ou_criar_responsavel_padrao()
        if self.responsavel_tecnico_ref_id:
            self.responsavel_tecnico = self.responsavel_tecnico_ref.nome
            if not self.aprovado_por:
                self.aprovado_por = self.responsavel_tecnico_ref.nome
            if self.responsavel_tecnico_ref.cargo and not self.aprovado_cargo:
                self.aprovado_cargo = self.responsavel_tecnico_ref.cargo
        super().save(*args, **kwargs)

    def __str__(self):
        return self.numero_relatorio


class ManutencaoEvidencia(models.Model):
    manutencao = models.ForeignKey(Manutencao, on_delete=models.CASCADE, related_name="evidencias")
    titulo = models.CharField(max_length=180, blank=True)
    arquivo = models.FileField(upload_to="manutencao/evidencias/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Evidência da manutenção"
        verbose_name_plural = "Evidências da manutenção"

    def __str__(self):
        return self.titulo or self.nome_arquivo

    @property
    def nome_arquivo(self):
        return self.arquivo.name.rsplit("/", 1)[-1]

    @property
    def eh_imagem(self):
        return self.nome_arquivo.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"))
