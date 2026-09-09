import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from clientes.models import Cliente
from qualidade.models import Documento

from .models import (
    Instrumento,
    Padrao,
    ResponsavelCertificado,
    _formatar_decimal_por_resolucao,
    salvar_com_numero_certificado,
)
from .services.sphyg_calculation import (
    average,
    conformity_result,
    correction_from_error,
    hysteresis,
    leakage_rate,
    measurement_error,
    root_sum_squares,
    sample_standard_deviation,
    standard_uncertainty_from_expanded,
    standard_uncertainty_from_rectangular_limit,
    standard_uncertainty_from_repeatability,
    standard_uncertainty_from_resolution,
)


Q6 = Decimal("0.000001")


def _q(value):
    return value.quantize(Q6) if value is not None else None


def _normalizar_unidade(unidade):
    return (unidade or "").strip().lower().replace(" ", "")


class CalibracaoEsfigmomanometro(models.Model):
    TECNOLOGIA_CHOICES = (
        ("aneroide", "Analógico aneroide"),
        ("digital_automatico", "Digital automático"),
        ("digital_nao_automatico", "Digital não automático"),
    )
    APLICACAO_CHOICES = (
        ("braco", "Braço"),
        ("antebraco", "Antebraço"),
        ("punho", "Punho"),
        ("coxa", "Coxa"),
    )
    TIPO_SERVICO_CHOICES = (
        ("calibracao", "Calibração"),
        ("calibracao_apos_manutencao", "Calibração após manutenção/reparo"),
    )
    STATUS_CHOICES = (
        ("rascunho", "Rascunho"),
        ("concluida", "Concluída"),
        ("emitida", "Emitida"),
        ("cancelada", "Cancelada"),
    )
    LOCAL_CHOICES = (
        ("laboratorio_pressao_ds", "Laboratório de Pressão DS Científica"),
        ("in_loco", "In loco"),
    )
    UNIDADE_CHOICES = (("mmHg", "mmHg"), ("kPa", "kPa"))
    CONTEXTO_CRITERIO_CHOICES = (
        ("sem_criterio", "Sem critério normativo pré-selecionado"),
        ("inicial_apos_reparo", "Referência legal inicial/após reparo: ±3 mmHg ou ±0,4 kPa"),
        ("periodica", "Referência legal periódica: ±4 mmHg ou ±0,5 kPa"),
        ("personalizado", "Critério personalizado do cliente/fabricante"),
    )
    REGRA_DECISAO_CHOICES = (
        ("sem_declaracao", "Sem declaração de conformidade"),
        ("aceitacao_simples", "Aceitação simples: |erro| ≤ tolerância"),
        ("banda_guarda", "Banda de guarda: |erro| + U ≤ tolerância"),
    )
    RESULTADO_CHOICES = (
        ("", "---------"),
        ("conforme", "Conforme"),
        ("nao_conforme", "Não conforme"),
        ("nao_declarado", "Não declarado"),
    )
    ENSAIO_STATUS_CHOICES = (
        ("", "Não realizado"),
        ("aprovado", "Aprovado"),
        ("reprovado", "Reprovado"),
        ("nao_aplicavel", "Não aplicável"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrumento = models.ForeignKey(
        Instrumento, on_delete=models.PROTECT, related_name="calibracoes_esfigmomanometro"
    )
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name="calibracoes_esfigmomanometro"
    )
    tecnologia = models.CharField(max_length=30, choices=TECNOLOGIA_CHOICES)
    aplicacao = models.CharField(max_length=20, choices=APLICACAO_CHOICES, default="braco")
    tipo_servico = models.CharField(max_length=35, choices=TIPO_SERVICO_CHOICES, default="calibracao")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="rascunho")
    numero_certificado = models.CharField(max_length=100, unique=True, blank=True)
    ordem_servico = models.CharField(max_length=100, blank=True)
    data_calibracao = models.DateField()
    data_emissao = models.DateField(default=date.today)
    proxima_calibracao = models.DateField(null=True, blank=True)
    revisao = models.CharField(max_length=20, default="00", blank=True)
    local_calibracao = models.CharField(max_length=30, choices=LOCAL_CHOICES, default="laboratorio_pressao_ds")

    contratante = models.CharField(max_length=255, blank=True)
    endereco_cliente = models.CharField(max_length=255, blank=True)
    tag = models.CharField(max_length=100, blank=True)
    fabricante = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    numero_serie = models.CharField(max_length=100, blank=True)
    ano_fabricacao = models.PositiveSmallIntegerField(null=True, blank=True)
    faixa_medicao = models.CharField(max_length=100, blank=True, default="0 a 300 mmHg")
    resolucao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    unidade = models.CharField(max_length=10, choices=UNIDADE_CHOICES, default="mmHg")

    identificacao_brachadeira = models.CharField("Identificação da braçadeira", max_length=100, blank=True)
    circunferencia_minima_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    circunferencia_maxima_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    marcacao_arteria_conforme = models.BooleanField(default=False)
    integridade_brachadeira_manguito = models.CharField(max_length=255, blank=True)

    portaria_aprovacao_modelo = models.CharField(max_length=100, blank=True)
    marca_aprovacao_modelo = models.CharField(max_length=100, blank=True)
    identificacao_marca_verificacao = models.CharField(max_length=100, blank=True)
    data_ultima_verificacao_legal = models.DateField(null=True, blank=True)
    data_proxima_verificacao_legal = models.DateField(null=True, blank=True)

    modo_manometro = models.CharField(
        max_length=255, blank=True,
        help_text="Para digitais, registre o modo de manômetro e como o circuito pneumático foi isolado.",
    )
    adaptador_conexao = models.CharField(max_length=150, blank=True)
    fonte_alimentacao = models.CharField(max_length=100, blank=True)

    procedimento_documento = models.ForeignKey(
        Documento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="calibracoes_esfigmomanometro",
    )
    procedimento_numero = models.CharField(max_length=100, blank=True)
    procedimento_revisao = models.CharField(max_length=50, blank=True)
    referencias = models.TextField(blank=True, default="Portaria Inmetro nº 341/2021")

    temperatura_inicial = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    temperatura_final = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    umidade_inicial = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    umidade_final = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    justificativa_condicoes = models.CharField(max_length=255, blank=True)

    contexto_criterio = models.CharField(
        max_length=30, choices=CONTEXTO_CRITERIO_CHOICES, default="sem_criterio"
    )
    tolerancia_personalizada = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    criterio_origem = models.CharField(max_length=50, blank=True)
    criterio_referencia = models.CharField(max_length=255, blank=True)
    regra_decisao = models.CharField(max_length=30, choices=REGRA_DECISAO_CHOICES, default="sem_declaracao")

    exame_geral = models.CharField(max_length=20, choices=ENSAIO_STATUS_CHOICES, blank=True)
    ajuste_zero = models.CharField(max_length=20, choices=ENSAIO_STATUS_CHOICES, blank=True)
    interrupcao_imediata = models.CharField(max_length=20, choices=ENSAIO_STATUS_CHOICES, blank=True)
    ensaio_vazamento_aplicavel = models.BooleanField(default=True)
    justificativa_vazamento_nao_aplicavel = models.CharField(max_length=255, blank=True)
    observacoes_exame = models.TextField(blank=True)

    resultado_final = models.CharField(max_length=20, choices=RESULTADO_CHOICES, blank=True)
    observacoes_certificado = models.TextField(blank=True)
    responsavel_tecnico = models.ForeignKey(
        ResponsavelCertificado, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="calibracoes_esfig_como_responsavel",
    )
    tecnico_executante = models.ForeignKey(
        ResponsavelCertificado, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="calibracoes_esfig_como_executante",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Calibração de esfigmomanômetro"
        verbose_name_plural = "Calibrações de esfigmomanômetros"
        ordering = ("-data_calibracao", "-created_at")

    def __str__(self):
        return f"{self.numero_certificado or 'Em elaboração'} - {self.instrumento}"

    @property
    def titulo_certificado(self):
        return f"Certificado de calibração de esfigmomanômetro - {self.get_tecnologia_display()}"

    @property
    def tolerancia_resolvida(self):
        if self.contexto_criterio == "inicial_apos_reparo":
            return Decimal("3") if self.unidade == "mmHg" else Decimal("0.4")
        if self.contexto_criterio == "periodica":
            return Decimal("4") if self.unidade == "mmHg" else Decimal("0.5")
        if self.contexto_criterio == "personalizado":
            return self.tolerancia_personalizada
        return None

    def formatar_por_resolucao(self, valor):
        """Formata a apresentação sem reduzir a precisão interna do cálculo."""
        return _formatar_decimal_por_resolucao(valor, self.resolucao, default=0)

    @property
    def condicoes_na_referencia(self):
        temperatures = (self.temperatura_inicial, self.temperatura_final)
        humidities = (self.umidade_inicial, self.umidade_final)
        if None in temperatures or None in humidities:
            return False
        return all(Decimal("15") <= value <= Decimal("25") for value in temperatures) and all(
            Decimal("20") <= value <= Decimal("85") for value in humidities
        )

    def _gerar_numero_certificado(self):
        year = (self.data_calibracao or date.today()).year
        prefix = f"ESF-{year}"
        existing = type(self).objects.exclude(pk=self.pk).filter(
            numero_certificado__startswith=f"{prefix}-"
        ).values_list("numero_certificado", flat=True)
        used = set()
        for number in existing:
            try:
                used.add(int(str(number).rsplit("-", 1)[-1]))
            except (TypeError, ValueError):
                continue
        sequence = 1
        while sequence in used:
            sequence += 1
        return f"{prefix}-{sequence:04d}"

    def _preencher_snapshot(self):
        if self.instrumento_id:
            self.cliente = self.instrumento.cliente
            self.tag = self.tag or self.instrumento.tag or self.instrumento.codigo
            self.fabricante = self.fabricante or self.instrumento.marca or ""
            self.modelo = self.modelo or self.instrumento.modelo or ""
            self.numero_serie = self.numero_serie or self.instrumento.numero_serie or ""
        if self.cliente_id:
            self.contratante = self.contratante or self.cliente.razao_social
            if not self.endereco_cliente:
                parts = [
                    getattr(self.cliente, "endereco", ""), getattr(self.cliente, "numero", ""),
                    getattr(self.cliente, "bairro", ""), getattr(self.cliente, "cidade", ""),
                    getattr(self.cliente, "uf", ""),
                ]
                self.endereco_cliente = ", ".join(str(part) for part in parts if part)
        if self.procedimento_documento_id:
            self.procedimento_numero = self.procedimento_documento.codigo or ""
            self.procedimento_revisao = self.procedimento_documento.revisao or ""

    def pendencias_emissao(self):
        pending = []
        required = (
            (self.numero_certificado, "Número do certificado"),
            (self.contratante, "Contratante"),
            (self.endereco_cliente, "Endereço do cliente"),
            (self.procedimento_numero, "Método/procedimento"),
            (self.responsavel_tecnico_id, "Responsável técnico"),
            (self.tecnico_executante_id, "Técnico executante"),
            (self.exame_geral, "Exame geral"),
        )
        pending.extend(label for value, label in required if not value)
        if not self.condicoes_na_referencia and not self.justificativa_condicoes:
            pending.append("Condições ambientais fora/incompletas sem justificativa técnica")
        if self.tecnologia.startswith("digital") and not self.modo_manometro:
            pending.append("Modo de manômetro/conexão de ensaio do digital")
        if self.tecnologia == "digital_automatico" and not self.interrupcao_imediata:
            pending.append("Ensaio de interrupção imediata")
        if self.tecnologia == "aneroide" and self.ajuste_zero == "":
            pending.append("Verificação de retorno/ajuste do zero")
        if self.ensaio_vazamento_aplicavel:
            if not self.ensaios_vazamento.exists():
                pending.append("Ensaio de escapamento de ar")
        elif not self.justificativa_vazamento_nao_aplicavel:
            pending.append("Justificativa para não aplicar ensaio de escapamento de ar")
        if not self.padroes_utilizados.exists():
            pending.append("Padrão utilizado")
        else:
            for standard in self.padroes_utilizados.all():
                if standard.situacao_na_data != "valido":
                    pending.append(
                        f"Padrão {standard.codigo or standard.padrao}: {standard.get_situacao_na_data_display()}"
                    )
                if _normalizar_unidade(standard.unidade) != _normalizar_unidade(self.unidade):
                    pending.append(f"Unidade do padrão {standard.codigo or standard.padrao} divergente")
        points = list(self.pontos.all())
        if not points:
            pending.append("Pontos de pressão")
        elif any(point.media_decrescente is None for point in points):
            pending.append("Ciclo decrescente incompleto")
        if points:
            uncertainties = {item.ordem: item for item in self.pontos_incerteza.all()}
            for point in points:
                uncertainty = uncertainties.get(point.ordem)
                if not uncertainty or uncertainty.incerteza_expandida is None:
                    pending.append(f"Incerteza do ponto {point.ordem}")
                    continue
                if uncertainty.u_certificado_padrao is None:
                    pending.append(f"Incerteza de calibração do padrão no ponto {point.ordem}")
        if self.regra_decisao != "sem_declaracao":
            if self.tolerancia_resolvida is None:
                pending.append("Tolerância para declaração de conformidade")
            if not self.criterio_origem or not self.criterio_referencia:
                pending.append("Origem e referência do critério de aceitação")
        return pending

    def recalcular_resultado(self, save=True):
        if self.regra_decisao == "sem_declaracao":
            result = "nao_declarado" if self.pontos.exists() else ""
        else:
            results = list(self.pontos.exclude(resultado="").values_list("resultado", flat=True))
            results += list(self.ensaios_vazamento.exclude(resultado="").values_list("resultado", flat=True))
            functional = [self.exame_geral, self.ajuste_zero]
            if self.tecnologia == "digital_automatico":
                functional.append(self.interrupcao_imediata)
            if "reprovado" in results or "reprovado" in functional:
                result = "nao_conforme"
            elif results and all(item == "aprovado" for item in results) and all(
                item in ("", "aprovado", "nao_aplicavel") for item in functional
            ):
                result = "conforme"
            else:
                result = "nao_declarado"
        self.resultado_final = result
        if save and self.pk:
            type(self).objects.filter(pk=self.pk).update(resultado_final=result)

    def clean(self):
        super().clean()
        if self.instrumento_id and self.cliente_id and self.instrumento.cliente_id != self.cliente_id:
            raise ValidationError({"cliente": "O cliente deve ser o proprietário do instrumento."})
        if self.status == "emitida" and self.pk:
            pending = self.pendencias_emissao()
            if pending:
                raise ValidationError({"status": "Emissão bloqueada: " + "; ".join(pending)})

    def save(self, *args, **kwargs):
        self._preencher_snapshot()
        salvar_com_numero_certificado(self, super().save, args, kwargs)


class EsfigmomanometroPadraoUtilizado(models.Model):
    SITUACAO_CHOICES = (
        ("valido", "Válido na data"),
        ("vencido", "Vencido na data"),
        ("suspenso", "Suspenso"),
        ("incompleto", "Rastreabilidade incompleta"),
    )
    calibracao = models.ForeignKey(
        CalibracaoEsfigmomanometro, on_delete=models.CASCADE, related_name="padroes_utilizados"
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    padrao = models.ForeignKey(Padrao, on_delete=models.PROTECT, related_name="usos_esfigmomanometro")
    codigo = models.CharField(max_length=50, blank=True)
    descricao = models.CharField(max_length=255, blank=True)
    numero_certificado = models.CharField(max_length=100, blank=True)
    laboratorio_emitente = models.CharField(max_length=150, blank=True)
    data_calibracao = models.DateField(null=True, blank=True)
    validade = models.DateField(null=True, blank=True)
    resolucao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_expandida = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    fator_k = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    graus_liberdade = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unidade = models.CharField(max_length=30, blank=True)
    situacao_na_data = models.CharField(max_length=20, choices=SITUACAO_CHOICES, default="incompleto")

    class Meta:
        verbose_name = "Padrão utilizado - esfigmomanômetro"
        verbose_name_plural = "Padrões utilizados - esfigmomanômetros"
        ordering = ("ordem",)
        constraints = [
            models.UniqueConstraint(fields=("calibracao", "ordem"), name="uniq_esfig_padrao_ordem")
        ]

    def __str__(self):
        return f"{self.codigo or self.padrao} - {self.numero_certificado or 'sem certificado'}"

    def _resolver_situacao(self):
        if self.padrao.status == "suspenso":
            return "suspenso"
        if not all((self.numero_certificado, self.laboratorio_emitente, self.data_calibracao, self.validade)):
            return "incompleto"
        if self.data_calibracao > self.calibracao.data_calibracao:
            return "incompleto"
        if self.calibracao.data_calibracao > self.validade:
            return "vencido"
        return "valido"

    def save(self, *args, **kwargs):
        if self.padrao_id:
            self.codigo = self.codigo or self.padrao.codigo
            self.descricao = self.descricao or self.padrao.descricao
            self.numero_certificado = self.numero_certificado or self.padrao.numero_certificado
            self.laboratorio_emitente = self.laboratorio_emitente or self.padrao.laboratorio_emitente
            self.data_calibracao = self.data_calibracao or self.padrao.data_calibracao
            self.validade = self.validade or self.padrao.vencimento
            self.resolucao = self.resolucao if self.resolucao is not None else self.padrao.resolucao
            self.incerteza_expandida = (
                self.incerteza_expandida if self.incerteza_expandida is not None else self.padrao.incerteza
            )
            self.fator_k = self.fator_k if self.fator_k is not None else self.padrao.fator_k
            self.graus_liberdade = (
                self.graus_liberdade if self.graus_liberdade is not None else self.padrao.graus_liberdade
            )
            self.unidade = self.unidade or self.padrao.unidade
        self.situacao_na_data = self._resolver_situacao()
        super().save(*args, **kwargs)


class EsfigmomanometroPonto(models.Model):
    RESULTADO_CHOICES = (
        ("", "---------"), ("aprovado", "Aprovado"),
        ("reprovado", "Reprovado"), ("nao_declarado", "Não declarado"),
    )
    calibracao = models.ForeignKey(
        CalibracaoEsfigmomanometro, on_delete=models.CASCADE, related_name="pontos"
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    pressao_referencia = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    crescente_1 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    crescente_2 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    crescente_3 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    decrescente_1 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    decrescente_2 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    decrescente_3 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    media_crescente = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    media_decrescente = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    erro_crescente = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    erro_decrescente = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    correcao_crescente = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    correcao_decrescente = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    histerese = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    repetitividade = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    tolerancia = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES, blank=True, editable=False)
    observacoes = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Ponto de pressão do esfigmomanômetro"
        verbose_name_plural = "Pontos de pressão do esfigmomanômetro"
        ordering = ("ordem",)
        constraints = [
            models.UniqueConstraint(fields=("calibracao", "ordem"), name="uniq_esfig_ponto_ordem")
        ]

    def __str__(self):
        return f"Ponto {self.ordem} - {self.pressao_referencia or 'sem referência'}"

    @property
    def incerteza_expandida(self):
        item = self.calibracao.pontos_incerteza.filter(ordem=self.ordem).first()
        return item.incerteza_expandida if item else None

    def recalculate(self, save=False):
        increasing = [self.crescente_1, self.crescente_2, self.crescente_3]
        decreasing = [self.decrescente_1, self.decrescente_2, self.decrescente_3]
        self.media_crescente = _q(average(increasing))
        self.media_decrescente = _q(average(decreasing))
        self.erro_crescente = _q(measurement_error(self.media_crescente, self.pressao_referencia))
        self.erro_decrescente = _q(measurement_error(self.media_decrescente, self.pressao_referencia))
        self.correcao_crescente = _q(correction_from_error(self.erro_crescente))
        self.correcao_decrescente = _q(correction_from_error(self.erro_decrescente))
        self.histerese = _q(hysteresis(self.media_crescente, self.media_decrescente))
        deviations = [sample_standard_deviation(increasing), sample_standard_deviation(decreasing)]
        deviations = [value for value in deviations if value is not None]
        self.repetitividade = _q(max(deviations)) if deviations else None
        self.tolerancia = self.calibracao.tolerancia_resolvida
        self.resultado = conformity_result(
            (self.erro_crescente, self.erro_decrescente), self.tolerancia,
            self.incerteza_expandida, self.calibracao.regra_decisao,
        )
        if save and self.pk:
            type(self).objects.filter(pk=self.pk).update(
                media_crescente=self.media_crescente, media_decrescente=self.media_decrescente,
                erro_crescente=self.erro_crescente, erro_decrescente=self.erro_decrescente,
                correcao_crescente=self.correcao_crescente,
                correcao_decrescente=self.correcao_decrescente,
                histerese=self.histerese, repetitividade=self.repetitividade,
                tolerancia=self.tolerancia, resultado=self.resultado,
            )
            self.calibracao.recalcular_resultado(save=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.recalculate(save=True)


class EsfigmomanometroIncertezaPonto(models.Model):
    calibracao = models.ForeignKey(
        CalibracaoEsfigmomanometro, on_delete=models.CASCADE, related_name="pontos_incerteza"
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    resolucao_instrumento = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    resolucao_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incerteza_certificado_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    fator_k_certificado_padrao = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    limite_deriva_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    incluir_resolucao_padrao = models.BooleanField(
        default=False,
        help_text=(
            "Inclua somente se a quantização da indicação do padrão não estiver adequadamente "
            "representada em outra componente. Evite dupla contagem com o certificado."
        ),
    )
    incluir_deriva_padrao = models.BooleanField(
        default=False,
        help_text="Inclua somente com limite de deriva tecnicamente sustentado por histórico ou especificação.",
    )
    u_repetitividade = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    u_resolucao_instrumento = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    u_resolucao_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    u_certificado_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    u_deriva_padrao = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    u_outros = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    outros_descricao = models.CharField(max_length=255, blank=True)
    incerteza_padrao_combinada = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    fator_k = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal("2"))
    graus_liberdade = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    incerteza_expandida = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Incerteza do ponto - esfigmomanômetro"
        verbose_name_plural = "Incertezas dos pontos - esfigmomanômetro"
        ordering = ("ordem",)
        constraints = [
            models.UniqueConstraint(fields=("calibracao", "ordem"), name="uniq_esfig_incerteza_ordem")
        ]

    def __str__(self):
        return f"Incerteza - ponto {self.ordem}"

    @property
    def componentes_incluidos(self):
        componentes = ["repetitividade", "resolução do instrumento", "calibração do padrão"]
        if self.incluir_resolucao_padrao:
            componentes.append("resolução adicional do padrão")
        if self.incluir_deriva_padrao:
            componentes.append("deriva do padrão")
        if self.u_outros is not None:
            componentes.append(self.outros_descricao or "outra componente")
        return ", ".join(componentes)

    def clean(self):
        super().clean()
        errors = {}
        if self.incluir_deriva_padrao and self.limite_deriva_padrao is None:
            errors["limite_deriva_padrao"] = "Informe o limite de deriva que fundamenta esta componente."
        if self.u_outros is not None and not self.outros_descricao.strip():
            errors["outros_descricao"] = "Identifique e justifique a outra componente de incerteza."
        if errors:
            raise ValidationError(errors)

    def recalculate(self, save=False):
        point = self.calibracao.pontos.filter(ordem=self.ordem).first()
        standard = self.calibracao.padroes_utilizados.order_by("ordem").first()
        if standard:
            self.resolucao_padrao = self.resolucao_padrao if self.resolucao_padrao is not None else standard.resolucao
            self.incerteza_certificado_padrao = (
                self.incerteza_certificado_padrao
                if self.incerteza_certificado_padrao is not None else standard.incerteza_expandida
            )
            self.fator_k_certificado_padrao = (
                self.fator_k_certificado_padrao
                if self.fator_k_certificado_padrao is not None else standard.fator_k
            )
        self.resolucao_instrumento = (
            self.resolucao_instrumento
            if self.resolucao_instrumento is not None else self.calibracao.resolucao
        )
        repetitions = 3 if point and point.repetitividade is not None else 0
        self.u_repetitividade = _q(standard_uncertainty_from_repeatability(
            getattr(point, "repetitividade", None), repetitions
        ))
        self.u_resolucao_instrumento = _q(standard_uncertainty_from_resolution(self.resolucao_instrumento))
        self.u_resolucao_padrao = (
            _q(standard_uncertainty_from_resolution(self.resolucao_padrao))
            if self.incluir_resolucao_padrao else None
        )
        self.u_certificado_padrao = _q(standard_uncertainty_from_expanded(
            self.incerteza_certificado_padrao, self.fator_k_certificado_padrao
        ))
        self.u_deriva_padrao = (
            _q(standard_uncertainty_from_rectangular_limit(self.limite_deriva_padrao))
            if self.incluir_deriva_padrao else None
        )
        self.incerteza_padrao_combinada = _q(root_sum_squares((
            self.u_repetitividade, self.u_resolucao_instrumento, self.u_resolucao_padrao,
            self.u_certificado_padrao, self.u_deriva_padrao, self.u_outros,
        )))
        self.incerteza_expandida = (
            _q(self.incerteza_padrao_combinada * (self.fator_k or Decimal("2")))
            if self.incerteza_padrao_combinada is not None else None
        )
        if save and self.pk:
            type(self).objects.filter(pk=self.pk).update(
                resolucao_instrumento=self.resolucao_instrumento,
                resolucao_padrao=self.resolucao_padrao,
                incerteza_certificado_padrao=self.incerteza_certificado_padrao,
                fator_k_certificado_padrao=self.fator_k_certificado_padrao,
                u_repetitividade=self.u_repetitividade,
                u_resolucao_instrumento=self.u_resolucao_instrumento,
                u_resolucao_padrao=self.u_resolucao_padrao,
                u_certificado_padrao=self.u_certificado_padrao,
                u_deriva_padrao=self.u_deriva_padrao,
                incerteza_padrao_combinada=self.incerteza_padrao_combinada,
                incerteza_expandida=self.incerteza_expandida,
            )
            if point:
                point.recalculate(save=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.recalculate(save=True)


class EsfigmomanometroEnsaioVazamento(models.Model):
    RESULTADO_CHOICES = EsfigmomanometroPonto.RESULTADO_CHOICES
    calibracao = models.ForeignKey(
        CalibracaoEsfigmomanometro, on_delete=models.CASCADE, related_name="ensaios_vazamento"
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    pressao_inicial = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    pressao_final = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    duracao_minutos = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal("5"))
    taxa_vazamento = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    limite_personalizado = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    limite_resolvido = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, editable=False)
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES, blank=True, editable=False)
    observacoes = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Ensaio de escapamento de ar"
        verbose_name_plural = "Ensaios de escapamento de ar"
        ordering = ("ordem",)
        constraints = [
            models.UniqueConstraint(fields=("calibracao", "ordem"), name="uniq_esfig_vazamento_ordem")
        ]

    def __str__(self):
        return f"Escapamento de ar {self.ordem}"

    def _limite_normativo(self):
        if self.limite_personalizado is not None:
            return self.limite_personalizado
        automatic = self.calibracao.tecnologia == "digital_automatico"
        if self.calibracao.unidade == "mmHg":
            return Decimal("6") if automatic else Decimal("4")
        return Decimal("0.8") if automatic else Decimal("0.5")

    def recalculate(self, save=False):
        self.taxa_vazamento = _q(leakage_rate(
            self.pressao_inicial, self.pressao_final, self.duracao_minutos
        ))
        self.limite_resolvido = self._limite_normativo()
        if self.calibracao.regra_decisao == "sem_declaracao" or self.taxa_vazamento is None:
            self.resultado = "nao_declarado"
        else:
            self.resultado = (
                "aprovado" if self.taxa_vazamento <= self.limite_resolvido else "reprovado"
            )
        if save and self.pk:
            type(self).objects.filter(pk=self.pk).update(
                taxa_vazamento=self.taxa_vazamento,
                limite_resolvido=self.limite_resolvido,
                resultado=self.resultado,
            )
            self.calibracao.recalcular_resultado(save=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.recalculate(save=True)
