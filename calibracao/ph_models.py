from decimal import Decimal

from django.db import models
from django.utils.text import slugify

from clientes.models import Cliente
from qualidade.models import Documento

from .models import (
    CalibracaoTurbidez,
    Instrumento,
    InstrumentoTecnico,
    Padrao,
    ResponsavelCertificado,
    _extrair_decimal_criterio,
    _fator_abrangencia_95,
    _obter_ou_criar_responsavel_padrao,
    _para_decimal,
    _quantize_decimal,
    _quantize_instance_decimal_fields,
)
from .services.ph_meter_calculation import (
    average as ph_average,
    calcular_incerteza as ph_calcular_incerteza,
    error as ph_error,
    slope_teorico_ph as ph_slope_teorico_ph,
    teorico_ph_from_mv as ph_teorico_ph_from_mv,
    stdev as ph_stdev,
)


def _format_decimal(value, digits=6):
    if value in (None, ""):
        return "-"
    try:
        return f"{Decimal(str(value)):.{digits}f}".replace(".", ",")
    except Exception:
        return str(value)


def _join_address(cliente):
    if not cliente:
        return ""
    parts = [
        getattr(cliente, "endereco", ""),
        getattr(cliente, "numero", ""),
        getattr(cliente, "bairro", ""),
        getattr(cliente, "cidade", ""),
        getattr(cliente, "uf", ""),
    ]
    return ", ".join([part for part in parts if part])


def _resultado_conforme(valor):
    return str(valor or "").strip().lower() in {
        "ok",
        "aprovado",
        "conforme",
        "aprovado com ressalva",
        "aprovado_com_ressalva",
    }


class CalibracaoPH(models.Model):
    RESULTADO_FINAL_CHOICES = (
        ("", "---------"),
        ("conforme", "Equipamento conforme, dentro do criterio de aceitacao informado"),
        ("nao_conforme", "Equipamento nao conforme, fora do criterio de aceitacao informado"),
    )

    TIPO_CALIBRACAO_CHOICES = (
        ("calibracao_eletrica", "Calibração elétrica"),
        ("calibracao_ph_simples", "Calibração pH simples"),
        ("calibracao_ph_completa", "Calibração pH completa"),
    )

    TIPO_INDICACAO_CHOICES = (
        ("analogico", "Analogico"),
        ("digital", "Digital"),
    )

    LOCAL_CALIBRACAO_CHOICES = CalibracaoTurbidez.LOCAL_CALIBRACAO_CHOICES

    PREFIXO_CERTIFICADO_MAP = {
        "calibracao_eletrica": "PH",
        "calibracao_ph_simples": "PH",
        "calibracao_ph_completa": "PH",
    }

    id = models.AutoField(primary_key=True)
    instrumento = models.ForeignKey(Instrumento, on_delete=models.PROTECT, related_name="calibracoes_ph")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="calibracoes_ph")
    ordem_servico = models.CharField(max_length=100, blank=True)
    numero_certificado = models.CharField(max_length=100, blank=True)
    data_calibracao = models.DateField(null=True, blank=True)
    data_emissao = models.DateField(null=True, blank=True)
    revisao = models.CharField(max_length=20, blank=True)

    contratante = models.CharField(max_length=255, blank=True)
    endereco_contratante = models.CharField(max_length=255, blank=True)
    endereco_cliente = models.CharField(max_length=255, blank=True)
    local_calibracao = models.CharField(max_length=30, choices=LOCAL_CALIBRACAO_CHOICES, default="ds_cientifica")

    tipo_calibracao = models.CharField(max_length=30, choices=TIPO_CALIBRACAO_CHOICES, default="eletrica_ph")
    tipo_indicacao = models.CharField(max_length=20, choices=TIPO_INDICACAO_CHOICES, blank=True)

    equipamento_calibrado = models.CharField(max_length=255, blank=True)
    numero_identificacao = models.CharField(max_length=100, blank=True)
    marca = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    numero_serie = models.CharField(max_length=100, blank=True)
    capacidade_total = models.CharField(max_length=120, blank=True)
    faixa_calibrada = models.CharField(max_length=120, blank=True)
    menor_resolucao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao_mv = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao_ph = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    identificacao_eletrodo = models.CharField(max_length=120, blank=True)
    resolucao_termometro = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    temperatura_referencia = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    slope_indicado = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    id_sensor_temperatura = models.CharField(max_length=120, blank=True)
    unidade_leitura = models.CharField(max_length=20, default="pH", blank=True)
    compensacao_temperatura = models.CharField(max_length=120, blank=True)
    tipo_sensor_temperatura = models.CharField(max_length=120, blank=True)
    procedimento_documento = models.ForeignKey(
        Documento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_ph",
    )
    procedimento_numero = models.CharField(max_length=100, blank=True)
    procedimento_revisao = models.CharField(max_length=20, blank=True)

    temperatura_inicial = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    temperatura_final = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    umidade_inicial = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    umidade_final = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    ajuste_efetuado = models.CharField(max_length=255, blank=True)

    responsavel_tecnico_ref = models.ForeignKey(
        ResponsavelCertificado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_ph_responsavel",
    )
    tecnico_executante_ref = models.ForeignKey(
        ResponsavelCertificado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_ph_executante",
    )
    tecnico_responsavel = models.CharField(max_length=150, blank=True)
    responsavel_conferencia = models.CharField(max_length=150, blank=True)
    funcao_signatario = models.CharField(max_length=150, blank=True)
    signatario_autorizado = models.CharField(max_length=150, blank=True)

    resultado_final_status = models.CharField(max_length=30, choices=RESULTADO_FINAL_CHOICES, blank=True)
    resultado_final = models.TextField(blank=True)
    observacoes_certificado = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Calibracao de pH"
        verbose_name_plural = "Calibracoes de pH"

    def _gerar_prefixo_certificado(self):
        return self.PREFIXO_CERTIFICADO_MAP.get(self.tipo_calibracao, "ph")

    def _codigo_equipamento_certificado(self):
        codigo = slugify(getattr(self.instrumento, "codigo", "") or "").replace("-", "")
        return codigo or "ph"

    def _nome_curto_cliente(self):
        nome = (
            getattr(self.cliente, "razao_social", "")
            or getattr(self.cliente, "nome_empresa", "")
            or str(self.cliente or "")
        )
        texto = slugify(nome).replace("-", "").strip()
        if not texto:
            return "cliente"
        return texto.split()[0]

    def _sequencia_certificado(self):
        base = (
            CalibracaoPH.objects.filter(instrumento=self.instrumento, cliente=self.cliente)
            .exclude(pk=self.pk)
            .count()
            + 1
        )
        return f"{base:02d}"

    def _gerar_numero_certificado(self):
        prefixo = "ph"
        cliente = self._nome_curto_cliente()
        os_base = slugify(self.ordem_servico or "").replace("-", "")
        if not os_base and self.data_calibracao:
            os_base = self.data_calibracao.strftime("%d%m%y")
        if not os_base:
            os_base = "0000"
        sequencia = self._sequencia_certificado()
        return f"{prefixo}-{os_base}-{cliente}-{sequencia}"

    @classmethod
    def _normalizar_local_calibracao(cls, valor):
        valor = (valor or "").strip().lower()
        if valor in dict(cls.LOCAL_CALIBRACAO_CHOICES):
            return valor
        if "in loco" in valor or "in_loco" in valor:
            return "in_loco"
        return "ds_cientifica"

    def _obter_documento_metodo_padrao(self):
        if self.procedimento_documento_id:
            return self.procedimento_documento
        metodo = getattr(self.instrumento, "metodo_calibracao", None)
        if metodo:
            return metodo
        return None

    @property
    def titulo_certificado(self):
        return "Certificado de Calibracao de Medidor de pH"

    def _pontos_tipo(self, *tipos):
        return self.pontos_calibracao.filter(tipo__in=tipos).order_by("ordem")

    def _ponto_principal(self):
        return (
            self._pontos_tipo("quimica_acida", "eletrica_ph", "eletrica_mv").first()
            or self.pontos_calibracao.order_by("ordem").first()
        )

    def calculo_inclinacao_real(self):
        ponto_acido = self._pontos_tipo("quimica_acida", "verificacao_acida", "mrc_acida", "mrc_verificacao_acida").first()
        ponto_basico = self._pontos_tipo("quimica_basica", "verificacao_basica", "mrc_basica", "mrc_verificacao_basica").first()
        if not ponto_acido or not ponto_basico:
            return None

        e1 = ponto_acido.media
        e2 = ponto_basico.media
        ph1 = ponto_acido.valor_padrao_ph
        ph2 = ponto_basico.valor_padrao_ph
        if None in (e1, e2, ph1, ph2):
            return None

        denominador = ph2 - ph1
        if denominador == 0:
            return None
        return (e1 - e2) / denominador

    def calculo_pH0(self):
        ponto_acido = self._pontos_tipo("quimica_acida", "verificacao_acida", "mrc_acida", "mrc_verificacao_acida").first()
        slope = self.calculo_inclinacao_real()
        if not ponto_acido or slope in (None, "") or slope == 0:
            return None
        if ponto_acido.valor_padrao_ph is None or ponto_acido.media is None:
            return None
        return ponto_acido.valor_padrao_ph + (ponto_acido.media / slope)

    def eficiencia_eletromotriz(self):
        slope = self.calculo_inclinacao_real()
        if slope in (None, ""):
            return None
        slope_teorico = self.slope_teorico()
        if slope_teorico in (None, "") or slope_teorico == 0:
            return None
        return slope / slope_teorico

    def slope_teorico(self):
        temperatura = self.temperatura_referencia
        if temperatura is None:
            temperatura = Decimal("25")
        return ph_slope_teorico_ph(temperatura)

    def slope_relativo(self):
        eficiencia = self.eficiencia_eletromotriz()
        if eficiencia in (None, ""):
            return None
        return eficiencia * Decimal("100")

    def calcular_status_final(self):
        pontos = list(self.pontos_calibracao.all())
        if not pontos:
            return ""

        resultados = [str(ponto.resultado or "").strip() for ponto in pontos if ponto.resultado]
        if not resultados:
            return ""

        if all(_resultado_conforme(resultado) for resultado in resultados):
            return "conforme"
        return "nao_conforme"

    def _texto_resultado_final_status(self):
        if self.resultado_final_status == "conforme":
            return "Equipamento conforme, dentro do criterio de aceitacao informado."
        if self.resultado_final_status == "nao_conforme":
            return "Equipamento nao conforme, fora do criterio de aceitacao informado."
        return ""

    def _gerar_resultado_final(self):
        slope = self.calculo_inclinacao_real()
        pH0 = self.calculo_pH0()
        eficiencia = self.eficiencia_eletromotriz()
        slope_teorico = self.slope_teorico()
        slope_relativo = self.slope_relativo()
        partes = []
        if self.slope_indicado is not None:
            partes.append(f"slope indicado = {_format_decimal(self.slope_indicado, 4)}")
        if slope_teorico is not None:
            partes.append(f"slope teorico = {_format_decimal(slope_teorico, 4)}")
        if slope is not None:
            partes.append(f"slope real = {_format_decimal(slope, 4)}")
        if pH0 is not None:
            partes.append(f"pH0 = {_format_decimal(pH0, 4)}")
        if slope_relativo is not None:
            partes.append(f"slope relativo = {_format_decimal(slope_relativo, 2)}%")
        texto_status = self._texto_resultado_final_status()
        if texto_status:
            partes.append(texto_status)
        return "; ".join(partes)

    @property
    def resultado_final_resolvido(self):
        return self.resultado_final or self._texto_resultado_final_status()

    def save(self, *args, **kwargs):
        if self.cliente_id and not self.contratante:
            self.contratante = self.cliente.razao_social or str(self.cliente)
        if self.cliente_id:
            endereco = _join_address(self.cliente)
            if endereco and not self.endereco_contratante:
                self.endereco_contratante = endereco
            if endereco and not self.endereco_cliente:
                self.endereco_cliente = endereco

        self.local_calibracao = self._normalizar_local_calibracao(self.local_calibracao)
        if not self.data_emissao and self.data_calibracao:
            self.data_emissao = self.data_calibracao
        if self.procedimento_documento_id:
            self.procedimento_numero = self.procedimento_documento.codigo or self.procedimento_numero
            self.procedimento_revisao = self.procedimento_documento.revisao or self.procedimento_revisao

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

        status_final = self.calcular_status_final()
        resultado_final = self._gerar_resultado_final()
        if (
            status_final != self.resultado_final_status
            or resultado_final != self.resultado_final
        ):
            CalibracaoPH.objects.filter(pk=self.pk).update(
                resultado_final_status=status_final,
                resultado_final=resultado_final,
            )

    def __str__(self):
        return f"{self.numero_certificado} - {self.instrumento}"


class CalibracaoPHPadraoUtilizado(models.Model):
    TIPO_CHOICES = (
        ("gerador_tensao", "Gerador de tensao"),
        ("mrc_acida", "MRC faixa acida"),
        ("mrc_neutra", "MRC neutro"),
        ("mrc_basica", "MRC faixa basica"),
        ("mrc_verificacao_acida", "MRC de verificacao acida"),
        ("mrc_verificacao_basica", "MRC de verificacao basica"),
        ("termometro", "Termometro ambiente"),
        ("termohigrometro", "Termohigrometro ambiente"),
        ("outro", "Outro"),
    )

    calibracao = models.ForeignKey(
        CalibracaoPH,
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
        related_name="usos_ph",
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
        verbose_name = "Padrao utilizado - pH"
        verbose_name_plural = "Padroes utilizados - pH"
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


class CalibracaoPHPonto(models.Model):
    TIPO_CHOICES = (
        ("eletrica_mv", "Eletrica em mV"),
        ("eletrica_ph", "Eletrica em pH"),
        ("quimica_acida", "Quimica acida"),
        ("quimica_neutra", "Quimica neutra"),
        ("quimica_basica", "Quimica basica"),
        ("verificacao_acida", "Verificacao acida"),
        ("verificacao_basica", "Verificacao basica"),
        ("mrc_acida", "MRC acida"),
        ("mrc_neutra", "MRC neutra"),
        ("mrc_basica", "MRC basica"),
        ("mrc_verificacao_acida", "MRC verificacao acida"),
        ("mrc_verificacao_basica", "MRC verificacao basica"),
    )

    calibracao = models.ForeignKey(
        CalibracaoPH,
        on_delete=models.CASCADE,
        related_name="pontos_calibracao",
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    ordem = models.PositiveSmallIntegerField(default=1)
    valor_padrao_mv = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    valor_padrao_ph = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura_1 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura_2 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    leitura_3 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    media = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    desvio_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    erro = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    ema = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    criterio = models.CharField(max_length=120, blank=True)
    resultado = models.CharField(max_length=50, blank=True)
    observacoes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Ponto de calibracao - pH"
        verbose_name_plural = "Pontos de calibracao - pH"
        ordering = ("ordem",)

    def _referencia(self):
        if self.tipo in ("eletrica_mv", "eletrica_ph"):
            return self.valor_padrao_mv
        if self.valor_padrao_ph is not None:
            return self.valor_padrao_ph
        return self.valor_padrao_mv

    def save(self, *args, **kwargs):
        leituras = [valor for valor in (self.leitura_1, self.leitura_2, self.leitura_3) if valor is not None]

        if self.tipo in ("eletrica_mv", "eletrica_ph") and self.valor_padrao_mv is not None:
            self.valor_padrao_ph = None
        elif self.valor_padrao_ph is None and self.valor_padrao_mv is not None:
            temperatura = self.calibracao.temperatura_referencia
            if temperatura is None:
                temperatura = Decimal("25")
            self.valor_padrao_ph = ph_teorico_ph_from_mv(self.valor_padrao_mv, temperatura)

        if leituras:
            media = ph_average(leituras)
            if media is not None:
                self.media = _quantize_decimal(media)
            self.desvio_padrao = ph_stdev(leituras)
            if self.desvio_padrao is not None:
                self.desvio_padrao = _quantize_decimal(self.desvio_padrao)

        referencia = self._referencia()
        if self.media is not None and referencia is not None:
            self.erro = ph_error(self.media, referencia)
            if self.erro is not None:
                self.erro = _quantize_decimal(self.erro)

        tolerancia = _extrair_decimal_criterio(self.criterio)
        if tolerancia is not None and self.erro is not None:
            self.resultado = "OK" if abs(self.erro) <= tolerancia else "NAO OK"
        elif self.erro is not None:
            self.resultado = ""

        incerteza = (
            self.calibracao.pontos_incerteza.filter(ordem=self.ordem)
            .values_list("incerteza_expandida", flat=True)
            .first()
        )
        if self.erro is not None and incerteza is not None:
            self.ema = _quantize_decimal(abs(self.erro) + incerteza)

        _quantize_instance_decimal_fields(self)
        super().save(*args, **kwargs)

        status_final = self.calibracao.calcular_status_final()
        resultado_final = self.calibracao._gerar_resultado_final()
        if (
            status_final != self.calibracao.resultado_final_status
            or resultado_final != self.calibracao.resultado_final
        ):
            CalibracaoPH.objects.filter(pk=self.calibracao_id).update(
                resultado_final_status=status_final,
                resultado_final=resultado_final,
            )

    def __str__(self):
        return f"Calibracao pH {self.ordem}"


class CalibracaoPHIncertezaPonto(models.Model):
    calibracao = models.ForeignKey(
        CalibracaoPH,
        on_delete=models.CASCADE,
        related_name="pontos_incerteza",
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    repetibilidade = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao_instrumento = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_curva = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_temperatura = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_constante_faraday = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_constante_gas = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_phx = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    fator_k = models.DecimalField(max_digits=8, decimal_places=3, default=2)
    graus_liberdade = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    incerteza_padrao_combinada = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_expandida = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    class Meta:
        verbose_name = "Ponto de incerteza - pH"
        verbose_name_plural = "Pontos de incerteza - pH"
        ordering = ("ordem",)

    def _obter_padrao_referencia(self):
        padroes = self.calibracao.padroes_utilizados
        return (
            padroes.filter(tipo="mrc_acida", ordem=self.ordem).first()
            or padroes.filter(tipo="mrc_verificacao_acida", ordem=self.ordem).first()
            or padroes.filter(tipo="mrc_basica", ordem=self.ordem).first()
            or padroes.filter(tipo="mrc_verificacao_basica", ordem=self.ordem).first()
            or padroes.filter(tipo="mrc_neutra").order_by("ordem").first()
        )

    def save(self, *args, **kwargs):
        ponto_calibracao = self.calibracao.pontos_calibracao.filter(ordem=self.ordem).first()
        padrao_referencia = self._obter_padrao_referencia()

        if self.repetibilidade is None and ponto_calibracao and ponto_calibracao.desvio_padrao is not None:
            self.repetibilidade = ponto_calibracao.desvio_padrao
        if self.resolucao_instrumento is None:
            self.resolucao_instrumento = self.calibracao.resolucao_ph or self.calibracao.resolucao_mv or self.calibracao.menor_resolucao
        if padrao_referencia:
            if self.incerteza_padrao is None:
                self.incerteza_padrao = padrao_referencia.incerteza
            if self.resolucao_padrao is None:
                self.resolucao_padrao = padrao_referencia.resolucao

        componentes = [
            valor
            for valor in (
                self.repetibilidade,
                self.resolucao_instrumento,
                self.resolucao_padrao,
                self.incerteza_padrao,
                self.incerteza_curva,
                self.incerteza_temperatura,
                self.incerteza_constante_faraday,
                self.incerteza_constante_gas,
                self.incerteza_phx,
            )
            if valor is not None
        ]

        if componentes:
            resultado = ph_calcular_incerteza(componentes, graus_liberdade=self.graus_liberdade, fator_k=self.fator_k)
            self.incerteza_padrao_combinada = resultado["incerteza_padrao_combinada"]
            self.incerteza_expandida = resultado["incerteza_expandida"]
            self.fator_k = resultado["fator_k"] or self.fator_k
            self.graus_liberdade = resultado["graus_liberdade"]
        else:
            self.incerteza_padrao_combinada = None
            self.incerteza_expandida = None
            if self.fator_k in (None, ""):
                self.fator_k = Decimal("2.000")
            if self.graus_liberdade in (None, ""):
                self.graus_liberdade = Decimal("999999.00")

        _quantize_instance_decimal_fields(self)
        super().save(*args, **kwargs)

        if ponto_calibracao and ponto_calibracao.erro is not None and self.incerteza_expandida is not None:
            ponto_calibracao.ema = _quantize_decimal(abs(ponto_calibracao.erro) + self.incerteza_expandida)
            ponto_calibracao.save(update_fields=["ema"])

    def __str__(self):
        return f"Incerteza pH {self.ordem}"
