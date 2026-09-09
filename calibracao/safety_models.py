import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from clientes.models import Cliente
from qualidade.models import Documento

from .models import Instrumento, Padrao, ResponsavelCertificado, salvar_com_numero_certificado
from .services.safety_pressure_calculation import (
    average,
    conformity_result,
    correction,
    error,
    repeatability_range,
    resolved_tolerance,
    root_sum_squares,
    sample_standard_deviation,
    standard_uncertainty_from_expanded,
    standard_uncertainty_from_rectangular_limit,
    standard_uncertainty_from_repeatability,
    standard_uncertainty_from_resolution,
)


Q9 = Decimal("0.000000001")


def _q(value):
    return value.quantize(Q9) if value is not None else None


def _normalizar_unidade(unidade):
    return (unidade or "").strip().lower().replace("²", "2").replace(" ", "")


class CalibracaoDispositivoSegurancaPressao(models.Model):
    TIPO_DISPOSITIVO_CHOICES = (
        ("valvula_seguranca", "Válvula de segurança"),
        ("valvula_alivio", "Válvula de alívio"),
        ("valvula_seguranca_alivio", "Válvula de segurança e alívio"),
        ("pressostato", "Pressostato"),
        ("vacuostato", "Vacuostato"),
    )
    TIPO_DOCUMENTO_CHOICES = (
        ("calibracao", "Certificado de calibração"),
        ("ensaio_funcional", "Certificado de ensaio funcional"),
        ("ensaio_ajuste", "Certificado de ensaio e ajuste"),
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
    UNIDADE_CHOICES = (
        ("Pa", "Pa"), ("hPa", "hPa"), ("kPa", "kPa"), ("MPa", "MPa"),
        ("bar", "bar"), ("mbar", "mbar"), ("psi", "psi"),
        ("kgf/cm2", "kgf/cm²"), ("mmHg", "mmHg"), ("mH2O", "mH2O"),
        ("mmH2O", "mmH2O"), ("inH2O", "inH2O"),
    )
    REGRA_DECISAO_CHOICES = (
        ("sem_declaracao", "Sem declaração de conformidade"),
        ("aceitacao_simples", "Aceitação simples: |erro| ≤ tolerância"),
        ("banda_guarda", "Banda de guarda: |erro| + U ≤ tolerância"),
    )
    CRITERIO_TIPO_CHOICES = (
        ("absoluto", "Valor absoluto"),
        ("percentual", "Percentual da pressão de referência"),
    )
    RESULTADO_CHOICES = (
        ("", "---------"),
        ("conforme", "Conforme"),
        ("nao_conforme", "Não conforme"),
        ("nao_declarado", "Não declarado"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrumento = models.ForeignKey(
        Instrumento, on_delete=models.PROTECT, related_name="calibracoes_dispositivo_seguranca_pressao"
    )
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name="calibracoes_dispositivo_seguranca_pressao"
    )
    tipo_dispositivo = models.CharField(max_length=40, choices=TIPO_DISPOSITIVO_CHOICES)
    tipo_documento = models.CharField(max_length=30, choices=TIPO_DOCUMENTO_CHOICES, default="calibracao")
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
    equipamento_protegido = models.CharField(max_length=255, blank=True)
    fluido_servico = models.CharField(max_length=100, blank=True)
    fabricante = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    numero_serie = models.CharField(max_length=100, blank=True)
    tamanho_nominal = models.CharField(max_length=60, blank=True)
    tipo_conexao = models.CharField(max_length=100, blank=True)
    pressao_ajuste_declarada = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    pmta = models.DecimalField("PMTA", max_digits=18, decimal_places=9, null=True, blank=True)
    unidade = models.CharField(max_length=20, choices=UNIDADE_CHOICES, default="bar")

    fluido_teste = models.CharField(max_length=100, blank=True)
    ensaio_com_ajuste = models.BooleanField(default=False)
    ensaio_a_quente = models.BooleanField(default=False)
    manutencao_realizada = models.BooleanField(default=False)
    exame_visual_inicial = models.TextField(blank=True)
    defeitos_constatados = models.TextField(blank=True)
    condicao_final = models.TextField(blank=True)

    procedimento_documento = models.ForeignKey(
        Documento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="calibracoes_dispositivo_seguranca_pressao",
    )
    procedimento_numero = models.CharField(max_length=100, blank=True)
    procedimento_revisao = models.CharField(max_length=50, blank=True)
    referencias_normativas = models.TextField(
        blank=True,
        help_text="Informe somente referências realmente aplicáveis ao serviço e à edição utilizada.",
    )

    temperatura_inicial = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    temperatura_final = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    umidade_inicial = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    umidade_final = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    criterio_tipo = models.CharField(max_length=20, choices=CRITERIO_TIPO_CHOICES, default="absoluto")
    criterio_valor = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    criterio_origem = models.CharField(max_length=30, blank=True)
    criterio_referencia = models.CharField(max_length=255, blank=True)
    regra_decisao = models.CharField(max_length=30, choices=REGRA_DECISAO_CHOICES, default="sem_declaracao")

    resultado_inicial = models.CharField(max_length=20, choices=RESULTADO_CHOICES, blank=True)
    resultado_final = models.CharField(max_length=20, choices=RESULTADO_CHOICES, blank=True)
    observacoes_certificado = models.TextField(blank=True)
    responsavel_tecnico = models.ForeignKey(
        ResponsavelCertificado, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="calibracoes_seguranca_como_responsavel",
    )
    tecnico_executante = models.ForeignKey(
        ResponsavelCertificado, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="calibracoes_seguranca_como_executante",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Calibração de dispositivo de segurança - pressão"
        verbose_name_plural = "Calibrações de dispositivos de segurança - pressão"
        ordering = ("-data_calibracao", "-created_at")

    def __str__(self):
        return f"{self.numero_certificado or 'Em elaboração'} - {self.instrumento}"

    @property
    def titulo_certificado(self):
        return f"{self.get_tipo_documento_display()} - {self.get_tipo_dispositivo_display()}"

    def _gerar_numero_certificado(self):
        ano = (self.data_calibracao or date.today()).year
        prefixo = f"SEG-{ano}"
        existentes = type(self).objects.exclude(pk=self.pk).filter(
            numero_certificado__startswith=f"{prefixo}-"
        ).values_list("numero_certificado", flat=True)
        usados = set()
        for numero in existentes:
            try:
                usados.add(int(str(numero).rsplit("-", 1)[-1]))
            except (TypeError, ValueError):
                continue
        sequencia = 1
        while sequencia in usados:
            sequencia += 1
        return f"{prefixo}-{sequencia:04d}"

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
                partes = [
                    getattr(self.cliente, "endereco", ""), getattr(self.cliente, "numero", ""),
                    getattr(self.cliente, "bairro", ""), getattr(self.cliente, "cidade", ""),
                    getattr(self.cliente, "uf", ""),
                ]
                self.endereco_cliente = ", ".join(str(parte) for parte in partes if parte)
        if self.procedimento_documento_id:
            self.procedimento_numero = self.procedimento_documento.codigo or ""
            self.procedimento_revisao = self.procedimento_documento.revisao or ""

    def pendencias_emissao(self):
        pending = []
        required = (
            (self.numero_certificado, "Número do certificado"),
            (self.contratante, "Identificação do contratante"),
            (self.endereco_cliente, "Endereço do cliente"),
            (self.fluido_teste, "Fluido de teste"),
            (self.procedimento_numero, "Método/procedimento e revisão"),
            (self.responsavel_tecnico_id, "Responsável técnico"),
            (self.tecnico_executante_id, "Técnico executante"),
        )
        pending.extend(label for value, label in required if not value)
        if None in (self.temperatura_inicial, self.temperatura_final, self.umidade_inicial, self.umidade_final):
            pending.append("Condições ambientais completas")
        if not self.padroes_utilizados.exists():
            pending.append("Padrão utilizado")
        else:
            for padrao in self.padroes_utilizados.all():
                if padrao.situacao_na_data != "valido":
                    pending.append(f"Padrão {padrao.codigo or padrao.padrao}: {padrao.get_situacao_na_data_display()}")
                if _normalizar_unidade(padrao.unidade) != _normalizar_unidade(self.unidade):
                    pending.append(
                        f"Unidade do padrão {padrao.codigo or padrao.padrao} divergente da unidade do resultado"
                    )
        if not self.pontos.exists():
            pending.append("Pontos/ciclos de ensaio")
        if self.regra_decisao != "sem_declaracao" and self.criterio_valor is None:
            pending.append("Critério de aceitação para a declaração de conformidade")
        return pending

    def recalcular_resultados(self, save=True):
        mapping = {"aprovado": "conforme", "reprovado": "nao_conforme", "nao_declarado": "nao_declarado"}
        for condition, field in (("encontrado", "resultado_inicial"), ("deixado", "resultado_final")):
            results = list(self.pontos.filter(condicao=condition).exclude(resultado="").values_list("resultado", flat=True))
            if not results:
                value = ""
            elif "reprovado" in results:
                value = "nao_conforme"
            elif all(result == "aprovado" for result in results):
                value = "conforme"
            else:
                value = mapping.get(results[0], "nao_declarado")
            setattr(self, field, value)
        if save and self.pk:
            type(self).objects.filter(pk=self.pk).update(
                resultado_inicial=self.resultado_inicial, resultado_final=self.resultado_final
            )

    def clean(self):
        super().clean()
        if self.instrumento_id and self.cliente_id and self.instrumento.cliente_id != self.cliente_id:
            raise ValidationError({"cliente": "O cliente deve ser o proprietário do instrumento selecionado."})
        if self.status == "emitida" and self.pk:
            pending = self.pendencias_emissao()
            if pending:
                raise ValidationError({"status": "Emissão bloqueada: " + "; ".join(pending)})

    def save(self, *args, **kwargs):
        self._preencher_snapshot()
        salvar_com_numero_certificado(self, super().save, args, kwargs)


class DispositivoSegurancaPadraoUtilizado(models.Model):
    SITUACAO_CHOICES = (
        ("valido", "Válido na data"),
        ("vencido", "Vencido na data"),
        ("suspenso", "Suspenso"),
        ("incompleto", "Rastreabilidade incompleta"),
    )
    calibracao = models.ForeignKey(
        CalibracaoDispositivoSegurancaPressao, on_delete=models.CASCADE, related_name="padroes_utilizados"
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    padrao = models.ForeignKey(Padrao, on_delete=models.PROTECT, related_name="usos_dispositivo_seguranca_pressao")
    codigo = models.CharField(max_length=50, blank=True)
    descricao = models.CharField(max_length=255, blank=True)
    numero_certificado = models.CharField(max_length=100, blank=True)
    laboratorio_emitente = models.CharField(max_length=150, blank=True)
    data_calibracao = models.DateField(null=True, blank=True)
    validade = models.DateField(null=True, blank=True)
    resolucao = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    incerteza_expandida = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    fator_k = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    graus_liberdade = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unidade = models.CharField(max_length=30, blank=True)
    situacao_na_data = models.CharField(max_length=20, choices=SITUACAO_CHOICES, default="incompleto")

    class Meta:
        verbose_name = "Padrão utilizado - dispositivo de segurança"
        verbose_name_plural = "Padrões utilizados - dispositivos de segurança"
        ordering = ("ordem",)
        constraints = [
            models.UniqueConstraint(fields=("calibracao", "ordem"), name="uniq_seguranca_padrao_ordem")
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


class DispositivoSegurancaPonto(models.Model):
    CONDICAO_CHOICES = (("encontrado", "Como encontrado"), ("deixado", "Como deixado"))
    RESULTADO_CHOICES = (
        ("", "---------"), ("aprovado", "Aprovado"),
        ("reprovado", "Reprovado"), ("nao_declarado", "Não declarado"),
    )
    calibracao = models.ForeignKey(
        CalibracaoDispositivoSegurancaPressao, on_delete=models.CASCADE, related_name="pontos"
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    condicao = models.CharField(max_length=20, choices=CONDICAO_CHOICES, default="encontrado")
    pressao_referencia = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    atuacao_1 = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    atuacao_2 = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    atuacao_3 = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    rearme_1 = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    rearme_2 = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    rearme_3 = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    media_atuacao = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    media_rearme = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    erro = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    correcao = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    repetitividade = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    desvio_padrao = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    histerese = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    criterio_tipo = models.CharField(
        max_length=20, choices=CalibracaoDispositivoSegurancaPressao.CRITERIO_TIPO_CHOICES, blank=True
    )
    criterio_valor = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    tolerancia_resolvida = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES, blank=True, editable=False)
    observacoes = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Ponto/ciclo do dispositivo de segurança"
        verbose_name_plural = "Pontos/ciclos do dispositivo de segurança"
        ordering = ("condicao", "ordem")
        constraints = [
            models.UniqueConstraint(fields=("calibracao", "condicao", "ordem"), name="uniq_seguranca_ponto")
        ]

    def __str__(self):
        return f"{self.get_condicao_display()} - ponto {self.ordem}"

    @property
    def incerteza_expandida(self):
        item = self.calibracao.pontos_incerteza.filter(ordem=self.ordem, condicao=self.condicao).first()
        return item.incerteza_expandida if item else None

    def recalculate(self, save=False):
        readings = [self.atuacao_1, self.atuacao_2, self.atuacao_3]
        reset_readings = [self.rearme_1, self.rearme_2, self.rearme_3]
        self.media_atuacao = _q(average(readings))
        self.media_rearme = _q(average(reset_readings))
        self.erro = _q(error(self.media_atuacao, self.pressao_referencia))
        self.correcao = _q(correction(self.erro))
        self.repetitividade = _q(repeatability_range(readings))
        self.desvio_padrao = _q(sample_standard_deviation(readings))
        self.histerese = (
            _q(abs(self.media_atuacao - self.media_rearme))
            if self.media_atuacao is not None and self.media_rearme is not None else None
        )
        criterion_type = self.criterio_tipo or self.calibracao.criterio_tipo
        criterion_value = self.criterio_valor
        if criterion_value is None:
            criterion_value = self.calibracao.criterio_valor
        self.tolerancia_resolvida = _q(
            resolved_tolerance(self.pressao_referencia, criterion_value, criterion_type)
        )
        self.resultado = conformity_result(
            self.erro, self.tolerancia_resolvida, self.incerteza_expandida, self.calibracao.regra_decisao
        )
        if save and self.pk:
            type(self).objects.filter(pk=self.pk).update(
                media_atuacao=self.media_atuacao, media_rearme=self.media_rearme, erro=self.erro,
                correcao=self.correcao, repetitividade=self.repetitividade,
                desvio_padrao=self.desvio_padrao, histerese=self.histerese,
                tolerancia_resolvida=self.tolerancia_resolvida, resultado=self.resultado,
            )
            self.calibracao.recalcular_resultados(save=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.recalculate(save=True)


class DispositivoSegurancaIncertezaPonto(models.Model):
    calibracao = models.ForeignKey(
        CalibracaoDispositivoSegurancaPressao, on_delete=models.CASCADE, related_name="pontos_incerteza"
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    condicao = models.CharField(
        max_length=20, choices=DispositivoSegurancaPonto.CONDICAO_CHOICES, default="encontrado"
    )
    resolucao_dispositivo = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    resolucao_padrao = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    incerteza_certificado_padrao = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    fator_k_certificado_padrao = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    limite_deriva_padrao = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    u_repetitividade = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    u_resolucao_dispositivo = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    u_resolucao_padrao = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    u_certificado_padrao = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    u_deriva_padrao = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    u_outros = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True)
    outros_descricao = models.CharField(max_length=255, blank=True)
    incerteza_padrao_combinada = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)
    fator_k = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal("2"))
    graus_liberdade = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    incerteza_expandida = models.DecimalField(max_digits=18, decimal_places=9, null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Incerteza do ponto - dispositivo de segurança"
        verbose_name_plural = "Incertezas dos pontos - dispositivos de segurança"
        ordering = ("condicao", "ordem")
        constraints = [
            models.UniqueConstraint(
                fields=("calibracao", "condicao", "ordem"), name="uniq_seguranca_incerteza_ponto"
            )
        ]

    def __str__(self):
        return f"Incerteza - {self.get_condicao_display()} - ponto {self.ordem}"

    def recalculate(self, save=False):
        point = self.calibracao.pontos.filter(ordem=self.ordem, condicao=self.condicao).first()
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
        repetitions = len([
            value for value in (
                getattr(point, "atuacao_1", None), getattr(point, "atuacao_2", None), getattr(point, "atuacao_3", None)
            ) if value is not None
        ])
        self.u_repetitividade = _q(standard_uncertainty_from_repeatability(
            getattr(point, "desvio_padrao", None), repetitions
        ))
        self.u_resolucao_dispositivo = _q(standard_uncertainty_from_resolution(self.resolucao_dispositivo))
        self.u_resolucao_padrao = _q(standard_uncertainty_from_resolution(self.resolucao_padrao))
        self.u_certificado_padrao = _q(standard_uncertainty_from_expanded(
            self.incerteza_certificado_padrao, self.fator_k_certificado_padrao
        ))
        self.u_deriva_padrao = _q(standard_uncertainty_from_rectangular_limit(self.limite_deriva_padrao))
        self.incerteza_padrao_combinada = _q(root_sum_squares((
            self.u_repetitividade, self.u_resolucao_dispositivo, self.u_resolucao_padrao,
            self.u_certificado_padrao, self.u_deriva_padrao, self.u_outros,
        )))
        self.incerteza_expandida = (
            _q(self.incerteza_padrao_combinada * (self.fator_k or Decimal("2")))
            if self.incerteza_padrao_combinada is not None else None
        )
        if save and self.pk:
            type(self).objects.filter(pk=self.pk).update(
                resolucao_padrao=self.resolucao_padrao,
                incerteza_certificado_padrao=self.incerteza_certificado_padrao,
                fator_k_certificado_padrao=self.fator_k_certificado_padrao,
                u_repetitividade=self.u_repetitividade,
                u_resolucao_dispositivo=self.u_resolucao_dispositivo,
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
