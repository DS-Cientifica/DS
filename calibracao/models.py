import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from dateutil.relativedelta import relativedelta
from clientes.models import Cliente
from qualidade.models import Documento


def _extrair_decimal_criterio(texto):
    if not texto:
        return None

    correspondencia = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(texto))
    if not correspondencia:
        return None

    try:
        return abs(Decimal(correspondencia.group(0).replace(",", ".")))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _fator_abrangencia_95(graus_liberdade):
    if graus_liberdade in (None, ""):
        return 2

    try:
        veff = float(graus_liberdade)
    except (TypeError, ValueError):
        return 2

    if veff >= 30:
        return 2
    if veff >= 20:
        return 2.09
    if veff >= 15:
        return 2.13
    if veff >= 10:
        return 2.23
    if veff >= 9:
        return 2.26
    if veff >= 8:
        return 2.31
    if veff >= 7:
        return 2.36
    if veff >= 6:
        return 2.45
    if veff >= 5:
        return 2.57
    if veff >= 4:
        return 2.78
    if veff >= 3:
        return 3.18
    if veff >= 2:
        return 4.30
    if veff >= 1:
        return 12.71
    return 2


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
    capacidade_total = models.CharField(max_length=100, blank=True)
    menor_resolucao = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
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
    numero_certificado = models.CharField(max_length=100, blank=True)
    laboratorio_emitente = models.CharField(max_length=150, blank=True)
    data_calibracao = models.DateField(null=True, blank=True)
    resolucao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    fator_k = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    graus_liberdade = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unidade = models.CharField(max_length=30, default="NTU", blank=True)
    valor_nominal = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="valido")

    vencimento = models.DateField()

    certificado = models.FileField(
        upload_to='padroes/',
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.codigo} - {self.descricao}"

    class Meta:
        verbose_name = "Padrão"
        verbose_name_plural = "Padrões"


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
        ("in_loco", "In loco"),
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

    class Meta:
        verbose_name = "Calibração"
        verbose_name_plural = "Calibrações"

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


class PerfilIncertezaTurbidez(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfis_incerteza_turbidez",
    )
    padrao = models.ForeignKey(
        Padrao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfis_incerteza_turbidez",
    )
    resolucao_instrumento = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_curva = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_turbidimetro = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    observacoes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Perfil de incerteza de turbidez"
        verbose_name_plural = "Perfis de incerteza de turbidez"
        ordering = ("nome",)

    def save(self, *args, **kwargs):
        if self.resolucao_instrumento is None and self.instrumento_id:
            try:
                self.resolucao_instrumento = self.instrumento.tecnico.menor_resolucao
            except InstrumentoTecnico.DoesNotExist:
                self.resolucao_instrumento = None
        if self.padrao_id:
            if self.resolucao_padrao is None:
                self.resolucao_padrao = self.padrao.resolucao
            if self.incerteza_padrao is None:
                self.incerteza_padrao = self.padrao.incerteza
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class CalibracaoTurbidez(models.Model):
    LOCAL_CALIBRACAO_CHOICES = (
        ("in_loco", "IN LOCO"),
        ("laboratorio_optico_ds", "Laboratório Óptico DS Científica"),
        ("ds_cientifica", "DS Científica"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.PROTECT,
        related_name="calibracoes_turbidez"
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="calibracoes_turbidez"
    )

    numero_certificado = models.CharField(max_length=100, unique=True, blank=True)
    ordem_servico = models.CharField(max_length=100, blank=True)
    data_calibracao = models.DateField()
    data_emissao = models.DateField(default=date.today)
    revisao = models.CharField(max_length=20, default="00", blank=True)
    local_calibracao = models.CharField(
        max_length=30,
        choices=LOCAL_CALIBRACAO_CHOICES,
        default="ds_cientifica",
    )

    contratante = models.CharField(max_length=255, blank=True)
    endereco_contratante = models.CharField(max_length=255, blank=True)
    endereco_cliente = models.CharField(max_length=255, blank=True)

    equipamento_calibrado = models.CharField(max_length=255, default="Turbidímetro", blank=True)
    numero_identificacao = models.CharField(max_length=100, blank=True)
    capacidade_total = models.CharField(max_length=100, blank=True)
    faixa_calibrada = models.CharField(max_length=100, blank=True)
    menor_resolucao = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    unidade_leitura = models.CharField(max_length=50, default="NTU", blank=True)

    sonda_multiparametro = models.BooleanField(default=False)
    serie_sonda_optica_turbidez = models.CharField(max_length=100, blank=True)
    serie_cabo_multi = models.CharField(max_length=100, blank=True)
    id_sonda_multiparametro = models.CharField(max_length=100, blank=True)
    id_sonda_optica_turbidez = models.CharField(max_length=100, blank=True)
    id_cabo_multi = models.CharField(max_length=100, blank=True)

    procedimento_documento = models.ForeignKey(
        Documento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_turbidez"
    )
    perfil_incerteza = models.ForeignKey(
        "PerfilIncertezaTurbidez",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes",
    )
    procedimento_numero = models.CharField(max_length=100, blank=True)
    procedimento_revisao = models.CharField(max_length=50, blank=True)

    temperatura_inicial = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    temperatura_final = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    umidade_inicial = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    umidade_final = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    ajuste_efetuado = models.BooleanField(default=False)
    tecnico_responsavel = models.CharField(max_length=255, blank=True)
    responsavel_conferencia = models.CharField(max_length=255, blank=True)
    signatario_autorizado = models.CharField(max_length=255, blank=True)
    funcao_signatario = models.CharField(max_length=255, blank=True)
    observacoes_certificado = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Calibração de Turbidez"
        verbose_name_plural = "Calibrações de Turbidez"
        ordering = ("-data_calibracao", "-created_at")

    def _gerar_prefixo_certificado(self):
        os_token = slugify(self.ordem_servico or "", allow_unicode=False).upper().replace("-", "")
        cliente_base = ""
        if self.cliente_id:
            cliente_base = slugify(self.cliente.razao_social or "", allow_unicode=False).upper().replace("-", "")
        cliente_token = cliente_base[:10] if cliente_base else "CLIENTE"

        if os_token:
            return f"TURB-{os_token}-{cliente_token}"

        data_token = (self.data_calibracao or date.today()).strftime("%Y%m%d")
        return f"TURB-{cliente_token}-{data_token}"

    def _gerar_numero_certificado(self):
        prefixo = self._gerar_prefixo_certificado()
        existentes = (
            CalibracaoTurbidez.objects.exclude(pk=self.pk)
            .filter(numero_certificado__startswith=f"{prefixo}-")
            .values_list("numero_certificado", flat=True)
        )
        sufixos = set()
        for numero in existentes:
            try:
                sufixos.add(int(str(numero).rsplit("-", 1)[-1]))
            except (TypeError, ValueError):
                continue

        sequencia = 1
        while sequencia in sufixos:
            sequencia += 1
        return f"{prefixo}-{sequencia:02d}"

    def save(self, *args, **kwargs):
        if isinstance(self.data_calibracao, str):
            self.data_calibracao = date.fromisoformat(self.data_calibracao)

        if not self.cliente_id and self.instrumento_id:
            self.cliente = self.instrumento.cliente

        if not self.contratante and self.cliente_id:
            self.contratante = self.cliente.razao_social

        if not self.endereco_cliente and self.cliente_id:
            partes = [
                getattr(self.cliente, "endereco", ""),
                getattr(self.cliente, "numero", ""),
                getattr(self.cliente, "bairro", ""),
                getattr(self.cliente, "cidade", ""),
                getattr(self.cliente, "uf", ""),
            ]
            self.endereco_cliente = ", ".join([parte for parte in partes if parte])

        if not self.endereco_contratante:
            self.endereco_contratante = self.endereco_cliente

        if not self.numero_identificacao and self.instrumento_id:
            self.numero_identificacao = self.instrumento.codigo

        self.local_calibracao = self._normalizar_local_calibracao(
            self.local_calibracao or (self.instrumento.local_instalacao if self.instrumento_id else "")
        )

        if self.procedimento_documento_id:
            self.procedimento_numero = self.procedimento_documento.codigo or ""
            self.procedimento_revisao = self.procedimento_documento.revisao or ""

        if not self.numero_certificado:
            self.numero_certificado = self._gerar_numero_certificado()

        super().save(*args, **kwargs)

    @classmethod
    def _normalizar_local_calibracao(cls, valor):
        valor = (valor or "").strip().lower()
        if valor in dict(cls.LOCAL_CALIBRACAO_CHOICES):
            return valor
        if "in loco" in valor or "in_loco" in valor:
            return "in_loco"
        if "optico" in valor or "óptico" in valor:
            return "laboratorio_optico_ds"
        return "ds_cientifica"

    def __str__(self):
        return f"{self.numero_certificado} - {self.instrumento}"


class TurbidezPadraoUtilizado(models.Model):

    TIPO_CHOICES = (
        ("padrao_mae", "Padrão mãe"),
        ("preparacao", "Preparação"),
        ("verificacao", "Padrões da verificação"),
        ("calibracao", "Padrões da calibração"),
        ("turbidimetro_padrao", "Turbidímetro padrão"),
        ("termometro", "Termômetro ambiente"),
        ("higrometro", "Higrômetro ambiente"),
    )

    calibracao = models.ForeignKey(
        CalibracaoTurbidez,
        on_delete=models.CASCADE,
        related_name="padroes_utilizados"
    )

    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    ordem = models.PositiveSmallIntegerField(default=1)
    padrao = models.ForeignKey(
        Padrao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usos_turbidez"
    )

    codigo = models.CharField(max_length=100, blank=True)
    descricao = models.CharField(max_length=255, blank=True)
    numero_certificado = models.CharField(max_length=100, blank=True)
    laboratorio_emitente = models.CharField(max_length=150, blank=True)
    data_calibracao = models.DateField(null=True, blank=True)
    validade = models.DateField(null=True, blank=True)
    resolucao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    rastreabilidade = models.CharField(max_length=100, blank=True)
    incerteza = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    fator_k = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    graus_liberdade = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unidade = models.CharField(max_length=30, default="NTU", blank=True)
    valor_nominal = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    class Meta:
        verbose_name = "Padrão utilizado"
        verbose_name_plural = "Padrões utilizados"
        ordering = ("tipo", "ordem")

    def save(self, *args, **kwargs):
        if self.padrao_id:
            if not self.codigo:
                self.codigo = self.padrao.codigo
            if not self.descricao:
                self.descricao = self.padrao.descricao
            if not self.numero_certificado:
                self.numero_certificado = self.padrao.numero_certificado
            if not self.laboratorio_emitente:
                self.laboratorio_emitente = self.padrao.laboratorio_emitente
            if not self.data_calibracao:
                self.data_calibracao = self.padrao.data_calibracao
            if not self.validade:
                self.validade = self.padrao.vencimento
            if not self.numero_certificado and self.padrao.certificado:
                self.numero_certificado = self.padrao.certificado.name.split("/")[-1]
            if self.resolucao is None:
                self.resolucao = self.padrao.resolucao
            if self.incerteza is None:
                self.incerteza = self.padrao.incerteza
            if self.fator_k is None:
                self.fator_k = self.padrao.fator_k
            if self.graus_liberdade is None:
                self.graus_liberdade = self.padrao.graus_liberdade
            if not self.unidade:
                self.unidade = self.padrao.unidade
            if self.valor_nominal is None:
                self.valor_nominal = self.padrao.valor_nominal
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.codigo or self.descricao or self.ordem}"


class TurbidezVerificacaoPonto(models.Model):

    calibracao = models.ForeignKey(
        CalibracaoTurbidez,
        on_delete=models.CASCADE,
        related_name="pontos_verificacao"
    )

    ordem = models.PositiveSmallIntegerField(default=1)
    valor_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    erro = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    criterio = models.CharField(max_length=120, blank=True)
    resultado = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = "Ponto de verificação"
        verbose_name_plural = "Pontos de verificação"
        ordering = ("ordem",)

    def save(self, *args, **kwargs):
        if self.valor_padrao is not None and self.leitura is not None:
            self.erro = self.leitura - self.valor_padrao

        tolerancia = _extrair_decimal_criterio(self.criterio)
        if tolerancia is not None and self.erro is not None:
            self.resultado = "OK" if abs(self.erro) <= tolerancia else "NÃO OK"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Verificação {self.ordem}"


class TurbidezCalibracaoPonto(models.Model):

    calibracao = models.ForeignKey(
        CalibracaoTurbidez,
        on_delete=models.CASCADE,
        related_name="pontos_calibracao"
    )

    ordem = models.PositiveSmallIntegerField(default=1)
    valor_referencia = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura_1 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura_2 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura_3 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    casas_decimais = models.PositiveSmallIntegerField(null=True, blank=True)
    media = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    desvio_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    erro = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    ema = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    criterio = models.CharField(max_length=120, blank=True)

    class Meta:
        verbose_name = "Ponto de calibração"
        verbose_name_plural = "Pontos de calibração"
        ordering = ("ordem",)

    def save(self, *args, **kwargs):
        leituras = [valor for valor in (self.leitura_1, self.leitura_2, self.leitura_3) if valor is not None]

        if self.resolucao is None:
            try:
                self.resolucao = self.calibracao.instrumento.tecnico.menor_resolucao
            except InstrumentoTecnico.DoesNotExist:
                self.resolucao = None

        if leituras:
            media = sum(leituras) / len(leituras)
            self.media = round(media, 6)

            if len(leituras) > 1:
                media_float = float(media)
                variancia = sum((float(valor) - media_float) ** 2 for valor in leituras) / (len(leituras) - 1)
                self.desvio_padrao = round(variancia ** 0.5, 6)

        if self.media is not None and self.valor_referencia is not None:
            self.erro = self.media - self.valor_referencia

        incerteza = (
            self.calibracao.pontos_incerteza.filter(ordem=self.ordem)
            .values_list("incerteza_expandida", flat=True)
            .first()
        )
        if self.erro is not None and incerteza is not None:
            self.ema = Decimal(str(round(float(abs(self.erro)) + float(incerteza), 6)))
        elif self.erro is not None and self.resolucao is not None:
            self.ema = Decimal(str(round(float(abs(self.erro)) + float(self.resolucao), 6)))
        else:
            self.ema = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Calibração {self.ordem}"


class TurbidezIncertezaPonto(models.Model):

    calibracao = models.ForeignKey(
        CalibracaoTurbidez,
        on_delete=models.CASCADE,
        related_name="pontos_incerteza"
    )

    ordem = models.PositiveSmallIntegerField(default=1)
    repetibilidade = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao_instrumento = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_curva = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_turbidimetro = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    fator_k = models.DecimalField(max_digits=8, decimal_places=3, default=2)
    graus_liberdade = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    incerteza_padrao_combinada = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_expandida = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    class Meta:
        verbose_name = "Ponto de incerteza"
        verbose_name_plural = "Pontos de incerteza"
        ordering = ("ordem",)

    def _obter_padrao_referencia(self):
        padroes = self.calibracao.padroes_utilizados
        return (
            padroes.filter(tipo="calibracao", ordem=self.ordem).first()
            or padroes.filter(tipo="verificacao", ordem=self.ordem).first()
            or padroes.filter(tipo="turbidimetro_padrao").order_by("ordem").first()
            or padroes.filter(tipo="padrao_mae").order_by("ordem").first()
        )

    def save(self, *args, **kwargs):
        ponto_calibracao = self.calibracao.pontos_calibracao.filter(ordem=self.ordem).first()
        padrao_referencia = self._obter_padrao_referencia()
        perfil_incerteza = self.calibracao.perfil_incerteza

        if self.repetibilidade is None and ponto_calibracao and ponto_calibracao.desvio_padrao is not None:
            self.repetibilidade = ponto_calibracao.desvio_padrao

        if self.resolucao_instrumento is None:
            try:
                self.resolucao_instrumento = self.calibracao.instrumento.tecnico.menor_resolucao
            except InstrumentoTecnico.DoesNotExist:
                self.resolucao_instrumento = None
        if self.resolucao_instrumento is None and perfil_incerteza:
            self.resolucao_instrumento = perfil_incerteza.resolucao_instrumento

        if padrao_referencia:
            if self.incerteza_padrao is None:
                self.incerteza_padrao = padrao_referencia.incerteza
            if self.resolucao_padrao is None:
                self.resolucao_padrao = padrao_referencia.resolucao

        if perfil_incerteza:
            if self.incerteza_padrao is None:
                self.incerteza_padrao = perfil_incerteza.incerteza_padrao
            if self.resolucao_padrao is None:
                self.resolucao_padrao = perfil_incerteza.resolucao_padrao
            if self.incerteza_curva is None:
                self.incerteza_curva = perfil_incerteza.incerteza_curva
            if self.incerteza_turbidimetro is None:
                self.incerteza_turbidimetro = perfil_incerteza.incerteza_turbidimetro

        componentes = [
            float(valor)
            for valor in (
                self.repetibilidade,
                self.resolucao_instrumento,
                self.incerteza_padrao,
                self.resolucao_padrao,
                self.incerteza_curva,
                self.incerteza_turbidimetro,
            )
            if valor is not None
        ]

        if componentes:
            combinada = sum(valor ** 2 for valor in componentes) ** 0.5
            self.incerteza_padrao_combinada = Decimal(str(round(combinada, 6)))

            repeticoes = 0
            if ponto_calibracao:
                repeticoes = len([
                    valor for valor in (
                        ponto_calibracao.leitura_1,
                        ponto_calibracao.leitura_2,
                        ponto_calibracao.leitura_3,
                    ) if valor is not None
                ])

            graus_repetibilidade = max(repeticoes - 1, 0)
            if (
                self.repetibilidade is not None
                and float(self.repetibilidade or 0) > 0
                and graus_repetibilidade > 0
                and combinada > 0
            ):
                parcela = (float(self.repetibilidade) ** 4) / graus_repetibilidade
                self.graus_liberdade = Decimal(str(round((combinada ** 4) / parcela, 2))) if parcela else None
            elif not self.graus_liberdade:
                self.graus_liberdade = None

            self.fator_k = Decimal(str(round(_fator_abrangencia_95(self.graus_liberdade), 3)))
            self.incerteza_expandida = Decimal(str(round(combinada * float(self.fator_k or 2), 6)))
        else:
            self.incerteza_padrao_combinada = None
            self.incerteza_expandida = None

        super().save(*args, **kwargs)

        ponto_calibracao = self.calibracao.pontos_calibracao.filter(ordem=self.ordem).first()
        if ponto_calibracao and ponto_calibracao.erro is not None and self.incerteza_expandida is not None:
            ponto_calibracao.ema = Decimal(str(round(float(abs(ponto_calibracao.erro)) + float(self.incerteza_expandida), 6)))
            ponto_calibracao.save(update_fields=["ema"])

    def __str__(self):
        return f"Incerteza {self.ordem}"
