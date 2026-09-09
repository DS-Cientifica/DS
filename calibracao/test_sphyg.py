from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from clientes.models import Cliente

from .models import Padrao
from .services.sphyg_calculation import (
    conformity_result,
    correction_from_error,
    hysteresis,
    leakage_rate,
    measurement_error,
)
from .sphyg_models import (
    CalibracaoEsfigmomanometro,
    EsfigmomanometroEnsaioVazamento,
    EsfigmomanometroIncertezaPonto,
    EsfigmomanometroPadraoUtilizado,
    EsfigmomanometroPonto,
)


class SphygCalculationTests(TestCase):
    def test_vim_equations_leakage_and_guard_band(self):
        error = measurement_error(Decimal("101"), Decimal("100"))
        self.assertEqual(error, Decimal("1"))
        self.assertEqual(correction_from_error(error), Decimal("-1"))
        self.assertEqual(hysteresis(Decimal("101"), Decimal("99")), Decimal("2"))
        self.assertEqual(leakage_rate(Decimal("200"), Decimal("185"), Decimal("5")), Decimal("3"))
        self.assertEqual(
            conformity_result((Decimal("2.5"),), Decimal("3"), Decimal("0.6"), "banda_guarda"),
            "reprovado",
        )


class SphygWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            razao_social="Clínica Teste LTDA", nome_empresa="Clínica Teste LTDA",
            cnpj="44.345.678/0001-99", endereco="Rua Clínica", numero="10",
            cidade="Jundiaí", uf="SP",
        )
        cls.instrumento = cls.cliente.instrumentos.create(
            codigo="ESF-001", descricao="Esfigmomanômetro aneroide", tag="PA-01",
            marca="Marca", modelo="A100", numero_serie="12345",
        )
        cls.padrao = Padrao.objects.create(
            codigo="PAD-PRE-01", descricao="Manômetro padrão digital",
            numero_certificado="RBC-123/26", laboratorio_emitente="Laboratório RBC",
            data_calibracao=date(2026, 1, 10), vencimento=date(2027, 1, 10),
            resolucao=Decimal("0.1"), incerteza=Decimal("0.2"), fator_k=Decimal("2"),
            unidade="mmHg",
        )

    def create_calibration(self, **overrides):
        data = {
            "instrumento": self.instrumento, "cliente": self.cliente,
            "tecnologia": "aneroide", "data_calibracao": date(2026, 8, 7),
            "unidade": "mmHg", "resolucao": Decimal("1"),
            "contexto_criterio": "inicial_apos_reparo",
            "regra_decisao": "banda_guarda",
            "criterio_origem": "Inmetro", "criterio_referencia": "Portaria 341/2021",
        }
        data.update(overrides)
        return CalibracaoEsfigmomanometro.objects.create(**data)

    def test_regulatory_contexts_are_configurable(self):
        calibration = self.create_calibration()
        self.assertEqual(calibration.tolerancia_resolvida, Decimal("3"))
        calibration.contexto_criterio = "periodica"
        self.assertEqual(calibration.tolerancia_resolvida, Decimal("4"))
        calibration.unidade = "kPa"
        self.assertEqual(calibration.tolerancia_resolvida, Decimal("0.5"))

    def test_presentation_follows_instrument_resolution_without_truncating_calculation(self):
        calibration = self.create_calibration(resolucao=Decimal("1"))
        self.assertEqual(calibration.formatar_por_resolucao(Decimal("101.333333")), "101")
        calibration.resolucao = Decimal("0.1")
        self.assertEqual(calibration.formatar_por_resolucao(Decimal("101.333333")), "101,3")
        calibration.resolucao = Decimal("0.01")
        self.assertEqual(calibration.formatar_por_resolucao(Decimal("101.333333")), "101,33")

    def test_standard_snapshot_point_uncertainty_and_leakage(self):
        calibration = self.create_calibration()
        used = EsfigmomanometroPadraoUtilizado.objects.create(
            calibracao=calibration, ordem=1, padrao=self.padrao
        )
        self.assertEqual(used.numero_certificado, "RBC-123/26")
        self.assertEqual(used.situacao_na_data, "valido")
        point = EsfigmomanometroPonto.objects.create(
            calibracao=calibration, ordem=1, pressao_referencia=Decimal("100"),
            crescente_1=Decimal("101"), crescente_2=Decimal("102"), crescente_3=Decimal("101"),
            decrescente_1=Decimal("99"), decrescente_2=Decimal("100"), decrescente_3=Decimal("100"),
        )
        self.assertEqual(point.media_crescente, Decimal("101.333333"))
        self.assertEqual(point.erro_crescente, Decimal("1.333333"))
        self.assertEqual(point.correcao_crescente, Decimal("-1.333333"))
        self.assertEqual(point.histerese, Decimal("1.666666"))
        uncertainty = EsfigmomanometroIncertezaPonto.objects.create(
            calibracao=calibration, ordem=1, resolucao_instrumento=Decimal("1"),
            limite_deriva_padrao=Decimal("0.3"),
        )
        self.assertIsNotNone(uncertainty.incerteza_expandida)
        self.assertIsNone(uncertainty.u_resolucao_padrao)
        self.assertIsNone(uncertainty.u_deriva_padrao)
        self.assertEqual(
            uncertainty.componentes_incluidos,
            "repetitividade, resolução do instrumento, calibração do padrão",
        )
        leakage = EsfigmomanometroEnsaioVazamento.objects.create(
            calibracao=calibration, ordem=1, pressao_inicial=Decimal("200"),
            pressao_final=Decimal("185"), duracao_minutos=Decimal("5"),
        )
        self.assertEqual(leakage.taxa_vazamento, Decimal("3.000000"))
        self.assertEqual(leakage.limite_resolvido, Decimal("4"))
        self.assertEqual(leakage.resultado, "aprovado")

    def test_optional_uncertainty_components_require_evidence(self):
        calibration = self.create_calibration()
        uncertainty = EsfigmomanometroIncertezaPonto(
            calibracao=calibration, ordem=1, incluir_deriva_padrao=True,
            u_outros=Decimal("0.1"),
        )
        with self.assertRaises(ValidationError) as context:
            uncertainty.full_clean()
        self.assertIn("limite_deriva_padrao", context.exception.message_dict)
        self.assertIn("outros_descricao", context.exception.message_dict)

    def test_optional_components_are_only_summed_when_enabled(self):
        calibration = self.create_calibration()
        EsfigmomanometroPadraoUtilizado.objects.create(
            calibracao=calibration, ordem=1, padrao=self.padrao
        )
        EsfigmomanometroPonto.objects.create(
            calibracao=calibration, ordem=1, pressao_referencia=Decimal("100"),
            crescente_1=Decimal("100"), crescente_2=Decimal("100"), crescente_3=Decimal("100"),
            decrescente_1=Decimal("100"), decrescente_2=Decimal("100"), decrescente_3=Decimal("100"),
        )
        uncertainty = EsfigmomanometroIncertezaPonto.objects.create(
            calibracao=calibration, ordem=1, resolucao_instrumento=Decimal("1"),
            resolucao_padrao=Decimal("0.1"), limite_deriva_padrao=Decimal("0.3"),
        )
        base_uncertainty = uncertainty.incerteza_expandida
        uncertainty.incluir_resolucao_padrao = True
        uncertainty.incluir_deriva_padrao = True
        uncertainty.save()
        self.assertIsNotNone(uncertainty.u_resolucao_padrao)
        self.assertIsNotNone(uncertainty.u_deriva_padrao)
        self.assertGreater(uncertainty.incerteza_expandida, base_uncertainty)

    def test_digital_requires_test_mode_and_immediate_interruption(self):
        calibration = self.create_calibration(tecnologia="digital_automatico")
        pending = calibration.pendencias_emissao()
        self.assertIn("Modo de manômetro/conexão de ensaio do digital", pending)
        self.assertIn("Ensaio de interrupção imediata", pending)

    def test_authenticated_certificate_renders_with_legal_warning(self):
        calibration = self.create_calibration()
        user = User.objects.create_superuser("sphyg-admin", "sphyg@example.com", "pass123")
        client = Client()
        client.force_login(user)
        response = client.get(reverse("pdf_calibracao_esfigmomanometro", args=(calibration.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, calibration.numero_certificado)
        self.assertContains(response, "Não substitui aprovação de modelo")

    def test_certificate_result_uses_resolution_decimal_places(self):
        calibration = self.create_calibration(resolucao=Decimal("0.1"))
        point = EsfigmomanometroPonto.objects.create(
            calibracao=calibration, ordem=1, pressao_referencia=Decimal("100"),
            crescente_1=Decimal("101"), crescente_2=Decimal("102"), crescente_3=Decimal("101"),
            decrescente_1=Decimal("99"), decrescente_2=Decimal("100"), decrescente_3=Decimal("100"),
        )
        self.assertEqual(point.media_crescente, Decimal("101.333333"))
        user = User.objects.create_superuser("sphyg-format", "format@example.com", "pass123")
        client = Client(); client.force_login(user)
        response = client.get(reverse("pdf_calibracao_esfigmomanometro", args=(calibration.pk,)))
        self.assertContains(response, "101,3")
        self.assertNotContains(response, "101,333333")

    def test_current_expired_status_does_not_rewrite_historical_validity(self):
        calibration = self.create_calibration()
        self.padrao.status = "vencido"
        self.padrao.save(update_fields=("status",))
        used = EsfigmomanometroPadraoUtilizado.objects.create(
            calibracao=calibration, ordem=1, padrao=self.padrao
        )
        self.assertEqual(used.situacao_na_data, "valido")

    def test_certificate_requires_model_view_permission(self):
        calibration = self.create_calibration()
        user = User.objects.create_user("sphyg-no-access", password="pass123")
        client = Client()
        client.force_login(user)
        response = client.get(
            reverse("pdf_calibracao_esfigmomanometro", args=(calibration.pk,))
        )
        self.assertEqual(response.status_code, 403)
