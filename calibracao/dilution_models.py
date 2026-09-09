from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, localcontext

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


SQRT_3 = Decimal("3").sqrt()
SQRT_6 = Decimal("6").sqrt()
SQRT_12 = Decimal("12").sqrt()
NINE_DECIMALS = Decimal("0.000000001")


def _decimal(value):
    if value in (None, ""):
        return None
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _q(value):
    value = _decimal(value)
    return value.quantize(NINE_DECIMALS) if value is not None else None


def _fator_abrangencia_95(graus_liberdade):
    veff = _decimal(graus_liberdade)
    if veff is None:
        return Decimal("2.000")
    if veff >= 30:
        return Decimal("2.000")
    if veff >= 20:
        return Decimal("2.090")
    if veff >= 15:
        return Decimal("2.130")
    if veff >= 10:
        return Decimal("2.230")
    if veff >= 9:
        return Decimal("2.260")
    if veff >= 8:
        return Decimal("2.310")
    if veff >= 7:
        return Decimal("2.360")
    if veff >= 6:
        return Decimal("2.450")
    if veff >= 5:
        return Decimal("2.570")
    if veff >= 4:
        return Decimal("2.780")
    if veff >= 3:
        return Decimal("3.180")
    if veff >= 2:
        return Decimal("4.300")
    if veff >= 1:
        return Decimal("12.710")
    return Decimal("2.000")


class PreparacaoPadraoSequencia(models.Model):
    aplicacao = models.CharField(max_length=30)
    data_preparacao = models.DateField()
    ultimo_numero = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Sequência de preparação de padrão"
        verbose_name_plural = "Sequências de preparação de padrões"
        constraints = [
            models.UniqueConstraint(
                fields=("aplicacao", "data_preparacao"),
                name="unique_preparacao_padrao_sequencia_data",
            )
        ]


class PreparacaoPadrao(models.Model):
    APLICACAO_CHOICES = (
        ("turbidez", "Turbidez", "TUR"),
        ("cor", "Cor", "COR"),
        ("cloro", "Cloro", "CLO"),
        ("fluor", "Flúor", "FLU"),
        ("colorimetria", "Colorimetria geral", "COL"),
        ("condutividade", "Condutividade", "CON"),
        ("outro", "Outra aplicação", "OUT"),
    )
    APLICACAO_DISPLAY_CHOICES = tuple((value, label) for value, label, _ in APLICACAO_CHOICES)
    APLICACAO_PREFIXOS = {value: prefix for value, _, prefix in APLICACAO_CHOICES}
    TIPO_CHOICES = (
        ("volumetrica", "Diluição volumétrica"),
        ("serial", "Diluição volumétrica serial"),
        ("gravimetrica", "Preparação gravimétrica"),
        ("outro", "Outro modelo validado"),
    )
    STATUS_CHOICES = (
        ("rascunho", "Rascunho"),
        ("em_revisao", "Em revisão"),
        ("aprovado", "Aprovado"),
        ("cancelado", "Cancelado"),
    )

    codigo = models.CharField(max_length=50, unique=True, blank=True, editable=False)
    codigo_anterior = models.CharField(
        max_length=50,
        blank=True,
        editable=False,
        help_text="Identificação preservada quando um registro retroativo é reidentificado.",
    )
    revisao_de = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="revisoes",
        editable=False,
        verbose_name="Revisão do registro",
    )
    motivo_revisao = models.TextField(
        blank=True,
        help_text="Descreva o dado corrigido e o impacto metrológico da revisão.",
    )
    aplicacao = models.CharField(max_length=30, choices=APLICACAO_DISPLAY_CHOICES)
    tipo_preparacao = models.CharField(max_length=30, choices=TIPO_CHOICES, default="volumetrica")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="rascunho",
        help_text="A aprovação é realizada pela ação controlada após a revisão.",
    )
    data_preparacao = models.DateField(default=timezone.localdate)
    validade = models.DateField()
    padrao_origem = models.ForeignKey(
        "calibracao.Padrao",
        on_delete=models.PROTECT,
        related_name="preparacoes_como_origem",
    )
    procedimento = models.ForeignKey(
        "qualidade.Documento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preparacoes_padrao",
    )
    valor_alvo = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        null=True,
        blank=True,
        help_text="Campo legado. No novo gabarito, informe os valores nas linhas de saída.",
    )
    unidade = models.CharField(max_length=30)
    lote = models.CharField(max_length=100, blank=True)
    matriz_diluente = models.CharField(max_length=150, blank=True)
    temperatura_preparacao = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    responsavel_preparo = models.CharField(max_length=255)
    responsavel_revisao = models.CharField(max_length=255, blank=True)
    condicao_armazenamento = models.CharField(max_length=255, blank=True)
    observacoes = models.TextField(blank=True)
    registro_retroativo = models.BooleanField(
        default=False,
        help_text="Marque quando o registro estiver sendo lançado após a data real da preparação.",
    )
    justificativa_registro_retroativo = models.TextField(
        blank=True,
        help_text="Informe por que o registro não foi realizado na data da preparação.",
    )
    evidencia_registro_retroativo = models.FileField(
        upload_to="calibracao/preparacoes/evidencias_retroativas/",
        null=True,
        blank=True,
        help_text="Anexe o registro original que comprova a preparação e a data informada.",
    )
    registrado_retroativamente_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="preparacoes_padrao_registradas_retroativamente",
        editable=False,
    )
    registrado_retroativamente_em = models.DateTimeField(null=True, blank=True, editable=False)

    valor_atribuido = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True, editable=False)
    incerteza_padrao_combinada = models.DecimalField(
        max_digits=20, decimal_places=9, null=True, blank=True, editable=False
    )
    graus_liberdade_efetivos = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True, editable=False
    )
    fator_abrangencia = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True, editable=False
    )
    incerteza_expandida = models.DecimalField(
        max_digits=20, decimal_places=9, null=True, blank=True, editable=False
    )
    padrao_gerado = models.OneToOneField(
        "calibracao.Padrao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="preparacao_geradora",
        editable=False,
    )
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="preparacoes_padrao_aprovadas",
        editable=False,
    )
    aprovado_em = models.DateTimeField(null=True, blank=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Diluição e preparação de padrão"
        verbose_name_plural = "Diluições e preparações de padrões"
        ordering = ("-data_preparacao", "-criado_em")

    @property
    def prefixo_aplicacao(self):
        return self.APLICACAO_PREFIXOS.get(self.aplicacao, "OUT")

    def _gerar_codigo(self, using):
        sequencia, _ = PreparacaoPadraoSequencia.objects.using(using).get_or_create(
            aplicacao=self.aplicacao,
            data_preparacao=self.data_preparacao,
            defaults={"ultimo_numero": 0},
        )
        sequencia = (
            PreparacaoPadraoSequencia.objects.using(using)
            .select_for_update()
            .get(pk=sequencia.pk)
        )
        sequencia.ultimo_numero += 1
        sequencia.save(update_fields=("ultimo_numero",))
        data_token = self.data_preparacao.strftime("%d%m%y")
        ano_token = self.data_preparacao.strftime("%y")
        return f"DIL-{self.prefixo_aplicacao}-{data_token}-{sequencia.ultimo_numero:02d}/{ano_token}"

    def clean(self):
        super().clean()
        if self.validade and self.data_preparacao and self.validade < self.data_preparacao:
            raise ValidationError({"validade": "A validade não pode ser anterior à preparação."})
        if self.padrao_origem_id and self.unidade and self.padrao_origem.unidade:
            if self.padrao_origem.unidade.strip().lower() != self.unidade.strip().lower():
                raise ValidationError(
                    {"unidade": "A unidade deve ser compatível com a unidade do padrão de origem."}
                )

    def save(self, *args, **kwargs):
        if isinstance(self.data_preparacao, str):
            self.data_preparacao = date.fromisoformat(self.data_preparacao)
        if self.codigo_anterior:
            self.registro_retroativo = True
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = tuple(set(update_fields) | {"registro_retroativo"})
        if self.codigo:
            token_data = f"-{self.data_preparacao:%d%m%y}-"
            if (
                self.registro_retroativo
                and self.status != "aprovado"
                and token_data not in self.codigo
            ):
                using = kwargs.get("using") or self._state.db or "default"
                with transaction.atomic(using=using):
                    if not self.codigo_anterior:
                        self.codigo_anterior = self.codigo
                    self.codigo = self._gerar_codigo(using)
                    update_fields = kwargs.get("update_fields")
                    if update_fields is not None:
                        kwargs["update_fields"] = tuple(
                            set(update_fields) | {"codigo", "codigo_anterior"}
                        )
                    return super().save(*args, **kwargs)
            return super().save(*args, **kwargs)
        using = kwargs.get("using") or self._state.db or "default"
        with transaction.atomic(using=using):
            self.codigo = self._gerar_codigo(using)
            return super().save(*args, **kwargs)

    def _sincronizar_componente_origem(self):
        if self.valor_atribuido is None or not self.padrao_origem_id:
            return
        valor_origem = _decimal(self.padrao_origem.valor_nominal)
        incerteza_origem = _decimal(self.padrao_origem.incerteza)
        if not valor_origem or incerteza_origem is None:
            return
        coeficiente = abs(self.valor_atribuido / valor_origem)
        PreparacaoPadraoComponenteIncerteza.objects.update_or_create(
            preparacao=self,
            chave_automatica="padrao_origem",
            defaults={
                "ordem": 1,
                "nome": f"Incerteza do padrão de origem {self.padrao_origem.codigo}",
                "fonte_padrao": self.padrao_origem,
                "tipo_valor": "expandida",
                "valor_informado": incerteza_origem,
                "fator_abrangencia_origem": self.padrao_origem.fator_k or Decimal("2"),
                "graus_liberdade": self.padrao_origem.graus_liberdade,
                "coeficiente_sensibilidade": coeficiente,
                "automatico": True,
                "incluir": True,
            },
        )

    def _sincronizar_componentes_equipamentos(self):
        chaves_ativas = {"padrao_origem"}
        if self.valor_atribuido is None:
            return chaves_ativas
        for equipamento in self.equipamentos.select_related("padrao", "etapa").all():
            equipamento.atualizar_snapshot()
            coeficiente = equipamento.coeficiente_para_resultado(self.valor_atribuido)
            if coeficiente is None:
                continue
            if equipamento.incerteza_snapshot is not None:
                chave = f"equipamento:{equipamento.pk}:incerteza"
                chaves_ativas.add(chave)
                PreparacaoPadraoComponenteIncerteza.objects.update_or_create(
                    preparacao=self,
                    chave_automatica=chave,
                    defaults={
                        "ordem": 20 + equipamento.ordem,
                        "nome": f"Incerteza de {equipamento.get_papel_display()} - {equipamento.padrao.codigo}",
                        "fonte_padrao": equipamento.padrao,
                        "tipo_valor": "expandida",
                        "valor_informado": equipamento.incerteza_snapshot,
                        "fator_abrangencia_origem": equipamento.fator_k_snapshot or Decimal("2"),
                        "graus_liberdade": equipamento.graus_liberdade_snapshot,
                        "coeficiente_sensibilidade": coeficiente,
                        "automatico": True,
                        "incluir": True,
                    },
                )
            if equipamento.resolucao_snapshot is not None:
                chave = f"equipamento:{equipamento.pk}:resolucao"
                chaves_ativas.add(chave)
                PreparacaoPadraoComponenteIncerteza.objects.update_or_create(
                    preparacao=self,
                    chave_automatica=chave,
                    defaults={
                        "ordem": 40 + equipamento.ordem,
                        "nome": f"Resolução de {equipamento.get_papel_display()} - {equipamento.padrao.codigo}",
                        "fonte_padrao": equipamento.padrao,
                        "tipo_valor": "resolucao",
                        "valor_informado": equipamento.resolucao_snapshot,
                        "coeficiente_sensibilidade": coeficiente,
                        "automatico": True,
                        "incluir": True,
                    },
                )
        return chaves_ativas

    def _sincronizar_componentes_etapas(self):
        chaves_ativas = set()
        if self.valor_atribuido is None:
            return chaves_ativas
        for etapa in self.etapas.select_related("pipeta", "recipiente_final"):
            equipamentos = (
                ("pipeta", etapa.pipeta, etapa.volume_aliquota, Decimal("1")),
                ("recipiente_final", etapa.recipiente_final, etapa.volume_final, Decimal("-1")),
            )
            for papel, padrao, volume, sinal in equipamentos:
                if not padrao or not volume:
                    continue
                coeficiente = sinal * self.valor_atribuido / volume
                if padrao.incerteza is not None:
                    chave = f"etapa:{etapa.pk}:{papel}:incerteza"
                    chaves_ativas.add(chave)
                    PreparacaoPadraoComponenteIncerteza.objects.update_or_create(
                        preparacao=self,
                        chave_automatica=chave,
                        defaults={
                            "ordem": 10 + (etapa.ordem * 10),
                            "nome": f"Incerteza de {papel.replace('_', ' ')} - {padrao.codigo}",
                            "fonte_padrao": padrao,
                            "tipo_valor": "expandida",
                            "valor_informado": padrao.incerteza,
                            "fator_abrangencia_origem": padrao.fator_k or Decimal("2"),
                            "graus_liberdade": padrao.graus_liberdade,
                            "coeficiente_sensibilidade": coeficiente,
                            "automatico": True,
                            "incluir": True,
                        },
                    )
                if padrao.resolucao is not None:
                    chave = f"etapa:{etapa.pk}:{papel}:resolucao"
                    chaves_ativas.add(chave)
                    PreparacaoPadraoComponenteIncerteza.objects.update_or_create(
                        preparacao=self,
                        chave_automatica=chave,
                        defaults={
                            "ordem": 11 + (etapa.ordem * 10),
                            "nome": f"Resolução de {papel.replace('_', ' ')} - {padrao.codigo}",
                            "fonte_padrao": padrao,
                            "tipo_valor": "resolucao",
                            "valor_informado": padrao.resolucao,
                            "coeficiente_sensibilidade": coeficiente,
                            "automatico": True,
                            "incluir": True,
                        },
                    )
        return chaves_ativas

    @transaction.atomic
    def recalcular(self):
        resultados = list(self.resultados.select_related("pipeta", "recipiente_final"))
        if resultados:
            for equipamento in self.equipamentos.select_related("padrao"):
                equipamento.atualizar_snapshot()
            for resultado in resultados:
                resultado.calcular()
            # Os resultados metrológicos pertencem a cada linha do gabarito.
            # Os campos abaixo são mantidos apenas para registros legados de resultado único.
            resumo = resultados[0] if len(resultados) == 1 else None
            self.valor_atribuido = resumo.valor_calculado if resumo else None
            self.incerteza_padrao_combinada = resumo.incerteza_padrao_combinada if resumo else None
            self.graus_liberdade_efetivos = resumo.graus_liberdade_efetivos if resumo else None
            self.fator_abrangencia = resumo.fator_abrangencia if resumo else None
            self.incerteza_expandida = resumo.incerteza_expandida if resumo else None
            type(self).objects.filter(pk=self.pk).update(
                valor_atribuido=self.valor_atribuido,
                incerteza_padrao_combinada=self.incerteza_padrao_combinada,
                graus_liberdade_efetivos=self.graus_liberdade_efetivos,
                fator_abrangencia=self.fator_abrangencia,
                incerteza_expandida=self.incerteza_expandida,
            )
            return

        valor_anterior = _decimal(self.padrao_origem.valor_nominal) if self.padrao_origem_id else None
        etapas = list(self.etapas.order_by("ordem", "pk"))
        for etapa in etapas:
            if etapa.valor_entrada is None:
                etapa.valor_entrada = valor_anterior
            etapa.calcular()
            valor_anterior = etapa.valor_resultante

        self.valor_atribuido = valor_anterior if etapas else None
        type(self).objects.filter(pk=self.pk).update(valor_atribuido=self.valor_atribuido)

        self._sincronizar_componente_origem()
        chaves_ativas = self._sincronizar_componentes_equipamentos()
        chaves_ativas.update(self._sincronizar_componentes_etapas())
        self.componentes.filter(automatico=True).exclude(chave_automatica__in=chaves_ativas).delete()

        componentes = list(self.componentes.filter(incluir=True).order_by("ordem", "pk"))
        for componente in componentes:
            componente.calcular()

        contribuicoes = [abs(c.contribuicao) for c in componentes if c.contribuicao is not None]
        if contribuicoes:
            with localcontext() as context:
                context.prec = 40
                uc = sum((valor * valor for valor in contribuicoes), Decimal("0")).sqrt()
            denominador = Decimal("0")
            for componente in componentes:
                contribuicao = abs(componente.contribuicao or Decimal("0"))
                graus = _decimal(componente.graus_liberdade)
                if contribuicao and graus and graus > 0:
                    denominador += (contribuicao ** 4) / graus
            veff = (uc ** 4) / denominador if denominador else None
            k = _fator_abrangencia_95(veff)
            expandida = uc * k
            self.incerteza_padrao_combinada = _q(uc)
            self.graus_liberdade_efetivos = veff.quantize(Decimal("0.01")) if veff is not None else None
            self.fator_abrangencia = k
            self.incerteza_expandida = _q(expandida)
        else:
            self.incerteza_padrao_combinada = None
            self.graus_liberdade_efetivos = None
            self.fator_abrangencia = None
            self.incerteza_expandida = None
        type(self).objects.filter(pk=self.pk).update(
            valor_atribuido=self.valor_atribuido,
            incerteza_padrao_combinada=self.incerteza_padrao_combinada,
            graus_liberdade_efetivos=self.graus_liberdade_efetivos,
            fator_abrangencia=self.fator_abrangencia,
            incerteza_expandida=self.incerteza_expandida,
        )

    def pendencias_aprovacao(self):
        pendencias = []
        if self.data_preparacao and f"-{self.data_preparacao:%d%m%y}-" not in self.codigo:
            pendencias.append(
                "o código não corresponde à data da preparação; salve o registro retroativo para reidentificar"
            )
        usa_gabarito = self.resultados.exists()
        if self.status != "em_revisao":
            pendencias.append("a preparação deve ser enviada para revisão antes da aprovação")
        if self.registro_retroativo:
            if not self.justificativa_registro_retroativo.strip():
                pendencias.append("justificativa do registro retroativo não informada")
            if not self.evidencia_registro_retroativo:
                pendencias.append("evidência documental do registro retroativo não anexada")
            if not self.registrado_retroativamente_por_id or not self.registrado_retroativamente_em:
                pendencias.append("responsável ou data do lançamento retroativo não registrados")
        if self.tipo_preparacao not in ("volumetrica", "serial"):
            pendencias.append(
                "o modelo de cálculo desta preparação ainda não foi implementado e validado"
            )
        if usa_gabarito and self.tipo_preparacao != "volumetrica":
            pendencias.append(
                "o gabarito com múltiplos valores está validado somente para diluição volumétrica direta"
            )
        if not usa_gabarito and not self.etapas.exists():
            pendencias.append("nenhuma etapa de diluição cadastrada")
        if not usa_gabarito and self.valor_atribuido is None:
            pendencias.append("valor atribuído não calculado")
        if not usa_gabarito and self.incerteza_expandida is None:
            pendencias.append("orçamento de incerteza incompleto")
        if not usa_gabarito and not self.componentes.filter(incluir=True).exists():
            pendencias.append("nenhuma componente de incerteza incluída")
        if not self.responsavel_revisao:
            pendencias.append("responsável pela revisão não informado")
        if not self.procedimento_id:
            pendencias.append("procedimento controlado não informado")
        elif self.procedimento.status != "vigente":
            pendencias.append("o procedimento controlado selecionado não está vigente")
        if self.padrao_origem.incerteza is None:
            pendencias.append("incerteza do padrão de origem não informada")
        if not self.padrao_origem.fator_k:
            pendencias.append("fator k do padrão de origem não informado")
        if self.tipo_preparacao in ("volumetrica", "serial"):
            if self.temperatura_preparacao is None:
                pendencias.append("temperatura da preparação não informada")
            if not self.matriz_diluente:
                pendencias.append("matriz ou diluente não informado")
            for resultado in self.resultados.select_related("pipeta", "recipiente_final"):
                pendencias.extend(resultado.pendencias_aprovacao(self.data_preparacao))
            for etapa in self.etapas.select_related("pipeta", "recipiente_final"):
                if not etapa.pipeta_id:
                    pendencias.append(f"pipeta da etapa {etapa.ordem} não informada")
                if not etapa.recipiente_final_id:
                    pendencias.append(f"recipiente final da etapa {etapa.ordem} não informado")
                unidade_etapa = (etapa.unidade_volume or "").strip().casefold()
                for nome, padrao in (
                    ("pipeta", etapa.pipeta),
                    ("recipiente final", etapa.recipiente_final),
                ):
                    if not padrao:
                        continue
                    if (padrao.unidade or "").strip().casefold() != unidade_etapa:
                        pendencias.append(
                            f"unidade do {nome} da etapa {etapa.ordem} incompatível "
                            f"com {etapa.unidade_volume}"
                        )
                    if padrao.incerteza is None:
                        pendencias.append(
                            f"incerteza do {nome} da etapa {etapa.ordem} não informada"
                        )
                    if not padrao.fator_k:
                        pendencias.append(
                            f"fator k do {nome} da etapa {etapa.ordem} não informado"
                        )
        if self.padrao_origem.vencimento < self.data_preparacao:
            pendencias.append("padrão de origem vencido na data da preparação")
        if (
            self.padrao_origem.data_calibracao
            and self.padrao_origem.data_calibracao > self.data_preparacao
        ):
            pendencias.append(
                "o certificado do padrão de origem é posterior à data da preparação"
            )
        for equipamento in self.equipamentos.select_related("padrao"):
            if equipamento.padrao.vencimento < self.data_preparacao:
                pendencias.append(f"equipamento/padrão {equipamento.padrao.codigo} vencido")
            if (
                equipamento.padrao.data_calibracao
                and equipamento.padrao.data_calibracao > self.data_preparacao
            ):
                pendencias.append(
                    f"certificado do equipamento/padrão {equipamento.padrao.codigo} posterior à preparação"
                )
        for etapa in self.etapas.select_related("pipeta", "recipiente_final"):
            for padrao in (etapa.pipeta, etapa.recipiente_final):
                if padrao and padrao.vencimento < self.data_preparacao:
                    pendencias.append(f"equipamento/padrão {padrao.codigo} vencido")
        return pendencias

    @transaction.atomic
    def aprovar(self, usuario):
        self.recalcular()
        pendencias = self.pendencias_aprovacao()
        if pendencias:
            raise ValidationError(pendencias)
        from .models import Padrao

        resultados = list(self.resultados.order_by("ordem", "pk"))
        if resultados:
            for resultado in resultados:
                descricao = (
                    f"Padrão preparado - {self.get_aplicacao_display()} - "
                    f"{resultado.valor_calculado} {self.unidade} - {resultado.codigo_resultado}"
                )
                padrao = resultado.padrao_gerado or Padrao(descricao=descricao)
                padrao.descricao = descricao
                padrao.numero_certificado = resultado.codigo_resultado
                padrao.laboratorio_emitente = "DS Científica"
                padrao.data_calibracao = self.data_preparacao
                padrao.valor_nominal = resultado.valor_calculado
                padrao.incerteza = resultado.incerteza_expandida
                padrao.fator_k = resultado.fator_abrangencia
                padrao.graus_liberdade = resultado.graus_liberdade_efetivos
                padrao.unidade = self.unidade
                padrao.vencimento = self.validade
                padrao.status = "valido"
                padrao.save()
                resultado.padrao_gerado = padrao
                resultado.save(update_fields=("padrao_gerado",))
            self.status = "aprovado"
            self.aprovado_por = usuario
            self.aprovado_em = timezone.now()
            super().save(update_fields=("status", "aprovado_por", "aprovado_em", "atualizado_em"))
            return

        descricao = (
            f"Padrão preparado - {self.get_aplicacao_display()} - "
            f"{self.valor_atribuido} {self.unidade} - {self.codigo}"
        )
        if self.padrao_gerado_id:
            padrao = self.padrao_gerado
            padrao.descricao = descricao
        else:
            padrao = Padrao(descricao=descricao)
        padrao.numero_certificado = self.codigo
        padrao.laboratorio_emitente = "DS Científica"
        padrao.data_calibracao = self.data_preparacao
        padrao.valor_nominal = self.valor_atribuido
        padrao.incerteza = self.incerteza_expandida
        padrao.fator_k = self.fator_abrangencia
        padrao.graus_liberdade = self.graus_liberdade_efetivos
        padrao.unidade = self.unidade
        padrao.vencimento = self.validade
        padrao.status = "valido"
        padrao.save()

        self.padrao_gerado = padrao
        self.status = "aprovado"
        self.aprovado_por = usuario
        self.aprovado_em = timezone.now()
        super().save(
            update_fields=("padrao_gerado", "status", "aprovado_por", "aprovado_em", "atualizado_em")
        )

    @transaction.atomic
    def duplicar_como_rascunho(self, data_preparacao=None):
        """Duplica o planejamento sem copiar execução, aprovação ou evidência histórica."""
        data_nova = data_preparacao or timezone.localdate()
        prazo_validade = max((self.validade - self.data_preparacao).days, 0)
        copia = type(self).objects.create(
            aplicacao=self.aplicacao,
            tipo_preparacao=self.tipo_preparacao,
            status="rascunho",
            data_preparacao=data_nova,
            validade=data_nova + timedelta(days=prazo_validade),
            padrao_origem=self.padrao_origem,
            procedimento=self.procedimento,
            valor_alvo=self.valor_alvo,
            unidade=self.unidade,
            lote="",
            matriz_diluente=self.matriz_diluente,
            temperatura_preparacao=None,
            responsavel_preparo=self.responsavel_preparo,
            responsavel_revisao="",
            condicao_armazenamento=self.condicao_armazenamento,
            observacoes=f"Duplicada de {self.codigo}; revisar antes da execução.",
            registro_retroativo=False,
        )

        etapas = {}
        for etapa in self.etapas.order_by("ordem", "pk"):
            nova_etapa = PreparacaoPadraoEtapa.objects.create(
                preparacao=copia,
                ordem=etapa.ordem,
                descricao=etapa.descricao,
                volume_aliquota=etapa.volume_aliquota,
                volume_final=etapa.volume_final,
                unidade_volume=etapa.unidade_volume,
                pipeta=etapa.pipeta,
                recipiente_final=etapa.recipiente_final,
            )
            etapas[etapa.pk] = nova_etapa

        for resultado in self.resultados.order_by("ordem", "pk"):
            PreparacaoPadraoResultado.objects.create(
                preparacao=copia,
                ordem=resultado.ordem,
                valor_alvo=resultado.valor_alvo,
                volume_final=resultado.volume_final,
                unidade_volume=resultado.unidade_volume,
                volume_aliquota_utilizado=None,
                pipeta=resultado.pipeta,
                recipiente_final=resultado.recipiente_final,
            )

        for equipamento in self.equipamentos.order_by("ordem", "pk"):
            PreparacaoPadraoEquipamento.objects.create(
                preparacao=copia,
                etapa=etapas.get(equipamento.etapa_id),
                ordem=equipamento.ordem,
                papel=equipamento.papel,
                padrao=equipamento.padrao,
                valor_utilizado=None,
                coeficiente_sensibilidade_manual=equipamento.coeficiente_sensibilidade_manual,
            )

        for componente in self.componentes.filter(automatico=False).order_by("ordem", "pk"):
            PreparacaoPadraoComponenteIncerteza.objects.create(
                preparacao=copia,
                ordem=componente.ordem,
                nome=componente.nome,
                fonte_padrao=componente.fonte_padrao,
                tipo_valor=componente.tipo_valor,
                valor_informado=componente.valor_informado,
                fator_abrangencia_origem=componente.fator_abrangencia_origem,
                divisor=componente.divisor,
                coeficiente_sensibilidade=componente.coeficiente_sensibilidade,
                graus_liberdade=componente.graus_liberdade,
                incluir=componente.incluir,
                justificativa=componente.justificativa,
            )

        copia.recalcular()
        return copia

    def __str__(self):
        return self.codigo or f"Preparação {self.get_aplicacao_display()}"


class PreparacaoPadraoEtapa(models.Model):
    preparacao = models.ForeignKey(PreparacaoPadrao, on_delete=models.CASCADE, related_name="etapas")
    ordem = models.PositiveSmallIntegerField(default=1)
    descricao = models.CharField(max_length=150, blank=True)
    valor_entrada = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    volume_aliquota = models.DecimalField(max_digits=20, decimal_places=9)
    volume_final = models.DecimalField(max_digits=20, decimal_places=9)
    unidade_volume = models.CharField(max_length=20, default="mL")
    pipeta = models.ForeignKey(
        "calibracao.Padrao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="etapas_diluicao_como_pipeta",
    )
    recipiente_final = models.ForeignKey(
        "calibracao.Padrao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="etapas_diluicao_como_recipiente_final",
    )
    valor_resultante = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Etapa de diluição"
        verbose_name_plural = "Etapas de diluição"
        ordering = ("ordem",)
        constraints = [
            models.UniqueConstraint(fields=("preparacao", "ordem"), name="unique_preparacao_etapa_ordem")
        ]

    def clean(self):
        super().clean()
        if self.volume_aliquota is not None and self.volume_aliquota <= 0:
            raise ValidationError({"volume_aliquota": "O volume deve ser maior que zero."})
        if self.volume_final is not None and self.volume_final <= 0:
            raise ValidationError({"volume_final": "O volume deve ser maior que zero."})
        if (
            self.volume_aliquota is not None
            and self.volume_final is not None
            and self.volume_aliquota > self.volume_final
        ):
            raise ValidationError({"volume_aliquota": "A alíquota não pode exceder o volume final."})

    def calcular(self):
        entrada = _decimal(self.valor_entrada)
        aliquota = _decimal(self.volume_aliquota)
        final = _decimal(self.volume_final)
        self.valor_resultante = _q(entrada * aliquota / final) if entrada is not None and aliquota and final else None
        type(self).objects.filter(pk=self.pk).update(
            valor_entrada=self.valor_entrada,
            valor_resultante=self.valor_resultante,
        )

    def __str__(self):
        return f"{self.preparacao.codigo} - etapa {self.ordem}"


class PreparacaoPadraoResultado(models.Model):
    """Uma linha do gabarito e um padrão preparado independente."""

    preparacao = models.ForeignKey(
        PreparacaoPadrao,
        on_delete=models.CASCADE,
        related_name="resultados",
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    valor_alvo = models.DecimalField(max_digits=20, decimal_places=9)
    volume_final = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        help_text="Capacidade do balão/recipiente. O diluente deve completar até o traço.",
    )
    unidade_volume = models.CharField(max_length=20, default="mL")
    volume_aliquota_planejado = models.DecimalField(
        max_digits=20, decimal_places=9, null=True, blank=True, editable=False
    )
    volume_diluente_aproximado = models.DecimalField(
        max_digits=20, decimal_places=9, null=True, blank=True, editable=False
    )
    volume_aliquota_utilizado = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        null=True,
        blank=True,
        help_text="Valor efetivamente transferido; obrigatório para aprovar.",
    )
    pipeta = models.ForeignKey(
        "calibracao.Padrao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resultados_preparacao_como_pipeta",
    )
    recipiente_final = models.ForeignKey(
        "calibracao.Padrao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resultados_preparacao_como_recipiente_final",
    )
    valor_calculado = models.DecimalField(
        max_digits=20, decimal_places=9, null=True, blank=True, editable=False
    )
    incerteza_padrao_combinada = models.DecimalField(
        max_digits=20, decimal_places=9, null=True, blank=True, editable=False
    )
    graus_liberdade_efetivos = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True, editable=False
    )
    fator_abrangencia = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True, editable=False
    )
    incerteza_expandida = models.DecimalField(
        max_digits=20, decimal_places=9, null=True, blank=True, editable=False
    )
    contribuicao_padrao_origem = models.DecimalField(
        max_digits=20, decimal_places=9, null=True, blank=True, editable=False
    )
    contribuicao_pipeta = models.DecimalField(
        max_digits=20, decimal_places=9, null=True, blank=True, editable=False
    )
    contribuicao_recipiente = models.DecimalField(
        max_digits=20, decimal_places=9, null=True, blank=True, editable=False
    )
    padrao_gerado = models.OneToOneField(
        "calibracao.Padrao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resultado_preparacao_gerador",
        editable=False,
    )

    class Meta:
        verbose_name = "Valor do gabarito de diluição"
        verbose_name_plural = "Gabarito de diluição - valores a preparar"
        ordering = ("ordem", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("preparacao", "ordem"),
                name="unique_preparacao_resultado_ordem",
            )
        ]

    @property
    def codigo_resultado(self):
        codigo = self.preparacao.codigo
        if "/" in codigo:
            base, ano = codigo.rsplit("/", 1)
            return f"{base}-P{self.ordem:02d}/{ano}"
        return f"{codigo}-P{self.ordem:02d}"

    @staticmethod
    def _incerteza_instrumento(padrao):
        if not padrao:
            return Decimal("0"), []
        componentes = []
        if padrao.incerteza is not None and padrao.fator_k:
            componentes.append(
                (abs(_decimal(padrao.incerteza)) / abs(_decimal(padrao.fator_k)), padrao.graus_liberdade)
            )
        if padrao.resolucao is not None:
            componentes.append((abs(_decimal(padrao.resolucao)) / SQRT_12, None))
        with localcontext() as context:
            context.prec = 40
            combinada = sum((valor * valor for valor, _ in componentes), Decimal("0")).sqrt()
        return combinada, componentes

    def calcular(self):
        origem = self.preparacao.padrao_origem
        concentracao_origem = _decimal(origem.valor_nominal)
        alvo = _decimal(self.valor_alvo)
        final = _decimal(self.volume_final)
        utilizado = _decimal(self.volume_aliquota_utilizado)

        planejado = alvo * final / concentracao_origem if alvo is not None and final and concentracao_origem else None
        self.volume_aliquota_planejado = _q(planejado)
        self.volume_diluente_aproximado = _q(final - planejado) if planejado is not None else None
        aliquota_calculo = utilizado if utilizado is not None else planejado
        self.valor_calculado = (
            _q(concentracao_origem * aliquota_calculo / final)
            if concentracao_origem is not None and aliquota_calculo is not None and final
            else None
        )

        contribuicoes = []
        if self.valor_calculado is not None:
            u_origem = (
                abs(_decimal(origem.incerteza)) / abs(_decimal(origem.fator_k))
                if origem.incerteza is not None and origem.fator_k
                else Decimal("0")
            )
            c_origem = abs(aliquota_calculo / final)
            contrib_origem = c_origem * u_origem
            self.contribuicao_padrao_origem = _q(contrib_origem)
            contribuicoes.append((contrib_origem, origem.graus_liberdade))

            u_pipeta, componentes_pipeta = self._incerteza_instrumento(self.pipeta)
            c_pipeta = abs(concentracao_origem / final)
            contrib_pipeta = c_pipeta * u_pipeta
            self.contribuicao_pipeta = _q(contrib_pipeta)
            for valor, graus in componentes_pipeta:
                contribuicoes.append((c_pipeta * valor, graus))

            u_recipiente, componentes_recipiente = self._incerteza_instrumento(self.recipiente_final)
            c_recipiente = abs(concentracao_origem * aliquota_calculo / (final * final))
            contrib_recipiente = c_recipiente * u_recipiente
            self.contribuicao_recipiente = _q(contrib_recipiente)
            for valor, graus in componentes_recipiente:
                contribuicoes.append((c_recipiente * valor, graus))

            with localcontext() as context:
                context.prec = 40
                uc = sum((valor * valor for valor, _ in contribuicoes), Decimal("0")).sqrt()
            denominador = sum(
                ((valor ** 4) / _decimal(graus))
                for valor, graus in contribuicoes
                if valor and _decimal(graus) and _decimal(graus) > 0
            )
            veff = (uc ** 4) / denominador if denominador else None
            k = _fator_abrangencia_95(veff)
            self.incerteza_padrao_combinada = _q(uc)
            self.graus_liberdade_efetivos = veff.quantize(Decimal("0.01")) if veff is not None else None
            self.fator_abrangencia = k
            self.incerteza_expandida = _q(uc * k)
        else:
            self.contribuicao_padrao_origem = None
            self.contribuicao_pipeta = None
            self.contribuicao_recipiente = None
            self.incerteza_padrao_combinada = None
            self.graus_liberdade_efetivos = None
            self.fator_abrangencia = None
            self.incerteza_expandida = None

        if self.pk:
            type(self).objects.filter(pk=self.pk).update(
                volume_aliquota_planejado=self.volume_aliquota_planejado,
                volume_diluente_aproximado=self.volume_diluente_aproximado,
                valor_calculado=self.valor_calculado,
                contribuicao_padrao_origem=self.contribuicao_padrao_origem,
                contribuicao_pipeta=self.contribuicao_pipeta,
                contribuicao_recipiente=self.contribuicao_recipiente,
                incerteza_padrao_combinada=self.incerteza_padrao_combinada,
                graus_liberdade_efetivos=self.graus_liberdade_efetivos,
                fator_abrangencia=self.fator_abrangencia,
                incerteza_expandida=self.incerteza_expandida,
            )

    def pendencias_aprovacao(self, data_preparacao):
        pendencias = []
        prefixo = f"linha {self.ordem} ({self.valor_alvo} {self.preparacao.unidade})"
        if self.volume_aliquota_utilizado is None:
            pendencias.append(f"{prefixo}: volume efetivamente utilizado não informado")
        if not self.pipeta_id:
            pendencias.append(f"{prefixo}: pipeta não informada")
        if not self.recipiente_final_id:
            pendencias.append(f"{prefixo}: balão/recipiente final não informado")
        if self.valor_calculado is None or self.incerteza_expandida is None:
            pendencias.append(f"{prefixo}: valor final ou incerteza não calculado")
        for nome, padrao in (("pipeta", self.pipeta), ("recipiente", self.recipiente_final)):
            if not padrao:
                continue
            if (padrao.unidade or "").strip().casefold() != (self.unidade_volume or "").strip().casefold():
                pendencias.append(f"{prefixo}: unidade do {nome} incompatível")
            if padrao.incerteza is None or not padrao.fator_k:
                pendencias.append(f"{prefixo}: incerteza ou fator k do {nome} incompleto")
            if padrao.vencimento < data_preparacao:
                pendencias.append(f"{prefixo}: {nome} vencido na data da preparação")
        return pendencias

    def clean(self):
        super().clean()
        for field in ("valor_alvo", "volume_final"):
            valor = _decimal(getattr(self, field))
            if valor is not None and valor <= 0:
                raise ValidationError({field: "O valor deve ser maior que zero."})
        if self.volume_aliquota_utilizado is not None and self.volume_aliquota_utilizado <= 0:
            raise ValidationError({"volume_aliquota_utilizado": "O volume deve ser maior que zero."})
        if (
            self.volume_aliquota_utilizado is not None
            and self.volume_final is not None
            and self.volume_aliquota_utilizado > self.volume_final
        ):
            raise ValidationError(
                {"volume_aliquota_utilizado": "A alíquota não pode exceder o volume final."}
            )
        origem = _decimal(self.preparacao.padrao_origem.valor_nominal) if self.preparacao_id else None
        if origem and self.valor_alvo and self.valor_alvo > origem:
            raise ValidationError({"valor_alvo": "Uma diluição não pode exceder o valor do padrão de origem."})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.calcular()

    def __str__(self):
        return f"{self.codigo_resultado} - {self.valor_alvo} {self.preparacao.unidade}"


class PreparacaoPadraoEquipamento(models.Model):
    PAPEL_CHOICES = (
        ("pipeta", "Pipeta/alíquota"),
        ("recipiente_final", "Balão ou recipiente final"),
        ("balanca", "Balança"),
        ("termometro", "Termômetro"),
        ("outro", "Outro equipamento"),
    )
    preparacao = models.ForeignKey(PreparacaoPadrao, on_delete=models.CASCADE, related_name="equipamentos")
    etapa = models.ForeignKey(
        PreparacaoPadraoEtapa,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="equipamentos",
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    papel = models.CharField(max_length=30, choices=PAPEL_CHOICES)
    padrao = models.ForeignKey("calibracao.Padrao", on_delete=models.PROTECT, related_name="usos_em_preparacoes")
    valor_utilizado = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        null=True,
        blank=True,
        help_text="Obrigatório para equipamentos sem relação volumétrica automática.",
    )
    coeficiente_sensibilidade_manual = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        null=True,
        blank=True,
        help_text="Use somente quando o modelo não for pipeta ou recipiente final.",
    )
    resolucao_snapshot = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True, editable=False)
    incerteza_snapshot = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True, editable=False)
    fator_k_snapshot = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, editable=False)
    graus_liberdade_snapshot = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, editable=False)
    validade_snapshot = models.DateField(null=True, blank=True, editable=False)
    unidade_snapshot = models.CharField(max_length=30, blank=True, editable=False)

    class Meta:
        verbose_name = "Padrão ou equipamento utilizado"
        verbose_name_plural = "Padrões e equipamentos utilizados"
        ordering = ("ordem",)

    def clean(self):
        super().clean()
        if self.etapa_id and self.etapa.preparacao_id != self.preparacao_id:
            raise ValidationError({"etapa": "A etapa deve pertencer à mesma preparação."})
        if self.papel in ("pipeta", "recipiente_final") and not self.etapa_id:
            raise ValidationError({"etapa": "Informe a etapa associada ao equipamento volumétrico."})

    def atualizar_snapshot(self):
        if not self.padrao_id:
            return
        self.resolucao_snapshot = self.padrao.resolucao
        self.incerteza_snapshot = self.padrao.incerteza
        self.fator_k_snapshot = self.padrao.fator_k
        self.graus_liberdade_snapshot = self.padrao.graus_liberdade
        self.validade_snapshot = self.padrao.vencimento
        self.unidade_snapshot = self.padrao.unidade
        type(self).objects.filter(pk=self.pk).update(
            resolucao_snapshot=self.resolucao_snapshot,
            incerteza_snapshot=self.incerteza_snapshot,
            fator_k_snapshot=self.fator_k_snapshot,
            graus_liberdade_snapshot=self.graus_liberdade_snapshot,
            validade_snapshot=self.validade_snapshot,
            unidade_snapshot=self.unidade_snapshot,
        )

    def coeficiente_para_resultado(self, resultado_final):
        resultado = _decimal(resultado_final)
        if resultado is None:
            return None
        if self.papel == "pipeta" and self.etapa_id and self.etapa.volume_aliquota:
            return resultado / self.etapa.volume_aliquota
        if self.papel == "recipiente_final" and self.etapa_id and self.etapa.volume_final:
            return -(resultado / self.etapa.volume_final)
        return _decimal(self.coeficiente_sensibilidade_manual)

    def save(self, *args, **kwargs):
        if self.padrao_id:
            self.resolucao_snapshot = self.padrao.resolucao
            self.incerteza_snapshot = self.padrao.incerteza
            self.fator_k_snapshot = self.padrao.fator_k
            self.graus_liberdade_snapshot = self.padrao.graus_liberdade
            self.validade_snapshot = self.padrao.vencimento
            self.unidade_snapshot = self.padrao.unidade
        super().save(*args, **kwargs)


class PreparacaoPadraoComponenteIncerteza(models.Model):
    TIPO_VALOR_CHOICES = (
        ("padrao", "Incerteza-padrão"),
        ("expandida", "Incerteza expandida"),
        ("resolucao", "Resolução - distribuição retangular"),
        ("limite_retangular", "Limite ±a - distribuição retangular"),
        ("limite_triangular", "Limite ±a - distribuição triangular"),
        ("divisor_informado", "Divisor informado"),
    )
    preparacao = models.ForeignKey(PreparacaoPadrao, on_delete=models.CASCADE, related_name="componentes")
    ordem = models.PositiveSmallIntegerField(default=1)
    nome = models.CharField(max_length=255)
    fonte_padrao = models.ForeignKey(
        "calibracao.Padrao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="componentes_preparacao",
    )
    tipo_valor = models.CharField(max_length=30, choices=TIPO_VALOR_CHOICES, default="padrao")
    valor_informado = models.DecimalField(max_digits=20, decimal_places=9)
    fator_abrangencia_origem = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    divisor = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)
    coeficiente_sensibilidade = models.DecimalField(max_digits=20, decimal_places=9, default=1)
    graus_liberdade = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    incluir = models.BooleanField(default=True)
    justificativa = models.CharField(max_length=255, blank=True)
    automatico = models.BooleanField(default=False, editable=False)
    chave_automatica = models.CharField(max_length=100, null=True, blank=True, editable=False)
    incerteza_padrao = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True, editable=False)
    contribuicao = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Componente de incerteza da preparação"
        verbose_name_plural = "Orçamento de incerteza"
        ordering = ("ordem",)
        constraints = [
            models.UniqueConstraint(
                fields=("preparacao", "chave_automatica"),
                name="unique_preparacao_componente_automatica",
            )
        ]

    def clean(self):
        super().clean()
        if not self.incluir and not self.justificativa:
            raise ValidationError({"justificativa": "Justifique a exclusão da componente."})
        if self.tipo_valor == "expandida" and not self.fator_abrangencia_origem:
            raise ValidationError({"fator_abrangencia_origem": "Informe o fator k da incerteza expandida."})
        if self.tipo_valor == "divisor_informado" and not self.divisor:
            raise ValidationError({"divisor": "Informe o divisor adotado."})

    def calcular(self):
        valor = abs(_decimal(self.valor_informado) or Decimal("0"))
        if self.tipo_valor == "expandida":
            divisor = abs(_decimal(self.fator_abrangencia_origem) or Decimal("2"))
        elif self.tipo_valor == "resolucao":
            divisor = SQRT_12
        elif self.tipo_valor == "limite_retangular":
            divisor = SQRT_3
        elif self.tipo_valor == "limite_triangular":
            divisor = SQRT_6
        elif self.tipo_valor == "divisor_informado":
            divisor = abs(_decimal(self.divisor) or Decimal("1"))
        else:
            divisor = Decimal("1")
        if divisor == 0:
            divisor = Decimal("1")
        self.incerteza_padrao = _q(valor / divisor)
        coeficiente = _decimal(self.coeficiente_sensibilidade) or Decimal("0")
        self.contribuicao = _q(abs(coeficiente * self.incerteza_padrao))
        type(self).objects.filter(pk=self.pk).update(
            incerteza_padrao=self.incerteza_padrao,
            contribuicao=self.contribuicao,
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.calcular()
