import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from clientes.models import Cliente
from qualidade.models import Documento

from .models import (
    Instrumento,
    InstrumentoTecnico,
    Padrao,
    ResponsavelCertificado,
    salvar_com_numero_certificado,
)
from .services.balance_calculation import (
    average,
    convert_mass,
    correction_from_error,
    eccentricity_standard_uncertainty,
    format_by_resolution,
    indication_error,
    sample_standard_deviation,
    select_significant_components,
    standard_uncertainty_from_certificate,
    standard_uncertainty_from_rectangular_limit,
    standard_uncertainty_from_resolution,
)


MASS_UNIT_CHOICES = (
    ("mg", "mg"),
    ("g", "g"),
    ("kg", "kg"),
    ("t", "t"),
)
CONDITION_CHOICES = (
    ("encontrado", "Como encontrado"),
    ("deixado", "Como deixado"),
)
DECISION_RULE_CHOICES = (
    ("", "Sem declaração de conformidade"),
    ("aceitacao_simples", "Aceitação simples: |erro| ≤ tolerância"),
    ("guard_band", "Faixa de guarda: |erro| + U ≤ tolerância"),
)


def _quantize(value, places="0.000000001"):
    if value in (None, ""):
        return value
    return Decimal(str(value)).quantize(Decimal(places))


def _client_address(client):
    if not client:
        return ""
    parts = [
        getattr(client, "endereco", ""),
        getattr(client, "numero", ""),
        getattr(client, "bairro", ""),
        getattr(client, "cidade", ""),
        getattr(client, "uf", ""),
    ]
    return ", ".join(str(part) for part in parts if part)


class CalibracaoBalanca(models.Model):
    STATUS_CHOICES = (
        ("rascunho", "Rascunho"),
        ("concluida", "Concluída"),
        ("emitida", "Certificado emitido"),
        ("cancelada", "Cancelada"),
    )
    LOCAL_CHOICES = (
        ("laboratorio", "Laboratório DS Científica"),
        ("in_loco", "IN LOCO"),
    )
    TIPO_CHOICES = (
        ("intervalo_unico", "Intervalo único"),
        ("multi_intervalo", "Multi-intervalo"),
        ("multiplos_intervalos", "Múltiplos intervalos"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.PROTECT,
        related_name="calibracoes_balanca",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="calibracoes_balanca",
    )
    numero_certificado = models.CharField(max_length=100, unique=True, blank=True)
    ordem_servico = models.CharField("Ordem de serviço", max_length=100, blank=True)
    data_calibracao = models.DateField("Data da calibração")
    data_emissao = models.DateField("Data de emissão", default=date.today)
    revisao = models.CharField("Revisão", max_length=20, default="00", blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="rascunho")
    local_calibracao = models.CharField(
        "Local da calibração",
        max_length=20,
        choices=LOCAL_CHOICES,
        default="laboratorio",
    )

    contratante = models.CharField(max_length=255, blank=True)
    endereco_contratante = models.CharField("Endereço do contratante", max_length=255, blank=True)
    endereco_cliente = models.CharField("Endereço do cliente", max_length=255, blank=True)
    equipamento_calibrado = models.CharField(max_length=255, default="Balança", blank=True)
    numero_identificacao = models.CharField("Número de identificação", max_length=100, blank=True)
    marca = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    numero_serie = models.CharField("Número de série", max_length=100, blank=True)
    tipo_instrumento = models.CharField(max_length=30, choices=TIPO_CHOICES, default="intervalo_unico")
    classe_exatidao = models.CharField("Classe de exatidão declarada", max_length=30, blank=True)
    capacidade_maxima = models.DecimalField("Capacidade máxima (Max)", max_digits=20, decimal_places=9)
    capacidade_minima = models.DecimalField(
        "Capacidade mínima (Min)", max_digits=20, decimal_places=9, null=True, blank=True
    )
    divisao_escala = models.DecimalField("Divisão de escala (d)", max_digits=20, decimal_places=9)
    intervalo_verificacao = models.DecimalField(
        "Intervalo de verificação (e)", max_digits=20, decimal_places=9, null=True, blank=True
    )
    unidade = models.CharField(max_length=5, choices=MASS_UNIT_CHOICES, default="g")
    dispositivo_zero = models.CharField(
        "Dispositivo de zero/rastreamento durante os ensaios", max_length=120, blank=True
    )

    procedimento_documento = models.ForeignKey(
        Documento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_balanca",
    )
    metodo_referencia = models.CharField(
        "Método/referência",
        max_length=255,
        default="EURAMET Calibration Guide No. 18, versão 4.0",
    )
    temperatura_inicial = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    temperatura_final = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    umidade_inicial = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    umidade_final = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    pressao_atmosferica = models.DecimalField(
        "Pressão atmosférica (hPa)", max_digits=8, decimal_places=2, null=True, blank=True
    )
    nivelamento_verificado = models.BooleanField(default=False)
    ajuste_efetuado = models.BooleanField(default=False)
    autorizacao_ajuste = models.CharField("Autorização do ajuste", max_length=255, blank=True)

    regra_decisao = models.CharField(
        "Regra de decisão",
        max_length=30,
        choices=DECISION_RULE_CHOICES,
        blank=True,
    )
    criterio_referencia = models.CharField(
        "Referência do critério de aceitação", max_length=255, blank=True
    )
    responsavel_tecnico_ref = models.ForeignKey(
        ResponsavelCertificado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_balanca_como_responsavel",
    )
    tecnico_executante_ref = models.ForeignKey(
        ResponsavelCertificado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_balanca_como_executante",
    )
    observacoes_certificado = models.TextField("Observações", blank=True)
    snapshot_json = models.JSONField(default=dict, blank=True)
    pdf_arquivo = models.FileField(upload_to="calibracoes/balanca/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Calibração de Balança"
        verbose_name_plural = "Calibrações de Balança"
        ordering = ("-data_calibracao", "-created_at")

    def __str__(self):
        return f"{self.numero_certificado or 'Nova calibração'} - {self.instrumento}"

    def formatar_resultado(self, value, *, casas_adicionais=0):
        return format_by_resolution(value, self.divisao_escala, casas_adicionais)

    @property
    def capacidade_maxima_formatada(self):
        return self.formatar_resultado(self.capacidade_maxima)

    @property
    def capacidade_minima_formatada(self):
        return self.formatar_resultado(self.capacidade_minima)

    @property
    def divisao_escala_formatada(self):
        return self.formatar_resultado(self.divisao_escala)

    @property
    def intervalo_verificacao_formatado(self):
        return self.formatar_resultado(self.intervalo_verificacao)

    def clean(self):
        errors = {}
        if self.capacidade_maxima is not None and self.capacidade_maxima <= 0:
            errors["capacidade_maxima"] = "A capacidade máxima deve ser maior que zero."
        if self.capacidade_minima is not None and self.capacidade_minima < 0:
            errors["capacidade_minima"] = "A capacidade mínima não pode ser negativa."
        if (
            self.capacidade_minima is not None
            and self.capacidade_maxima is not None
            and self.capacidade_minima >= self.capacidade_maxima
        ):
            errors["capacidade_minima"] = "Min deve ser menor que Max."
        if self.divisao_escala is not None and self.divisao_escala <= 0:
            errors["divisao_escala"] = "A divisão de escala deve ser maior que zero."
        if self.ajuste_efetuado and not self.autorizacao_ajuste.strip():
            errors["autorizacao_ajuste"] = "Registre a autorização antes de declarar ajuste efetuado."
        if self.regra_decisao and not self.criterio_referencia.strip():
            errors["criterio_referencia"] = "Informe a origem do critério associado à regra de decisão."
        if errors:
            raise ValidationError(errors)

    def _generate_certificate_number(self):
        client_token = "CLIENTE"
        if self.cliente_id:
            name = (self.cliente.razao_social or "").strip().split()
            if name:
                client_token = slugify(name[0], allow_unicode=False).upper().replace("-", "")[:10]
        os_token = slugify(self.ordem_servico or "", allow_unicode=False).upper().replace("-", "")
        base = f"BAL-{os_token or client_token}-{(self.data_calibracao or date.today()):%Y%m%d}"
        existing = CalibracaoBalanca.objects.exclude(pk=self.pk).filter(
            numero_certificado__startswith=f"{base}-"
        ).values_list("numero_certificado", flat=True)
        suffixes = set()
        for number in existing:
            try:
                suffixes.add(int(str(number).rsplit("-", 1)[-1]))
            except (TypeError, ValueError):
                pass
        sequence = 1
        while sequence in suffixes:
            sequence += 1
        return f"{base}-{sequence:02d}"

    def save(self, *args, **kwargs):
        if self.instrumento_id:
            if not self.cliente_id:
                self.cliente = self.instrumento.cliente
            self.equipamento_calibrado = self.equipamento_calibrado or self.instrumento.descricao or "Balança"
            self.numero_identificacao = self.numero_identificacao or self.instrumento.codigo
            self.marca = self.marca or self.instrumento.marca or ""
            self.modelo = self.modelo or self.instrumento.modelo or ""
            self.numero_serie = self.numero_serie or self.instrumento.numero_serie or ""
            try:
                technical = self.instrumento.tecnico
            except InstrumentoTecnico.DoesNotExist:
                technical = None
            if technical:
                if not self.classe_exatidao:
                    self.classe_exatidao = technical.classe or ""
                if self.divisao_escala is None:
                    self.divisao_escala = technical.menor_resolucao
                if not self.unidade and technical.unidade in dict(MASS_UNIT_CHOICES):
                    self.unidade = technical.unidade
        if self.cliente_id:
            self.contratante = self.contratante or self.cliente.razao_social
            address = _client_address(self.cliente)
            self.endereco_cliente = self.endereco_cliente or address
            self.endereco_contratante = self.endereco_contratante or address
        for field in (
            "capacidade_maxima", "capacidade_minima", "divisao_escala", "intervalo_verificacao"
        ):
            value = getattr(self, field)
            if value is not None:
                setattr(self, field, _quantize(value))
        salvar_com_numero_certificado(self, super().save, args, kwargs)

    def certificate_pending_items(self):
        pending = []
        if not self.procedimento_documento_id:
            pending.append("procedimento vigente não vinculado")
        if None in (self.temperatura_inicial, self.temperatura_final, self.umidade_inicial, self.umidade_final):
            pending.append("condições ambientais incompletas")
        if not self.padroes_utilizados.exists():
            pending.append("padrões não informados")
        if not self.pontos_indicacao.exists():
            pending.append("ensaio de indicação não informado")
        if not self.repetibilidades.exists():
            pending.append("ensaio de repetibilidade não informado")
        if not self.pontos_excentricidade.exists():
            pending.append("ensaio de excentricidade não informado")
        if self.ajuste_efetuado and not self.pontos_indicacao.filter(condicao="encontrado").exists():
            pending.append("resultados como encontrado ausentes")
        if self.ajuste_efetuado and not self.pontos_indicacao.filter(condicao="deixado").exists():
            pending.append("resultados como deixado ausentes")
        return pending


class BalancaPadraoUtilizado(models.Model):
    calibracao = models.ForeignKey(
        CalibracaoBalanca, on_delete=models.CASCADE, related_name="padroes_utilizados"
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    padrao = models.ForeignKey(Padrao, on_delete=models.PROTECT, related_name="usos_em_balancas")
    codigo = models.CharField(max_length=50, blank=True)
    descricao = models.CharField(max_length=255, blank=True)
    classe_oiml = models.CharField("Classe OIML", max_length=20, blank=True)
    numero_certificado = models.CharField("Número do certificado", max_length=100, blank=True)
    laboratorio_emitente = models.CharField("Laboratório emitente", max_length=150, blank=True)
    data_calibracao = models.DateField(null=True, blank=True)
    validade = models.DateField(null=True, blank=True)
    valor_nominal = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    correcao = models.DecimalField("Correção da massa convencional", max_digits=20, decimal_places=9, default=0)
    incerteza_expandida = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    fator_k = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    limite_deriva = models.DecimalField(
        "Limite de deriva adotado (±D)", max_digits=20, decimal_places=9, null=True, blank=True
    )
    densidade = models.DecimalField("Densidade (kg/m³)", max_digits=12, decimal_places=3, null=True, blank=True)
    unidade = models.CharField(max_length=5, choices=MASS_UNIT_CHOICES, default="g")

    class Meta:
        verbose_name = "Peso padrão utilizado"
        verbose_name_plural = "Pesos padrão utilizados"
        ordering = ("ordem",)
        constraints = [
            models.UniqueConstraint(fields=("calibracao", "ordem"), name="unique_balanca_padrao_ordem")
        ]

    def __str__(self):
        return f"{self.codigo or self.padrao.codigo} - {self.valor_nominal or ''} {self.unidade}"

    @property
    def massa_convencional(self):
        if self.valor_nominal is None:
            return None
        return self.valor_nominal + (self.correcao or Decimal("0"))

    @property
    def valor_nominal_formatado(self):
        return self.calibracao.formatar_resultado(
            convert_mass(self.valor_nominal, self.unidade, self.calibracao.unidade)
        )

    @property
    def correcao_formatada(self):
        return self.calibracao.formatar_resultado(
            convert_mass(self.correcao, self.unidade, self.calibracao.unidade),
            casas_adicionais=2,
        )

    @property
    def incerteza_expandida_formatada(self):
        return self.calibracao.formatar_resultado(
            convert_mass(self.incerteza_expandida, self.unidade, self.calibracao.unidade),
            casas_adicionais=2,
        )

    @property
    def validade_status(self):
        if self.validade is None:
            return "Validade não informada"
        return "Válido" if self.validade >= self.calibracao.data_calibracao else "Vencido na data de uso"

    def save(self, *args, **kwargs):
        if self.padrao_id:
            self.codigo = self.codigo or self.padrao.codigo
            self.descricao = self.descricao or self.padrao.descricao
            self.numero_certificado = self.numero_certificado or self.padrao.numero_certificado
            self.laboratorio_emitente = self.laboratorio_emitente or self.padrao.laboratorio_emitente
            self.data_calibracao = self.data_calibracao or self.padrao.data_calibracao
            self.validade = self.validade or self.padrao.vencimento
            self.valor_nominal = self.valor_nominal if self.valor_nominal is not None else self.padrao.valor_nominal
            self.incerteza_expandida = (
                self.incerteza_expandida if self.incerteza_expandida is not None else self.padrao.incerteza
            )
            self.fator_k = self.fator_k if self.fator_k is not None else self.padrao.fator_k
            if self.unidade == "g" and self.padrao.unidade in dict(MASS_UNIT_CHOICES):
                self.unidade = self.padrao.unidade
        super().save(*args, **kwargs)


class BalancaRepetibilidade(models.Model):
    calibracao = models.ForeignKey(
        CalibracaoBalanca, on_delete=models.CASCADE, related_name="repetibilidades"
    )
    condicao = models.CharField(max_length=20, choices=CONDITION_CHOICES, default="encontrado")
    ordem = models.PositiveSmallIntegerField(default=1)
    carga_teste = models.DecimalField(max_digits=20, decimal_places=9)
    leitura_1 = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    leitura_2 = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    leitura_3 = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    leitura_4 = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    leitura_5 = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    leitura_6 = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    leitura_7 = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    leitura_8 = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    leitura_9 = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    leitura_10 = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    media = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    desvio_padrao = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)

    class Meta:
        verbose_name = "Ensaio de repetibilidade"
        verbose_name_plural = "Ensaios de repetibilidade"
        ordering = ("condicao", "ordem")

    @property
    def readings(self):
        return [
            value for value in (
                self.leitura_1, self.leitura_2, self.leitura_3, self.leitura_4, self.leitura_5,
                self.leitura_6, self.leitura_7, self.leitura_8, self.leitura_9, self.leitura_10,
            ) if value is not None
        ]

    @property
    def numero_repeticoes(self):
        return len(self.readings)

    @property
    def carga_teste_formatada(self):
        return self.calibracao.formatar_resultado(self.carga_teste)

    @property
    def media_formatada(self):
        return self.calibracao.formatar_resultado(self.media)

    @property
    def desvio_padrao_formatado(self):
        return self.calibracao.formatar_resultado(self.desvio_padrao, casas_adicionais=2)

    def clean(self):
        load_kg = convert_mass(self.carga_teste, self.calibracao.unidade, "kg")
        minimum = 3 if load_kg is not None and load_kg >= 100 else 5
        if self.numero_repeticoes and self.numero_repeticoes < minimum:
            raise ValidationError(
                f"Registre pelo menos {minimum} aplicações da carga para este ensaio de repetibilidade."
            )

    def save(self, *args, **kwargs):
        self.media = _quantize(average(self.readings)) if self.readings else None
        deviation = sample_standard_deviation(self.readings)
        self.desvio_padrao = _quantize(deviation) if deviation is not None else None
        super().save(*args, **kwargs)


class BalancaExcentricidadePonto(models.Model):
    POSITION_CHOICES = (
        ("centro", "1 - Centro"),
        ("frente_esquerda", "2 - Frente esquerda"),
        ("fundo_esquerda", "3 - Fundo esquerda"),
        ("fundo_direita", "4 - Fundo direita"),
        ("frente_direita", "5 - Frente direita"),
        ("outra", "Outra posição documentada"),
    )
    calibracao = models.ForeignKey(
        CalibracaoBalanca, on_delete=models.CASCADE, related_name="pontos_excentricidade"
    )
    condicao = models.CharField(max_length=20, choices=CONDITION_CHOICES, default="encontrado")
    ordem = models.PositiveSmallIntegerField(default=1)
    posicao = models.CharField(max_length=30, choices=POSITION_CHOICES)
    descricao_posicao = models.CharField(max_length=100, blank=True)
    carga_teste = models.DecimalField(max_digits=20, decimal_places=9)
    indicacao = models.DecimalField(max_digits=20, decimal_places=9)
    indicacao_zero = models.DecimalField(max_digits=20, decimal_places=9, default=0)
    diferenca_centro = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)

    class Meta:
        verbose_name = "Ponto de excentricidade"
        verbose_name_plural = "Pontos de excentricidade"
        ordering = ("condicao", "ordem")

    @property
    def carga_teste_formatada(self):
        return self.calibracao.formatar_resultado(self.carga_teste)

    @property
    def indicacao_formatada(self):
        return self.calibracao.formatar_resultado(self.indicacao)

    @property
    def indicacao_zero_formatada(self):
        return self.calibracao.formatar_resultado(self.indicacao_zero)

    @property
    def diferenca_centro_formatada(self):
        return self.calibracao.formatar_resultado(self.diferenca_centro)

    def recalculate(self, save=True):
        center = self.calibracao.pontos_excentricidade.filter(
            condicao=self.condicao, posicao="centro"
        ).order_by("ordem").first()
        if self.posicao == "centro":
            difference = Decimal("0")
        elif center:
            difference = (self.indicacao - (self.indicacao_zero or Decimal("0"))) - center.indicacao
        else:
            difference = None
        self.diferenca_centro = _quantize(difference) if difference is not None else None
        if save and self.pk:
            type(self).objects.filter(pk=self.pk).update(diferenca_centro=self.diferenca_centro)
        return self.diferenca_centro

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.recalculate(save=True)


class BalancaPontoIndicacao(models.Model):
    calibracao = models.ForeignKey(
        CalibracaoBalanca, on_delete=models.CASCADE, related_name="pontos_indicacao"
    )
    condicao = models.CharField(max_length=20, choices=CONDITION_CHOICES, default="encontrado")
    ordem = models.PositiveSmallIntegerField(default=1)
    carga_nominal = models.DecimalField(max_digits=20, decimal_places=9)
    correcao_padroes = models.DecimalField(
        "Soma das correções dos pesos", max_digits=20, decimal_places=9, default=0
    )
    massa_referencia = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    indicacao_1 = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    indicacao_2 = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    indicacao_3 = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    indicacao_media = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    erro = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    correcao = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    tolerancia = models.DecimalField(
        "Tolerância (±)", max_digits=20, decimal_places=9, null=True, blank=True
    )
    resultado = models.CharField(max_length=30, blank=True)
    padroes_aplicados = models.ManyToManyField(BalancaPadraoUtilizado, blank=True)

    class Meta:
        verbose_name = "Ponto do ensaio de indicação"
        verbose_name_plural = "Pontos do ensaio de indicação"
        ordering = ("condicao", "ordem")
        constraints = [
            models.UniqueConstraint(
                fields=("calibracao", "condicao", "ordem"), name="unique_balanca_indicacao_ordem"
            )
        ]

    @property
    def readings(self):
        return [value for value in (self.indicacao_1, self.indicacao_2, self.indicacao_3) if value is not None]

    @property
    def carga_nominal_formatada(self):
        return self.calibracao.formatar_resultado(self.carga_nominal)

    @property
    def massa_referencia_formatada(self):
        return self.calibracao.formatar_resultado(self.massa_referencia)

    @property
    def indicacao_media_formatada(self):
        return self.calibracao.formatar_resultado(self.indicacao_media)

    @property
    def erro_formatado(self):
        return self.calibracao.formatar_resultado(self.erro)

    @property
    def correcao_formatada(self):
        return self.calibracao.formatar_resultado(self.correcao)

    @property
    def tolerancia_formatada(self):
        return self.calibracao.formatar_resultado(self.tolerancia)

    def recalculate(self, save=True):
        self.massa_referencia = _quantize(self.carga_nominal + (self.correcao_padroes or Decimal("0")))
        mean = average(self.readings)
        self.indicacao_media = _quantize(mean) if mean is not None else None
        error = indication_error(self.indicacao_media, self.massa_referencia)
        self.erro = _quantize(error) if error is not None else None
        correction = correction_from_error(self.erro)
        self.correcao = _quantize(correction) if correction is not None else None
        uncertainty = getattr(getattr(self, "incerteza", None), "incerteza_expandida", None)
        if self.tolerancia is None or self.erro is None or not self.calibracao.regra_decisao:
            self.resultado = ""
        elif self.calibracao.regra_decisao == "guard_band":
            self.resultado = (
                "conforme" if uncertainty is not None and abs(self.erro) + uncertainty <= self.tolerancia
                else "não conforme" if uncertainty is not None else ""
            )
        else:
            self.resultado = "conforme" if abs(self.erro) <= self.tolerancia else "não conforme"
        if save and self.pk:
            type(self).objects.filter(pk=self.pk).update(
                massa_referencia=self.massa_referencia,
                indicacao_media=self.indicacao_media,
                erro=self.erro,
                correcao=self.correcao,
                resultado=self.resultado,
            )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.recalculate(save=True)


class BalancaIncertezaPonto(models.Model):
    ponto = models.OneToOneField(
        BalancaPontoIndicacao, on_delete=models.CASCADE, related_name="incerteza"
    )
    repetibilidade = models.ForeignKey(
        BalancaRepetibilidade, on_delete=models.SET_NULL, null=True, blank=True
    )
    usar_media_indicacoes = models.BooleanField(
        "Considerar média das indicações no termo de repetibilidade", default=False
    )
    u_resolucao_zero = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    u_resolucao_carga = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    u_repetibilidade = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    u_excentricidade = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    u_certificados_pesos = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    u_deriva_pesos = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    u_empuxo_ar = models.DecimalField(
        "u do empuxo do ar", max_digits=20, decimal_places=9, null=True, blank=True
    )
    u_conveccao = models.DecimalField(
        "u da convecção", max_digits=20, decimal_places=9, null=True, blank=True
    )
    u_outros = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    outros_descricao = models.CharField(max_length=255, blank=True)
    limite_variancia_desconsiderada_percentual = models.DecimalField(
        "Limite acumulado de variância desconsiderada (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        help_text=(
            "Somente parcelas cuja variância acumulada permaneça dentro deste limite são "
            "desconsideradas do resultado adotado. Todas continuam registradas para auditoria."
        ),
    )
    incerteza_padrao_combinada_completa = models.DecimalField(
        "Incerteza padrão combinada completa",
        max_digits=20,
        decimal_places=9,
        null=True,
        blank=True,
    )
    incerteza_padrao_combinada = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    percentual_variancia_desconsiderada = models.DecimalField(
        max_digits=7, decimal_places=4, default=0
    )
    componentes_significativos = models.JSONField(default=dict, blank=True)
    componentes_desconsiderados = models.JSONField(default=dict, blank=True)
    fator_k = models.DecimalField(max_digits=8, decimal_places=3, default=2)
    graus_liberdade = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    incerteza_expandida = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)

    class Meta:
        verbose_name = "Incerteza do ponto"
        verbose_name_plural = "Incertezas dos pontos"

    @property
    def incerteza_padrao_combinada_completa_formatada(self):
        return self.ponto.calibracao.formatar_resultado(self.incerteza_padrao_combinada_completa)

    @property
    def incerteza_padrao_combinada_formatada(self):
        return self.ponto.calibracao.formatar_resultado(self.incerteza_padrao_combinada)

    @property
    def incerteza_expandida_formatada(self):
        return self.ponto.calibracao.formatar_resultado(self.incerteza_expandida)

    def recalculate(self, save=True):
        calibration = self.ponto.calibracao
        resolution_u = standard_uncertainty_from_resolution(calibration.divisao_escala)
        self.u_resolucao_zero = _quantize(resolution_u) if resolution_u is not None else None
        self.u_resolucao_carga = _quantize(resolution_u) if resolution_u is not None else None

        if self.repetibilidade and self.repetibilidade.desvio_padrao is not None:
            repeat_u = self.repetibilidade.desvio_padrao
            if self.usar_media_indicacoes and len(self.ponto.readings) > 1:
                repeat_u = repeat_u / Decimal(len(self.ponto.readings)).sqrt()
            self.u_repetibilidade = _quantize(repeat_u)

        eccentric_points = calibration.pontos_excentricidade.filter(condicao=self.ponto.condicao)
        differences = [abs(point.diferenca_centro) for point in eccentric_points if point.diferenca_centro is not None]
        eccentric_load = eccentric_points.exclude(carga_teste__isnull=True).values_list("carga_teste", flat=True).first()
        if differences and eccentric_load and self.ponto.indicacao_media is not None:
            value = eccentricity_standard_uncertainty(
                max(differences), self.ponto.indicacao_media, eccentric_load
            )
            self.u_excentricidade = _quantize(value) if value is not None else None

        certificate_components = []
        drift_components = []
        for standard in self.ponto.padroes_aplicados.all():
            certificate_u = standard_uncertainty_from_certificate(
                standard.incerteza_expandida, standard.fator_k
            )
            if certificate_u is not None:
                certificate_components.append(convert_mass(certificate_u, standard.unidade, calibration.unidade))
            drift_u = standard_uncertainty_from_rectangular_limit(standard.limite_deriva)
            if drift_u is not None:
                drift_components.append(convert_mass(drift_u, standard.unidade, calibration.unidade))
        self.u_certificados_pesos = _quantize(sum(certificate_components, Decimal("0"))) if certificate_components else None
        self.u_deriva_pesos = _quantize(sum(drift_components, Decimal("0"))) if drift_components else None

        selection = select_significant_components({
            "resolução no zero": self.u_resolucao_zero,
            "resolução sob carga": self.u_resolucao_carga,
            "repetibilidade": self.u_repetibilidade,
            "excentricidade": self.u_excentricidade,
            "certificados dos pesos": self.u_certificados_pesos,
            "deriva dos pesos": self.u_deriva_pesos,
            "empuxo do ar": self.u_empuxo_ar,
            "convecção": self.u_conveccao,
            self.outros_descricao.strip() or "outros": self.u_outros,
        }, self.limite_variancia_desconsiderada_percentual)
        complete_combined = selection["complete_combined"]
        combined = selection["adopted_combined"]
        self.incerteza_padrao_combinada_completa = (
            _quantize(complete_combined) if complete_combined is not None else None
        )
        self.incerteza_padrao_combinada = _quantize(combined) if combined is not None else None
        self.percentual_variancia_desconsiderada = Decimal(
            str(selection["discarded_variance_percent"])
        ).quantize(Decimal("0.0001"))
        self.componentes_significativos = {
            name: str(_quantize(value)) for name, value in selection["included"].items()
        }
        self.componentes_desconsiderados = {
            name: str(_quantize(value)) for name, value in selection["discarded"].items()
        }
        self.incerteza_expandida = (
            _quantize(combined * (self.fator_k or Decimal("2"))) if combined is not None else None
        )
        if save and self.pk:
            type(self).objects.filter(pk=self.pk).update(
                u_resolucao_zero=self.u_resolucao_zero,
                u_resolucao_carga=self.u_resolucao_carga,
                u_repetibilidade=self.u_repetibilidade,
                u_excentricidade=self.u_excentricidade,
                u_certificados_pesos=self.u_certificados_pesos,
                u_deriva_pesos=self.u_deriva_pesos,
                incerteza_padrao_combinada_completa=self.incerteza_padrao_combinada_completa,
                incerteza_padrao_combinada=self.incerteza_padrao_combinada,
                percentual_variancia_desconsiderada=self.percentual_variancia_desconsiderada,
                componentes_significativos=self.componentes_significativos,
                componentes_desconsiderados=self.componentes_desconsiderados,
                incerteza_expandida=self.incerteza_expandida,
            )
        if self.ponto_id:
            self.ponto.recalculate(save=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.recalculate(save=True)
