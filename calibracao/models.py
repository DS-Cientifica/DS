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
from .services.ph_meter_calculation import (
    average as ph_average,
    calcular_incerteza as ph_calcular_incerteza,
    error as ph_error,
    teorico_ph_from_mv as ph_teorico_ph_from_mv,
    stdev as ph_stdev,
)


THREE_DECIMAL_PLACES = Decimal("0.001")
SQRT_12 = Decimal(12).sqrt()


def _quantize_decimal(value, quantizer=THREE_DECIMAL_PLACES):
    if value is None or value == "":
        return value
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value
    return decimal_value.quantize(quantizer)


def _quantize_instance_decimal_fields(instance, quantizer=THREE_DECIMAL_PLACES):
    for field in instance._meta.fields:
        if isinstance(field, models.DecimalField):
            value = getattr(instance, field.attname, None)
            if value is not None:
                setattr(instance, field.attname, _quantize_decimal(value, quantizer))


PRESSAO_UNIDADE_FATORES = {
    "pa": Decimal("1"),
    "hpa": Decimal("100"),
    "kpa": Decimal("1000"),
    "mpa": Decimal("1000000"),
    "bar": Decimal("100000"),
    "mbar": Decimal("100"),
    "psi": Decimal("6894.757293168"),
    "kgf/cm2": Decimal("98066.5"),
    "mmhg": Decimal("133.322387415"),
    "mh2o": Decimal("9806.65"),
    "mmh2o": Decimal("9.80665"),
    "inh2o": Decimal("249.08891"),
}


def _normalizar_unidade_pressao(unidade):
    valor = (unidade or "").strip().lower()
    substituicoes = {
        "kgf/cm²": "kgf/cm2",
        "kgfcm2": "kgf/cm2",
        "kg/cm2": "kgf/cm2",
        "mm hg": "mmhg",
        "m h2o": "mh2o",
        "mm h2o": "mmh2o",
        "in h2o": "inh2o",
        "polh2o": "inh2o",
    }
    return substituicoes.get(valor, valor.replace(" ", ""))


def _para_decimal(valor):
    if valor in (None, ""):
        return None
    if isinstance(valor, Decimal):
        return valor
    try:
        return Decimal(str(valor).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _converter_pressao(valor, unidade_origem, unidade_destino):
    valor_decimal = _para_decimal(valor)
    if valor_decimal is None:
        return None

    origem = PRESSAO_UNIDADE_FATORES.get(_normalizar_unidade_pressao(unidade_origem))
    destino = PRESSAO_UNIDADE_FATORES.get(_normalizar_unidade_pressao(unidade_destino))
    if not origem or not destino:
        return valor_decimal

    valor_pa = valor_decimal * origem
    return valor_pa / destino


def _extrair_faixa_numerica(texto):
    if not texto:
        return None, None
    numeros = re.findall(r"[-+]?\d+(?:[.,]\d+)?", str(texto))
    if len(numeros) < 2:
        return None, None
    return _para_decimal(numeros[0]), _para_decimal(numeros[1])


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


def _formatar_decimal_criterio_texto(valor, casas=3):
    if valor in (None, ""):
        return ""
    try:
        decimal_value = valor if isinstance(valor, Decimal) else Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return str(valor)
    return f"{decimal_value:.{casas}f}".replace(".", ",")


def _casas_decimais_por_resolucao(resolucao, default=4):
    if resolucao in (None, ""):
        return default
    try:
        decimal_value = resolucao if isinstance(resolucao, Decimal) else Decimal(str(resolucao))
    except (InvalidOperation, TypeError, ValueError):
        return default
    normalized = decimal_value.normalize()
    exponent = normalized.as_tuple().exponent
    return max(0, -exponent)


def _formatar_decimal_por_resolucao(valor, resolucao, default=4):
    if valor in (None, ""):
        return "-"
    casas = _casas_decimais_por_resolucao(resolucao, default=default)
    try:
        decimal_value = valor if isinstance(valor, Decimal) else Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return str(valor)
    return f"{decimal_value:.{casas}f}".replace(".", ",")


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


def _incerteza_padrao_por_resolucao(resolucao):
    resolucao_decimal = _para_decimal(resolucao)
    if resolucao_decimal is None:
        return None
    return abs(resolucao_decimal) / SQRT_12


def _incerteza_padrao_por_certificado(incerteza_expandida, fator_k):
    incerteza_decimal = _para_decimal(incerteza_expandida)
    if incerteza_decimal is None:
        return None
    fator_decimal = _para_decimal(fator_k) or Decimal("2")
    if fator_decimal == 0:
        fator_decimal = Decimal("2")
    return abs(incerteza_decimal) / abs(fator_decimal)


def _incerteza_padrao_repetibilidade(desvio_padrao, repeticoes):
    desvio_decimal = _para_decimal(desvio_padrao)
    if desvio_decimal is None:
        return None
    if not repeticoes or repeticoes <= 0:
        return abs(desvio_decimal)
    return abs(desvio_decimal) / Decimal(repeticoes).sqrt()


def _obter_ou_criar_responsavel_padrao():
    responsavel, _ = ResponsavelCertificado.objects.get_or_create(
        nome="Diego Henrique Alves Saldanha",
        defaults={"cargo": "Responsável técnico", "ativo": True},
    )
    return responsavel


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
    tag = models.CharField(max_length=100, blank=True)

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
def _instrumento_clean(self):
    super(Instrumento, self).clean()
    if not self.cliente_id:
        return

    tag = (self.tag or "").strip()

    if tag:
        duplicado = Instrumento.objects.filter(
            cliente_id=self.cliente_id,
            tag__iexact=tag,
        )
        if self.pk:
            duplicado = duplicado.exclude(pk=self.pk)
        if duplicado.exists():
            raise ValidationError(
                {
                    "tag": (
                        "Já existe um instrumento cadastrado para este cliente com o mesmo número de série "
                        "e a mesma TAG."
                    )
                }
            )


Instrumento.clean = _instrumento_clean


def _instrumento_clean_por_cliente_tag(self):
    super(Instrumento, self).clean()
    if not self.cliente_id:
        return

    tag = (self.tag or "").strip()
    if not tag:
        return

    duplicado = Instrumento.objects.filter(
        cliente_id=self.cliente_id,
        tag__iexact=tag,
    )
    if self.pk:
        duplicado = duplicado.exclude(pk=self.pk)
    if duplicado.exists():
        raise ValidationError(
            {
                "tag": (
                    "JÃ¡ existe um instrumento cadastrado para este cliente com a mesma TAG."
                )
            }
        )


Instrumento.clean = _instrumento_clean_por_cliente_tag


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


class ResponsavelCertificado(models.Model):
    nome = models.CharField(max_length=255, unique=True)
    cargo = models.CharField(max_length=255, blank=True, default="Responsável técnico")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Responsável de certificado"
        verbose_name_plural = "Responsáveis de certificado"
        ordering = ("nome",)

    def __str__(self):
        if self.cargo:
            return f"{self.nome} - {self.cargo}"
        return self.nome


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
        _quantize_instance_decimal_fields(self)
        _quantize_instance_decimal_fields(self)
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

    responsavel_tecnico_ref = models.ForeignKey(
        "ResponsavelCertificado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_turbidez_como_responsavel",
    )
    tecnico_executante_ref = models.ForeignKey(
        "ResponsavelCertificado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_turbidez_como_executante",
    )
    ajuste_efetuado = models.BooleanField(default=False)
    tecnico_responsavel = models.CharField(max_length=255, blank=True)
    responsavel_conferencia = models.CharField(max_length=255, blank=True)
    signatario_autorizado = models.CharField(max_length=255, blank=True)
    funcao_signatario = models.CharField(max_length=255, blank=True)
    resultado_final = models.TextField(blank=True)
    observacoes_certificado = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Calibração de Turbidez"
        verbose_name_plural = "Calibrações de Turbidez"
        ordering = ("-data_calibracao", "-created_at")

    def _gerar_prefixo_certificado(self):
        os_token = slugify(self.ordem_servico or "", allow_unicode=False).upper().replace("-", "")
        cliente_token = "CLIENTE"
        if self.cliente_id:
            primeiro_nome = (self.cliente.razao_social or "").strip().split()
            if primeiro_nome:
                cliente_base = slugify(primeiro_nome[0], allow_unicode=False).upper().replace("-", "")
                if cliente_base:
                    cliente_token = cliente_base[:10]

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

        if not self.responsavel_tecnico_ref_id:
            self.responsavel_tecnico_ref = _obter_ou_criar_responsavel_padrao()
        if not self.tecnico_executante_ref_id:
            self.tecnico_executante_ref = self.responsavel_tecnico_ref or _obter_ou_criar_responsavel_padrao()

        if self.responsavel_tecnico_ref_id:
            self.tecnico_responsavel = self.responsavel_tecnico_ref.nome
            self.signatario_autorizado = self.responsavel_tecnico_ref.nome
            if self.responsavel_tecnico_ref.cargo:
                self.funcao_signatario = self.responsavel_tecnico_ref.cargo
        if self.tecnico_executante_ref_id:
            self.responsavel_conferencia = self.tecnico_executante_ref.nome

        if not self.numero_certificado:
            self.numero_certificado = self._gerar_numero_certificado()

        _quantize_instance_decimal_fields(self)
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
        _quantize_instance_decimal_fields(self)
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

        _quantize_instance_decimal_fields(self)
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
            self.media = _quantize_decimal(media)

            if len(leituras) > 1:
                media_float = float(media)
                variancia = sum((float(valor) - media_float) ** 2 for valor in leituras) / (len(leituras) - 1)
                self.desvio_padrao = _quantize_decimal(variancia ** 0.5)

        if self.media is not None and self.valor_referencia is not None:
            self.erro = self.media - self.valor_referencia

        incerteza = (
            self.calibracao.pontos_incerteza.filter(ordem=self.ordem)
            .values_list("incerteza_expandida", flat=True)
            .first()
        )
        if self.erro is not None and incerteza is not None:
            self.ema = _quantize_decimal(abs(self.erro) + incerteza)
        elif self.erro is not None and self.resolucao is not None:
            self.ema = _quantize_decimal(abs(self.erro) + self.resolucao)
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
            self.incerteza_padrao_combinada = _quantize_decimal(combinada)

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
            self.incerteza_expandida = _quantize_decimal(combinada * float(self.fator_k or 2))
        else:
            self.incerteza_padrao_combinada = None
            self.incerteza_expandida = None

        super().save(*args, **kwargs)

        ponto_calibracao = self.calibracao.pontos_calibracao.filter(ordem=self.ordem).first()
        if ponto_calibracao and ponto_calibracao.erro is not None and self.incerteza_expandida is not None:
            ponto_calibracao.ema = _quantize_decimal(abs(ponto_calibracao.erro) + self.incerteza_expandida)
            ponto_calibracao.save(update_fields=["ema"])

    def __str__(self):
        return f"Incerteza {self.ordem}"


class CalibracaoColorimetro(models.Model):
    RESULTADO_FINAL_CHOICES = (
        ("", "---------"),
        ("conforme", "Equipamento conforme, dentro do critério de aceitação informado"),
        ("nao_conforme", "Equipamento não conforme, fora do critério de aceitação informado"),
    )
    TIPO_APLICACAO_CHOICES = (
        ("cloro", "Cloro"),
        ("fluor", "Flúor"),
        ("cor", "Cor"),
        ("fotocolorimetro", "Fotocolorímetro"),
    )
    DOCUMENTO_CODIGO_MAP = {
        "cloro": "CCDS-0002 Rev.00",
        "fluor": "CCDS-0003 Rev.00",
        "cor": "CCDS-0004 Rev.00",
        "fotocolorimetro": "CCDS-0005 Rev.00",
    }
    METODO_CODIGO_MAP = {
        "cloro": "MDS-00043",
        "fluor": "",
        "cor": "",
        "fotocolorimetro": "",
    }
    PREFIXO_CERTIFICADO_MAP = {
        "cloro": "CLOR",
        "fluor": "FLUOR",
        "cor": "COR",
        "fotocolorimetro": "FOTO",
    }
    UNIDADE_MAP = {
        "cloro": "mg/L",
        "fluor": "mg/L",
        "cor": "UA",
        "fotocolorimetro": "mg/L",
    }
    LOCAL_CALIBRACAO_CHOICES = CalibracaoTurbidez.LOCAL_CALIBRACAO_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo_aplicacao = models.CharField(max_length=30, choices=TIPO_APLICACAO_CHOICES, default="cloro")

    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.PROTECT,
        related_name="calibracoes_colorimetro",
    )
    padrao_referencia = models.ForeignKey(
        Padrao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_colorimetro_referencia",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="calibracoes_colorimetro",
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

    equipamento_calibrado = models.CharField(max_length=255, default="Colorímetro", blank=True)
    numero_identificacao = models.CharField(max_length=100, blank=True)
    capacidade_total = models.CharField(max_length=100, blank=True)
    faixa_calibrada = models.CharField(max_length=100, blank=True)
    menor_resolucao = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    unidade_leitura = models.CharField(max_length=50, blank=True)

    procedimento_documento = models.ForeignKey(
        Documento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_colorimetro",
    )
    procedimento_numero = models.CharField(max_length=100, blank=True)
    procedimento_revisao = models.CharField(max_length=50, blank=True)

    temperatura_inicial = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    temperatura_final = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    umidade_inicial = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    umidade_final = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    responsavel_tecnico_ref = models.ForeignKey(
        "ResponsavelCertificado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_colorimetro_como_responsavel",
    )
    tecnico_executante_ref = models.ForeignKey(
        "ResponsavelCertificado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_colorimetro_como_executante",
    )
    ajuste_efetuado = models.BooleanField(default=False)
    tecnico_responsavel = models.CharField(max_length=255, blank=True)
    responsavel_conferencia = models.CharField(max_length=255, blank=True)
    signatario_autorizado = models.CharField(max_length=255, blank=True)
    funcao_signatario = models.CharField(max_length=255, blank=True)
    resultado_final_status = models.CharField(max_length=30, choices=RESULTADO_FINAL_CHOICES, blank=True)
    resultado_final = models.TextField(blank=True)
    observacoes_certificado = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Calibração de Colorímetro"
        verbose_name_plural = "Calibrações de Colorímetro"
        ordering = ("-data_calibracao", "-created_at")

    @property
    def codigo_documento(self):
        return self.DOCUMENTO_CODIGO_MAP.get(self.tipo_aplicacao, "CCDS-0002 Rev.00")

    @property
    def titulo_certificado(self):
        return f"Calibração de Colorímetro - {self.get_tipo_aplicacao_display()}"

    @property
    def resultado_final_resolvido(self):
        partes = []

        status_texto = self._texto_resultado_final_status()
        if status_texto:
            partes.append(status_texto.rstrip("."))

        if self.resultado_final:
            partes.append(self.resultado_final.strip())

        if partes:
            return ". ".join([parte for parte in partes if parte]).strip() + "."

        return self._gerar_resultado_final()

    def _gerar_prefixo_certificado(self):
        os_token = slugify(self.ordem_servico or "", allow_unicode=False).upper().replace("-", "")
        cliente_token = "CLIENTE"
        if self.cliente_id:
            primeiro_nome = (self.cliente.razao_social or "").strip().split()
            if primeiro_nome:
                cliente_base = slugify(primeiro_nome[0], allow_unicode=False).upper().replace("-", "")
                if cliente_base:
                    cliente_token = cliente_base[:12]
        if os_token:
            return f"{cliente_token}-{os_token}"
        data_token = (self.data_calibracao or date.today()).strftime("%Y%m%d")
        return f"{cliente_token}-{data_token}"

    def _gerar_numero_certificado(self):
        prefixo = self._gerar_prefixo_certificado()
        tipo_token = self.PREFIXO_CERTIFICADO_MAP.get(self.tipo_aplicacao, "COLOR")
        existentes = (
            CalibracaoColorimetro.objects.exclude(pk=self.pk)
            .filter(numero_certificado__startswith=f"{prefixo}/")
            .values_list("numero_certificado", flat=True)
        )
        sufixos = set()
        for numero in existentes:
            try:
                restante = str(numero)[len(prefixo) + 1 :]
                sequencia_texto = restante.split("-", 1)[0]
                sufixos.add(int(sequencia_texto))
            except (TypeError, ValueError):
                continue
        sequencia = 1
        while sequencia in sufixos:
            sequencia += 1
        return f"{prefixo}/{sequencia:02d}-{tipo_token}"

    def _obter_documento_metodo_padrao(self):
        codigo = self.METODO_CODIGO_MAP.get(self.tipo_aplicacao, "")
        queryset = Documento.objects.filter(
            status="vigente",
            tipo__in=("metodo", "procedimento", "instrucao"),
        )

        if codigo:
            documento = queryset.filter(codigo__iexact=codigo).order_by("codigo", "titulo").first()
            if documento:
                return documento

        termo_principal = self.get_tipo_aplicacao_display()
        documento = queryset.filter(titulo__icontains=termo_principal).order_by("codigo", "titulo").first()
        if documento:
            return documento

        return queryset.filter(titulo__icontains="color").order_by("codigo", "titulo").first()

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

        self.local_calibracao = CalibracaoTurbidez._normalizar_local_calibracao(
            self.local_calibracao or (self.instrumento.local_instalacao if self.instrumento_id else "")
        )

        if not self.unidade_leitura:
            self.unidade_leitura = self.UNIDADE_MAP.get(self.tipo_aplicacao, "mg/L")

        documento_padrao = self._obter_documento_metodo_padrao()
        if documento_padrao and not self.procedimento_documento_id:
            self.procedimento_documento = documento_padrao

        if self.procedimento_documento_id:
            self.procedimento_numero = self.procedimento_documento.codigo or ""
            self.procedimento_revisao = self.procedimento_documento.revisao or ""

        if not self.responsavel_tecnico_ref_id:
            self.responsavel_tecnico_ref = _obter_ou_criar_responsavel_padrao()
        if not self.tecnico_executante_ref_id:
            self.tecnico_executante_ref = self.responsavel_tecnico_ref or _obter_ou_criar_responsavel_padrao()

        if self.responsavel_tecnico_ref_id:
            self.tecnico_responsavel = self.responsavel_tecnico_ref.nome
            self.signatario_autorizado = self.responsavel_tecnico_ref.nome
            if self.responsavel_tecnico_ref.cargo:
                self.funcao_signatario = self.responsavel_tecnico_ref.cargo
        if self.tecnico_executante_ref_id:
            self.responsavel_conferencia = self.tecnico_executante_ref.nome

        if not self.numero_certificado:
            self.numero_certificado = self._gerar_numero_certificado()

        _quantize_instance_decimal_fields(self)
        super().save(*args, **kwargs)
        self.sincronizar_padrao_referencia_utilizado()

    def _gerar_resultado_final(self):
        status_texto = self._texto_resultado_final_status()
        if status_texto:
            return status_texto
        pontos = list(self.pontos_calibracao.all())
        if not pontos:
            return ""

        erros = [abs(ponto.erro) for ponto in pontos if ponto.erro is not None]
        referencias = [ponto.valor_referencia for ponto in pontos if ponto.valor_referencia is not None]
        if not erros or not referencias:
            return ""

        erro_maximo = max(erros)
        referencia_min = min(referencias)
        referencia_max = max(referencias)

        resultados_verificacao = [
            ponto.resultado for ponto in self.pontos_verificacao.all() if ponto.resultado
        ]
        conforme = all(resultado == "OK" for resultado in resultados_verificacao) if resultados_verificacao else True
        status_texto = "encontra-se conforme" if conforme else "não se encontra conforme"

        return (
            f"O instrumento apresentou erro máximo de {erro_maximo:.4f}".replace(".", ",")
            + f" {self.unidade_leitura or 'mg/L'} na faixa calibrada de "
            + f"{referencia_min:.4f}".replace(".", ",")
            + " a "
            + f"{referencia_max:.4f}".replace(".", ",")
            + f" {self.unidade_leitura or 'mg/L'} e {status_texto} os critérios estabelecidos."
        )

    def _texto_resultado_final_status(self):
        if self.resultado_final_status == "conforme":
            return "Equipamento conforme, dentro do critério de aceitação informado."
        if self.resultado_final_status == "nao_conforme":
            return "Equipamento não conforme, fora do critério de aceitação informado."
        return ""

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

    def sincronizar_padrao_referencia_utilizado(self):
        if not self.pk or not self.padrao_referencia_id:
            return None

        padrao_utilizado, _ = ColorimetroPadraoUtilizado.objects.get_or_create(
            calibracao=self,
            tipo="calibracao",
            ordem=1,
        )
        padrao_utilizado.padrao = self.padrao_referencia
        padrao_utilizado.codigo = self.padrao_referencia.codigo or ""
        padrao_utilizado.descricao = self.padrao_referencia.descricao or ""
        padrao_utilizado.numero_certificado = self.padrao_referencia.numero_certificado or ""
        padrao_utilizado.laboratorio_emitente = self.padrao_referencia.laboratorio_emitente or ""
        padrao_utilizado.data_calibracao = self.padrao_referencia.data_calibracao
        padrao_utilizado.validade = self.padrao_referencia.vencimento
        padrao_utilizado.resolucao = self.padrao_referencia.resolucao
        padrao_utilizado.incerteza = self.padrao_referencia.incerteza
        padrao_utilizado.fator_k = self.padrao_referencia.fator_k
        padrao_utilizado.graus_liberdade = self.padrao_referencia.graus_liberdade
        padrao_utilizado.unidade = self.padrao_referencia.unidade or self.unidade_leitura
        padrao_utilizado.valor_nominal = self.padrao_referencia.valor_nominal
        padrao_utilizado.save()
        return padrao_utilizado

    def sincronizar_pontos_incerteza(self):
        if not self.pk:
            return

        pontos_calibracao = list(self.pontos_calibracao.all())
        pontos_calibracao.sort(
            key=lambda ponto: (
                ponto.valor_referencia is None,
                ponto.valor_referencia or Decimal("0"),
                ponto.ordem,
                str(ponto.pk),
            )
        )
        for nova_ordem, ponto in enumerate(pontos_calibracao, start=1):
            if ponto.ordem != nova_ordem:
                ponto.ordem = nova_ordem
                ponto.save(update_fields=["ordem"])

        ordens_existentes = list(
            self.pontos_calibracao.order_by("ordem").values_list("ordem", flat=True)
        )
        if not ordens_existentes:
            self.pontos_incerteza.all().delete()
            return

        self.pontos_incerteza.exclude(ordem__in=ordens_existentes).delete()

        for ordem in ordens_existentes:
            ponto_incerteza, _ = ColorimetroIncertezaPonto.objects.get_or_create(
                calibracao=self,
                ordem=ordem,
            )
            ponto_incerteza.repetibilidade = None
            ponto_incerteza.resolucao_instrumento = None
            ponto_incerteza.incerteza_padrao = None
            ponto_incerteza.resolucao_padrao = None
            ponto_incerteza.graus_liberdade = None
            ponto_incerteza.incerteza_padrao_combinada = None
            ponto_incerteza.incerteza_expandida = None
            ponto_incerteza.save()


class ColorimetroPadraoUtilizado(models.Model):
    TIPO_CHOICES = (
        ("verificacao", "Padrões da verificação"),
        ("calibracao", "Padrões da calibração"),
        ("termometro", "Termômetro ambiente"),
        ("higrometro", "Higrômetro ambiente"),
    )

    calibracao = models.ForeignKey(
        CalibracaoColorimetro,
        on_delete=models.CASCADE,
        related_name="padroes_utilizados",
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    ordem = models.PositiveSmallIntegerField(default=1)
    padrao = models.ForeignKey(
        Padrao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usos_colorimetro",
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
    unidade = models.CharField(max_length=30, blank=True)
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
        if not self.unidade:
            self.unidade = self.calibracao.unidade_leitura
        _quantize_instance_decimal_fields(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.codigo or self.descricao or self.ordem}"


class ColorimetroVerificacaoPonto(models.Model):
    CRITERIO_ORIGEM_CHOICES = (
        ("", "---------"),
        ("cliente", "Cliente"),
        ("fabricante", "Fabricante"),
    )
    CRITERIO_TIPO_CHOICES = (
        ("numerico", "Numérico"),
        ("percentual", "Percentual (%)"),
    )
    calibracao = models.ForeignKey(
        CalibracaoColorimetro,
        on_delete=models.CASCADE,
        related_name="pontos_verificacao",
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    valor_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    erro = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    criterio = models.CharField(max_length=120, blank=True)
    criterio_tipo = models.CharField(
        "Tipo do critério",
        max_length=20,
        choices=CRITERIO_TIPO_CHOICES,
        default="numerico",
        blank=True,
    )
    criterio_origem = models.CharField(max_length=30, choices=CRITERIO_ORIGEM_CHOICES, blank=True)
    criterio_referencia = models.CharField(max_length=255, blank=True)
    resultado = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = "Ponto de verificação"
        verbose_name_plural = "Pontos de verificação"
        ordering = ("ordem",)

    def _tipo_criterio_resolvido(self):
        return self.criterio_tipo or "numerico"

    @property
    def tolerancia_resolvida(self):
        tolerancia_base = _extrair_decimal_criterio(self.criterio)
        if tolerancia_base is None:
            return None
        if self._tipo_criterio_resolvido() == "percentual":
            if self.valor_padrao is None:
                return None
            return _quantize_decimal(abs(self.valor_padrao) * tolerancia_base / Decimal("100"))
        return tolerancia_base

    @property
    def criterio_formatado(self):
        tolerancia_base = _extrair_decimal_criterio(self.criterio)
        if tolerancia_base is None:
            return self.criterio or ""
        valor_fmt = _formatar_decimal_criterio_texto(tolerancia_base)
        if self._tipo_criterio_resolvido() == "percentual":
            return f"{valor_fmt} %"
        return valor_fmt

    def save(self, *args, **kwargs):
        if self.valor_padrao is not None and self.leitura is not None:
            self.erro = self.leitura - self.valor_padrao
        tolerancia = self.tolerancia_resolvida
        if tolerancia is not None and self.erro is not None:
            self.resultado = "OK" if abs(self.erro) <= tolerancia else "NÃO OK"
        else:
            self.resultado = ""
        _quantize_instance_decimal_fields(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Verificação {self.ordem}"


class ColorimetroCalibracaoPonto(models.Model):
    CRITERIO_ORIGEM_CHOICES = ColorimetroVerificacaoPonto.CRITERIO_ORIGEM_CHOICES
    CRITERIO_TIPO_CHOICES = ColorimetroVerificacaoPonto.CRITERIO_TIPO_CHOICES
    calibracao = models.ForeignKey(
        CalibracaoColorimetro,
        on_delete=models.CASCADE,
        related_name="pontos_calibracao",
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    valor_referencia = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura_1 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura_2 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura_3 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    media = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    desvio_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    erro = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    ema = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    criterio = models.CharField(max_length=120, blank=True)
    criterio_tipo = models.CharField(
        "Tipo do critério",
        max_length=20,
        choices=CRITERIO_TIPO_CHOICES,
        default="numerico",
        blank=True,
    )
    criterio_origem = models.CharField(max_length=30, choices=CRITERIO_ORIGEM_CHOICES, blank=True)
    criterio_referencia = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Ponto de calibração"
        verbose_name_plural = "Pontos de calibração"
        ordering = ("ordem",)

    def _tipo_criterio_resolvido(self):
        return self.criterio_tipo or "numerico"

    @property
    def tolerancia_resolvida(self):
        tolerancia_base = _extrair_decimal_criterio(self.criterio)
        if tolerancia_base is None:
            return None
        if self._tipo_criterio_resolvido() == "percentual":
            if self.valor_referencia is None:
                return None
            return _quantize_decimal(abs(self.valor_referencia) * tolerancia_base / Decimal("100"))
        return tolerancia_base

    @property
    def criterio_formatado(self):
        tolerancia_base = _extrair_decimal_criterio(self.criterio)
        if tolerancia_base is None:
            return self.criterio or ""
        valor_fmt = _formatar_decimal_criterio_texto(tolerancia_base)
        if self._tipo_criterio_resolvido() == "percentual":
            return f"{valor_fmt} %"
        return valor_fmt

    def save(self, *args, **kwargs):
        leituras = [valor for valor in (self.leitura_1, self.leitura_2, self.leitura_3) if valor is not None]
        if self.resolucao is None:
            try:
                self.resolucao = self.calibracao.instrumento.tecnico.menor_resolucao
            except InstrumentoTecnico.DoesNotExist:
                self.resolucao = None
        if leituras:
            media = sum(leituras) / len(leituras)
            self.media = _quantize_decimal(media)
            if len(leituras) > 1:
                media_float = float(media)
                variancia = sum((float(valor) - media_float) ** 2 for valor in leituras) / (len(leituras) - 1)
                self.desvio_padrao = _quantize_decimal(variancia ** 0.5)
        if self.media is not None and self.valor_referencia is not None:
            self.erro = self.media - self.valor_referencia
        incerteza = (
            self.calibracao.pontos_incerteza.filter(ordem=self.ordem)
            .values_list("incerteza_expandida", flat=True)
            .first()
        )
        if self.erro is not None and incerteza is not None:
            self.ema = _quantize_decimal(abs(self.erro) + incerteza)
        elif self.erro is not None and self.resolucao is not None:
            self.ema = _quantize_decimal(abs(self.erro) + self.resolucao)
        else:
            self.ema = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Calibração {self.ordem}"


class ColorimetroIncertezaPonto(models.Model):
    calibracao = models.ForeignKey(
        CalibracaoColorimetro,
        on_delete=models.CASCADE,
        related_name="pontos_incerteza",
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    repetibilidade = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao_instrumento = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_curva = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
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
            or padroes.filter(tipo="calibracao").order_by("ordem").first()
            or (
                ColorimetroPadraoUtilizado(
                    calibracao=self.calibracao,
                    tipo="calibracao",
                    ordem=1,
                    padrao=self.calibracao.padrao_referencia,
                )
                if self.calibracao.padrao_referencia_id
                else None
            )
        )

    def save(self, *args, **kwargs):
        ponto_calibracao = self.calibracao.pontos_calibracao.filter(ordem=self.ordem).first()
        padrao_referencia = self._obter_padrao_referencia()

        if self.repetibilidade is None and ponto_calibracao and ponto_calibracao.desvio_padrao is not None:
            self.repetibilidade = ponto_calibracao.desvio_padrao
        if self.resolucao_instrumento is None:
            try:
                self.resolucao_instrumento = self.calibracao.instrumento.tecnico.menor_resolucao
            except InstrumentoTecnico.DoesNotExist:
                self.resolucao_instrumento = None
        if padrao_referencia:
            if self.incerteza_padrao is None:
                self.incerteza_padrao = padrao_referencia.incerteza
            if self.resolucao_padrao is None:
                self.resolucao_padrao = padrao_referencia.resolucao

        repeticoes = 0
        if ponto_calibracao:
            repeticoes = len([
                valor for valor in (
                    ponto_calibracao.leitura_1,
                    ponto_calibracao.leitura_2,
                    ponto_calibracao.leitura_3,
                ) if valor is not None
            ])

        componentes_padrao = [
            _incerteza_padrao_repetibilidade(self.repetibilidade, repeticoes),
            _incerteza_padrao_por_resolucao(self.resolucao_instrumento),
            _incerteza_padrao_por_certificado(
                self.incerteza_padrao,
                getattr(padrao_referencia, "fator_k", None) if padrao_referencia else None,
            ),
            _incerteza_padrao_por_resolucao(self.resolucao_padrao),
            _para_decimal(self.incerteza_curva),
        ]
        componentes = [float(valor) for valor in componentes_padrao if valor is not None]

        if componentes:
            combinada = sum(valor ** 2 for valor in componentes) ** 0.5
            self.incerteza_padrao_combinada = _quantize_decimal(combinada)
            graus_repetibilidade = max(repeticoes - 1, 0)
            if (
                self.repetibilidade is not None
                and float(self.repetibilidade or 0) > 0
                and graus_repetibilidade > 0
                and combinada > 0
            ):
                u_repetibilidade = _incerteza_padrao_repetibilidade(self.repetibilidade, repeticoes)
                parcela = (float(u_repetibilidade or 0) ** 4) / graus_repetibilidade
                self.graus_liberdade = Decimal(str(round((combinada ** 4) / parcela, 2))) if parcela else None
            elif not self.graus_liberdade:
                self.graus_liberdade = None

            self.fator_k = Decimal(str(round(_fator_abrangencia_95(self.graus_liberdade), 3)))
            self.incerteza_expandida = _quantize_decimal(combinada * float(self.fator_k or 2))
        else:
            self.incerteza_padrao_combinada = None
            self.incerteza_expandida = None

        super().save(*args, **kwargs)

        ponto_calibracao = self.calibracao.pontos_calibracao.filter(ordem=self.ordem).first()
        if ponto_calibracao and ponto_calibracao.erro is not None and self.incerteza_expandida is not None:
            ponto_calibracao.ema = _quantize_decimal(abs(ponto_calibracao.erro) + self.incerteza_expandida)
            ponto_calibracao.save(update_fields=["ema"])

    def __str__(self):
        return f"Incerteza {self.ordem}"


class CalibracaoPressao(models.Model):
    RESULTADO_FINAL_CHOICES = (
        ("", "---------"),
        ("conforme", "Equipamento conforme, dentro do critério de aceitação informado"),
        ("nao_conforme", "Equipamento não conforme, fora do critério de aceitação informado"),
    )
    TIPO_INSTRUMENTO_CHOICES = (
        ("manometro", "Manômetro"),
        ("transmissor", "Transmissor de pressão"),
        ("indicador_transmissor", "Indicador e transmissor de pressão"),
        ("vacuometro", "Vacuômetro"),
        ("manovacuometro", "Manovacuômetro"),
        ("pressostato", "Pressostato"),
        ("valvula_seguranca", "VÃ¡lvula de seguranÃ§a"),
        ("esfigmomanometro", "EsfigmomanÃ´metro"),
    )
    TIPO_INDICACAO_CHOICES = (
        ("analogico", "Analógico"),
        ("digital", "Digital"),
    )
    REFERENCIA_ESCOLHA_CHOICES = (
        ("padrao", "Padrão"),
        ("instrumento", "Instrumento"),
    )
    UNIDADE_CHOICES = (
        ("Pa", "Pa"),
        ("hPa", "hPa"),
        ("kPa", "kPa"),
        ("MPa", "MPa"),
        ("bar", "bar"),
        ("mbar", "mbar"),
        ("psi", "psi"),
        ("kgf/cm2", "kgf/cm²"),
        ("mmHg", "mmHg"),
        ("mH2O", "mH2O"),
        ("mmH2O", "mmH2O"),
        ("inH2O", "inH2O"),
    )
    LOCAL_CALIBRACAO_CHOICES = (
        ("in_loco", "IN LOCO"),
        ("laboratorio_optico_ds", "Laboratório Pressão DS Científica"),
        ("laboratorio_pressao_ds", "Laboratório Pressão DS Científica"),
        ("ds_cientifica", "DS Científica"),
    )
    DOCUMENTO_CODIGO_MAP = {
        "manometro": "CCDS-0006 Rev.00",
        "transmissor": "CCDS-0007 Rev.00",
        "indicador_transmissor": "CCDS-0008 Rev.00",
        "vacuometro": "CCDS-0009 Rev.00",
        "manovacuometro": "CCDS-0010 Rev.00",
        "pressostato": "CCDS-0011 Rev.00",
        "valvula_seguranca": "CCDS-0006 Rev.00",
        "esfigmomanometro": "CCDS-0006 Rev.00",
    }
    PREFIXO_CERTIFICADO_MAP = {
        "manometro": "PRE",
        "transmissor": "PRE",
        "indicador_transmissor": "PRE",
        "vacuometro": "PRE",
        "manovacuometro": "PRE",
        "pressostato": "PRE",
        "valvula_seguranca": "PRE",
        "esfigmomanometro": "PRE",
    }
    EQUIPAMENTO_CALIBRADO_MAP = {
        "manometro": "Manômetro",
        "transmissor": "Transmissor de pressão",
        "indicador_transmissor": "Indicador e transmissor de pressão",
        "vacuometro": "Vacuômetro",
        "manovacuometro": "Manovacuômetro",
        "pressostato": "Pressostato",
        "valvula_seguranca": "VÃ¡lvula de seguranÃ§a",
        "esfigmomanometro": "EsfigmomanÃ´metro",
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo_instrumento = models.CharField(max_length=30, choices=TIPO_INSTRUMENTO_CHOICES, default="manometro")
    tipo_indicacao = models.CharField(max_length=20, choices=TIPO_INDICACAO_CHOICES, default="digital")
    referencia_calculo = models.CharField(max_length=20, choices=REFERENCIA_ESCOLHA_CHOICES, default="padrao")

    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.PROTECT,
        related_name="calibracoes_pressao",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="calibracoes_pressao",
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

    equipamento_calibrado = models.CharField(max_length=255, default="Instrumento de Pressão", blank=True)
    numero_identificacao = models.CharField(max_length=100, blank=True)
    marca = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    numero_serie = models.CharField(max_length=100, blank=True)
    faixa_indicacao = models.CharField(max_length=120, blank=True)
    faixa_calibrada = models.CharField(max_length=120, blank=True)
    capacidade_total = models.CharField(max_length=100, blank=True)
    menor_resolucao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    classe_declarada = models.CharField(max_length=80, blank=True)
    unidade_indicacao = models.CharField(max_length=20, choices=UNIDADE_CHOICES, default="bar")
    unidade_padrao = models.CharField(max_length=20, choices=UNIDADE_CHOICES, default="bar")
    divisao_escala = models.PositiveIntegerField(null=True, blank=True)
    valor_por_divisao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    procedimento_documento = models.ForeignKey(
        Documento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_pressao",
    )
    procedimento_numero = models.CharField(max_length=100, blank=True)
    procedimento_revisao = models.CharField(max_length=50, blank=True)

    temperatura_inicial = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    temperatura_final = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    umidade_inicial = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    umidade_final = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    responsavel_tecnico_ref = models.ForeignKey(
        "ResponsavelCertificado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_pressao_como_responsavel",
    )
    tecnico_executante_ref = models.ForeignKey(
        "ResponsavelCertificado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_pressao_como_executante",
    )
    ajuste_efetuado = models.BooleanField(default=False)
    tecnico_responsavel = models.CharField(max_length=255, blank=True)
    responsavel_conferencia = models.CharField(max_length=255, blank=True)
    signatario_autorizado = models.CharField(max_length=255, blank=True)
    funcao_signatario = models.CharField(max_length=255, blank=True)
    resultado_final_status = models.CharField(max_length=30, choices=RESULTADO_FINAL_CHOICES, blank=True)
    resultado_final = models.TextField(blank=True)
    observacoes_certificado = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Calibração de Pressão"
        verbose_name_plural = "Calibrações de Pressão"
        ordering = ("-data_calibracao", "-created_at")

    @property
    def codigo_documento(self):
        return self.DOCUMENTO_CODIGO_MAP.get(self.tipo_instrumento, "CCDS-0006 Rev.00")

    @property
    def titulo_certificado(self):
        return f"Certificado de Pressão - {self.get_tipo_instrumento_display()}"

    @property
    def local_calibracao_certificado(self):
        mapa = {
            "in_loco": "IN LOCO",
            "laboratorio_optico_ds": "Laboratório Pressão DS Científica",
            "laboratorio_pressao_ds": "Laboratório Pressão DS Científica",
            "ds_cientifica": "DS Científica",
        }
        return mapa.get(self.local_calibracao, "DS Científica")

    @property
    def metodo_utilizado_titulo(self):
        return "Método utilizado"

    def metodo_utilizado_texto(self):
        return (
            "A calibração do equipamento calibrado foi realizada por comparação direta com padrão de referência "
            "rastreável, considerando as conversões de unidade aplicáveis, as condições ambientais registradas "
            "e as contribuições de incerteza pertinentes ao processo."
        )

    @property
    def resultado_final_resolvido(self):
        partes = []
        status_texto = self._texto_resultado_final_status()
        if status_texto:
            partes.append(status_texto.rstrip("."))
        if self.resultado_final:
            partes.append(self.resultado_final.strip())
        if partes:
            return ". ".join([parte for parte in partes if parte]).strip() + "."
        return self._gerar_resultado_final()

    def _texto_resultado_final_status(self):
        return dict(self.RESULTADO_FINAL_CHOICES).get(self.resultado_final_status, "")

    def _gerar_prefixo_certificado(self):
        prefixo_tipo = self.PREFIXO_CERTIFICADO_MAP.get(self.tipo_instrumento, "PRES")
        os_token = slugify(self.ordem_servico or "", allow_unicode=False).upper().replace("-", "")
        cliente_token = "CLIENTE"
        if self.cliente_id:
            primeiro_nome = (self.cliente.razao_social or "").strip().split()
            if primeiro_nome:
                cliente_base = slugify(primeiro_nome[0], allow_unicode=False).upper().replace("-", "")
                if cliente_base:
                    cliente_token = cliente_base[:10]
        if os_token:
            return f"{prefixo_tipo}-{os_token}-{cliente_token}"
        data_token = (self.data_calibracao or date.today()).strftime("%Y%m%d")
        return f"{prefixo_tipo}-{cliente_token}-{data_token}"

    def _gerar_numero_certificado(self):
        prefixo = self._gerar_prefixo_certificado()
        existentes = (
            CalibracaoPressao.objects.exclude(pk=self.pk)
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

    def _gerar_resultado_final(self):
        pontos = list(self.pontos_calibracao.all())
        if not pontos:
            return ""
        erros = [abs(float(ponto.erro)) for ponto in pontos if ponto.erro is not None]
        referencias = [
            float(ponto.valor_referencia_convertido or ponto.valor_referencia)
            for ponto in pontos
            if (ponto.valor_referencia_convertido is not None or ponto.valor_referencia is not None)
        ]
        if not erros:
            return ""
        erro_maximo = max(erros)
        faixa_inicial = min(referencias) if referencias else None
        faixa_final = max(referencias) if referencias else None
        situacao = "adequado" if self.calcular_status_final() == "conforme" else "inadequado"
        if faixa_inicial is not None and faixa_final is not None:
            return (
                f"O instrumento apresentou erro máximo de {erro_maximo:.4f} {self.unidade_padrao} "
                f"na faixa calibrada de {faixa_inicial:.4f} a {faixa_final:.4f} {self.unidade_padrao} "
                f"e encontra-se {situacao}."
            )
        return f"O instrumento apresentou erro máximo de {erro_maximo:.4f} {self.unidade_padrao}."

    def calcular_status_final(self):
        pontos = list(self.pontos_calibracao.all())
        if not pontos:
            return ""
        resultados = [ponto.resultado for ponto in pontos if ponto.resultado]
        if resultados and any(resultado == "reprovado" for resultado in resultados):
            return "nao_conforme"
        if resultados and all(resultado == "aprovado" for resultado in resultados):
            return "conforme"
        return ""

    def pendencias_certificado(self):
        pendencias = []
        if not self.contratante:
            pendencias.append("Contratante não informado")
        if not self.endereco_cliente:
            pendencias.append("Endereço do cliente não informado")
        if self.temperatura_inicial is None or self.temperatura_final is None:
            pendencias.append("Temperatura ambiental incompleta")
        if self.umidade_inicial is None or self.umidade_final is None:
            pendencias.append("Umidade ambiental incompleta")
        if not self.procedimento_numero:
            pendencias.append("Método utilizado não informado")
        if not self.padroes_utilizados.exists():
            pendencias.append("Padrões utilizados não informados")
        if not self.pontos_calibracao.exists():
            pendencias.append("Pontos de calibração não informados")
        return pendencias

    def _calcular_resolucao_analogica(self):
        inicio, fim = _extrair_faixa_numerica(self.faixa_indicacao or self.faixa_calibrada)
        if inicio is None or fim is None or not self.divisao_escala:
            return None
        try:
            span = abs(fim - inicio)
            return span / Decimal(str(self.divisao_escala))
        except (InvalidOperation, ZeroDivisionError):
            return None

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
        if self.instrumento_id:
            if not self.numero_identificacao:
                self.numero_identificacao = self.instrumento.codigo
            if not self.marca:
                self.marca = self.instrumento.marca or ""
            if not self.modelo:
                self.modelo = self.instrumento.modelo or ""
            if not self.numero_serie:
                self.numero_serie = self.instrumento.numero_serie or ""

        self.local_calibracao = self._normalizar_local_calibracao(
            self.local_calibracao or (self.instrumento.local_instalacao if self.instrumento_id else "")
        )

        if self.instrumento_id:
            try:
                tecnico = self.instrumento.tecnico
            except InstrumentoTecnico.DoesNotExist:
                tecnico = None
            if tecnico:
                if not self.faixa_indicacao:
                    self.faixa_indicacao = tecnico.faixa_medicao or ""
                if not self.faixa_calibrada:
                    self.faixa_calibrada = tecnico.faixa_medicao or ""
                if self.menor_resolucao is None:
                    self.menor_resolucao = tecnico.menor_resolucao
                if not self.capacidade_total:
                    self.capacidade_total = tecnico.capacidade_total or ""
                if not self.classe_declarada:
                    self.classe_declarada = tecnico.classe or ""
                if not self.unidade_indicacao:
                    self.unidade_indicacao = tecnico.unidade or self.unidade_indicacao

        if not self.equipamento_calibrado:
            self.equipamento_calibrado = self.EQUIPAMENTO_CALIBRADO_MAP.get(
                self.tipo_instrumento,
                "Instrumento de Pressão",
            )

        if self.tipo_indicacao == "analogico":
            resolucao_analogica = self._calcular_resolucao_analogica()
            if self.menor_resolucao is None and resolucao_analogica is not None:
                self.menor_resolucao = resolucao_analogica
            if self.valor_por_divisao is None and resolucao_analogica is not None:
                self.valor_por_divisao = resolucao_analogica
        elif self.valor_por_divisao is None and self.menor_resolucao is not None:
            self.valor_por_divisao = self.menor_resolucao

        if self.procedimento_documento_id:
            self.procedimento_numero = self.procedimento_documento.codigo or ""
            self.procedimento_revisao = self.procedimento_documento.revisao or ""

        if not self.responsavel_tecnico_ref_id:
            self.responsavel_tecnico_ref = _obter_ou_criar_responsavel_padrao()
        if not self.tecnico_executante_ref_id:
            self.tecnico_executante_ref = self.responsavel_tecnico_ref or _obter_ou_criar_responsavel_padrao()
        if self.responsavel_tecnico_ref_id:
            self.tecnico_responsavel = self.responsavel_tecnico_ref.nome
            self.signatario_autorizado = self.responsavel_tecnico_ref.nome
            if self.responsavel_tecnico_ref.cargo:
                self.funcao_signatario = self.responsavel_tecnico_ref.cargo
        if self.tecnico_executante_ref_id:
            self.responsavel_conferencia = self.tecnico_executante_ref.nome

        if not self.numero_certificado:
            self.numero_certificado = self._gerar_numero_certificado()

        _quantize_instance_decimal_fields(self)
        super().save(*args, **kwargs)

    @classmethod
    def _normalizar_local_calibracao(cls, valor):
        valor = (valor or "").strip().lower()
        if valor in dict(cls.LOCAL_CALIBRACAO_CHOICES):
            return valor
        if "in loco" in valor or "in_loco" in valor:
            return "in_loco"
        if "press" in valor:
            return "laboratorio_pressao_ds"
        if "optico" in valor or "óptico" in valor:
            return "laboratorio_optico_ds"
        return "ds_cientifica"

    def __str__(self):
        return f"{self.numero_certificado} - {self.instrumento}"


class PressaoPadraoUtilizado(models.Model):
    TIPO_CHOICES = (
        ("padrao_pressao", "Padrão de pressão"),
        ("termometro", "Termômetro ambiente"),
        ("higrometro", "Higrômetro ambiente"),
    )

    calibracao = models.ForeignKey(
        CalibracaoPressao,
        on_delete=models.CASCADE,
        related_name="padroes_utilizados",
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    ordem = models.PositiveSmallIntegerField(default=1)
    padrao = models.ForeignKey(
        Padrao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usos_pressao",
    )
    codigo = models.CharField(max_length=100, blank=True)
    descricao = models.CharField(max_length=255, blank=True)
    tipo_padrao = models.CharField(max_length=120, blank=True)
    numero_certificado = models.CharField(max_length=100, blank=True)
    laboratorio_emitente = models.CharField(max_length=150, blank=True)
    data_calibracao = models.DateField(null=True, blank=True)
    validade = models.DateField(null=True, blank=True)
    resolucao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    fator_k = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    graus_liberdade = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unidade = models.CharField(max_length=30, default="bar", blank=True)
    faixa_inicial = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    faixa_final = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    status_validade = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = "Padrão utilizado - pressão"
        verbose_name_plural = "Padrões utilizados - pressão"
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
            if self.faixa_inicial is None or self.faixa_final is None:
                faixa_inicial, faixa_final = _extrair_faixa_numerica(self.padrao.descricao)
                self.faixa_inicial = self.faixa_inicial if self.faixa_inicial is not None else faixa_inicial
                self.faixa_final = self.faixa_final if self.faixa_final is not None else faixa_final

        if self.validade:
            self.status_validade = "Vencido" if self.validade < date.today() else "Válido"

        _quantize_instance_decimal_fields(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.codigo or self.descricao or self.ordem}"


class PressaoCalibracaoPonto(models.Model):
    RESULTADO_CHOICES = (
        ("", "---------"),
        ("aprovado", "Aprovado"),
        ("reprovado", "Reprovado"),
    )

    calibracao = models.ForeignKey(
        CalibracaoPressao,
        on_delete=models.CASCADE,
        related_name="pontos_calibracao",
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    valor_referencia = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    valor_referencia_convertido = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura_1 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura_2 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura_3 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura_4 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    media = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    desvio_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    erro = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    erro_percentual = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    ema = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    tolerancia = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    criterio = models.CharField(max_length=120, blank=True)
    criterio_origem = models.CharField(
        max_length=30,
        choices=(
            ("", "---------"),
            ("cliente", "Tolerância do cliente"),
            ("fabricante", "Tolerância do fabricante"),
        ),
        blank=True,
        null=True,
        default="",
    )
    criterio_referencia = models.CharField(max_length=255, blank=True, null=True, default="")
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES, blank=True)

    class Meta:
        verbose_name = "Ponto de calibração - pressão"
        verbose_name_plural = "Pontos de calibração - pressão"
        ordering = ("ordem",)

    def save(self, *args, **kwargs):
        if self.criterio_origem is None:
            self.criterio_origem = ""
        if self.criterio_referencia is None:
            self.criterio_referencia = ""
        leituras = [valor for valor in (self.leitura_1, self.leitura_2, self.leitura_3, self.leitura_4) if valor is not None]
        unidade_origem = self.calibracao.unidade_indicacao
        unidade_destino = self.calibracao.unidade_padrao

        if self.valor_referencia is not None:
            self.valor_referencia_convertido = _converter_pressao(
                self.valor_referencia,
                unidade_destino,
                unidade_destino,
            )

        leituras_convertidas = []
        for valor in leituras:
            convertido = _converter_pressao(valor, unidade_origem, unidade_destino)
            if convertido is not None:
                leituras_convertidas.append(convertido)

        if leituras_convertidas:
            media = sum(leituras_convertidas) / len(leituras_convertidas)
            self.media = _quantize_decimal(media)
            if len(leituras_convertidas) > 1:
                media_float = float(media)
                variancia = sum((float(valor) - media_float) ** 2 for valor in leituras_convertidas) / (len(leituras_convertidas) - 1)
                self.desvio_padrao = _quantize_decimal(variancia ** 0.5)

        referencia = self.valor_referencia_convertido
        if referencia is not None and self.media is not None:
            self.erro = _quantize_decimal(self.media - referencia)
            if float(referencia) != 0:
                self.erro_percentual = _quantize_decimal((float(self.erro) / abs(float(referencia))) * 100)

        incerteza = (
            self.calibracao.pontos_incerteza.filter(ordem=self.ordem)
            .values_list("incerteza_expandida", flat=True)
            .first()
        )
        if self.erro is not None and incerteza is not None:
            self.ema = _quantize_decimal(abs(self.erro) + incerteza)

        tolerancia_resolvida = self.tolerancia
        if tolerancia_resolvida is None and self.criterio:
            tolerancia_resolvida = _extrair_decimal_criterio(self.criterio)
            if tolerancia_resolvida is not None:
                self.tolerancia = tolerancia_resolvida

        if tolerancia_resolvida is not None and self.erro is not None:
            self.resultado = "aprovado" if abs(self.erro) <= tolerancia_resolvida else "reprovado"
        elif self.erro is not None:
            self.resultado = ""

        _quantize_instance_decimal_fields(self)
        super().save(*args, **kwargs)

        status_final = self.calibracao.calcular_status_final()
        if status_final != self.calibracao.resultado_final_status:
            CalibracaoPressao.objects.filter(pk=self.calibracao_id).update(resultado_final_status=status_final)

    def __str__(self):
        return f"Pressão {self.ordem}"


class PressaoIncertezaPonto(models.Model):
    calibracao = models.ForeignKey(
        CalibracaoPressao,
        on_delete=models.CASCADE,
        related_name="pontos_incerteza",
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    repetibilidade = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao_instrumento = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_curva = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    fator_k = models.DecimalField(max_digits=8, decimal_places=3, default=2)
    graus_liberdade = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    incerteza_padrao_combinada = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_expandida = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    class Meta:
        verbose_name = "Ponto de incerteza - pressão"
        verbose_name_plural = "Pontos de incerteza - pressão"
        ordering = ("ordem",)

    def _obter_padrao_referencia(self):
        return self.calibracao.padroes_utilizados.filter(tipo="padrao_pressao").order_by("ordem").first()

    def save(self, *args, **kwargs):
        ponto_calibracao = self.calibracao.pontos_calibracao.filter(ordem=self.ordem).first()
        padrao_referencia = self._obter_padrao_referencia()

        if self.repetibilidade is None and ponto_calibracao and ponto_calibracao.desvio_padrao is not None:
            self.repetibilidade = ponto_calibracao.desvio_padrao
        if self.resolucao_instrumento is None:
            self.resolucao_instrumento = self.calibracao.menor_resolucao
        if padrao_referencia:
            if self.incerteza_padrao is None:
                self.incerteza_padrao = padrao_referencia.incerteza
            if self.resolucao_padrao is None:
                self.resolucao_padrao = padrao_referencia.resolucao

        componentes = [
            float(valor)
            for valor in (
                self.repetibilidade,
                self.resolucao_instrumento,
                self.incerteza_padrao,
                self.resolucao_padrao,
                self.incerteza_curva,
            )
            if valor is not None
        ]

        if componentes:
            combinada = sum(valor ** 2 for valor in componentes) ** 0.5
            self.incerteza_padrao_combinada = _quantize_decimal(combinada)
            self.graus_liberdade = Decimal("999999.00")
            self.fator_k = Decimal("2.000")
            self.incerteza_expandida = _quantize_decimal(combinada * float(self.fator_k or 2))
        else:
            self.incerteza_padrao_combinada = None
            self.incerteza_expandida = None

        _quantize_instance_decimal_fields(self)
        super().save(*args, **kwargs)

        if ponto_calibracao and ponto_calibracao.erro is not None and self.incerteza_expandida is not None:
            ponto_calibracao.ema = _quantize_decimal(abs(ponto_calibracao.erro) + self.incerteza_expandida)
            ponto_calibracao.save(update_fields=["ema"])

    def __str__(self):
        return f"Incerteza pressão {self.ordem}"

class CalibracaoCondutividade(models.Model):
    LOCAL_CALIBRACAO_CHOICES = (
        ("laboratorio", "Laboratório"),
        ("externo", "Externo"),
    )

    STATUS_CHOICES = (
        ("rascunho", "Rascunho"),
        ("em_analise", "Em análise"),
        ("emitida", "Emitida"),
        ("cancelada", "Cancelada"),
    )

    RESULTADO_CHOICES = (
        ("aprovado", "Aprovado"),
        ("aprovado_ressalva", "Aprovado com ressalva"),
        ("reprovado", "Reprovado"),
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="calibracoes_condutividade",
    )
    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.PROTECT,
        related_name="calibracoes_condutividade",
    )
    ordem_servico = models.CharField(max_length=50, blank=True)
    numero_certificado = models.CharField(max_length=80, unique=True)
    revisao = models.CharField(max_length=20, blank=True)
    data_calibracao = models.DateField()
    data_emissao = models.DateField(null=True, blank=True)
    local_calibracao = models.CharField(max_length=20, choices=LOCAL_CALIBRACAO_CHOICES, default="laboratorio")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="rascunho")
    resultado_final = models.CharField(max_length=30, choices=RESULTADO_CHOICES, default="aprovado")
    contratante = models.CharField(max_length=255, blank=True)
    endereco_contratante = models.CharField(max_length=255, blank=True)
    endereco_cliente = models.CharField(max_length=255, blank=True)
    equipamento_calibrado = models.CharField(max_length=255, blank=True)
    numero_identificacao = models.CharField(max_length=100, blank=True)
    marca = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    numero_serie = models.CharField(max_length=100, blank=True)
    faixa_capacidade = models.CharField(max_length=120, blank=True)
    resolucao = models.CharField(max_length=50, blank=True)
    unidade_indicacao = models.CharField(max_length=20, blank=True, default="mS/cm")
    unidade_padrao = models.CharField(max_length=20, blank=True, default="mS/cm")
    unidade_leitura = models.CharField(max_length=20, blank=True, default="mS/cm")
    temperatura_referencia = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    identificacao_celula = models.CharField(max_length=100, blank=True)
    constante_celula = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    compensacao_temperatura = models.CharField(max_length=100, blank=True)
    tecnico_responsavel = models.CharField(max_length=255, blank=True)
    responsavel_conferencia = models.CharField(max_length=255, blank=True)
    signatario_autorizado = models.CharField(max_length=255, blank=True)
    funcao_signatario = models.CharField(max_length=255, blank=True)
    temperatura_ambiente = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    umidade_ambiente = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    observacoes = models.TextField(blank=True)
    snapshot_json = models.JSONField(default=dict, blank=True)
    pdf_arquivo = models.FileField(upload_to="calibracoes/condutividade/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Calibração de Condutividade"
        verbose_name_plural = "Calibrações de Condutividade"
        ordering = ("-data_calibracao", "-created_at")

    def save(self, *args, **kwargs):
        if self.instrumento_id and not self.cliente_id:
            self.cliente = self.instrumento.cliente
        if self.cliente_id and not self.contratante:
            self.contratante = self.cliente.razao_social or str(self.cliente)
        if self.cliente_id:
            partes_endereco = [
                getattr(self.cliente, "endereco", ""),
                getattr(self.cliente, "numero", ""),
                getattr(self.cliente, "bairro", ""),
                getattr(self.cliente, "cidade", ""),
                getattr(self.cliente, "uf", ""),
            ]
            endereco = ", ".join([parte for parte in partes_endereco if parte])
            if endereco and not self.endereco_contratante:
                self.endereco_contratante = endereco
            if endereco and not self.endereco_cliente:
                self.endereco_cliente = endereco
        if self.instrumento_id:
            if not self.equipamento_calibrado:
                self.equipamento_calibrado = self.instrumento.descricao or str(self.instrumento)
            if not self.numero_identificacao:
                self.numero_identificacao = self.instrumento.codigo
            if not self.marca:
                self.marca = self.instrumento.marca
            if not self.modelo:
                self.modelo = self.instrumento.modelo
            if not self.numero_serie:
                self.numero_serie = self.instrumento.numero_serie

        if not self.data_emissao and self.data_calibracao:
            self.data_emissao = self.data_calibracao

        _quantize_instance_decimal_fields(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.numero_certificado} - {self.instrumento}"

from . import ph_models
