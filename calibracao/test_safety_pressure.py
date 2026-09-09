from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from clientes.models import Cliente

from .models import Padrao
from .safety_models import (
    CalibracaoDispositivoSegurancaPressao,
    DispositivoSegurancaIncertezaPonto,
    DispositivoSegurancaPadraoUtilizado,
    DispositivoSegurancaPonto,
)
from .services.safety_pressure_calculation import (
    conformity_result,
    correction,
    error,
    sample_standard_deviation,
    standard_uncertainty_from_resolution,
)


class SafetyPressureCalculationTests(TestCase):
    def test_core_equations(self):
        measurement_error = error(Decimal("4.20"), Decimal("4.08"))
        self.assertEqual(measurement_error, Decimal("0.12"))
        self.assertEqual(correction(measurement_error), Decimal("-0.12"))
        self.assertEqual(
            sample_standard_deviation([Decimal("4.1"), Decimal("4.2"), Decimal("4.3")]),
            Decimal("0.1"),
        )
        self.assertAlmostEqual(
            float(standard_uncertainty_from_resolution(Decimal("0.01"))), 0.002886751, places=9
        )
        self.assertEqual(
            conformity_result(Decimal("0.08"), Decimal("0.10"), Decimal("0.03"), "aceitacao_simples"),
            "aprovado",
        )
        self.assertEqual(
            conformity_result(Decimal("0.08"), Decimal("0.10"), Decimal("0.03"), "banda_guarda"),
            "reprovado",
        )


class SafetyPressureWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            razao_social="Cliente Segurança LTDA",
            nome_empresa="Cliente Segurança LTDA",
            cnpj="33.345.678/0001-88",
            endereco="Rua do Processo",
            numero="20",
            cidade="Jundiaí",
            uf="SP",
        )
        cls.instrumento = cls.cliente.instrumentos.create(
            codigo="PSV-4102-01",
            descricao="Válvula de segurança e alívio",
            tag="BBGB-183",
            marca="Caleffi",
            modelo="WN20402",
        )
        cls.padrao = Padrao.objects.create(
            codigo="DSP-010",
            descricao="Manômetro digital",
            numero_certificado="455883/26",
            laboratorio_emitente="Laboratório RBC",
            data_calibracao=date(2026, 3, 2),
            vencimento=date(2027, 3, 2),
            resolucao=Decimal("0.01"),
            incerteza=Decimal("0.02"),
            fator_k=Decimal("2"),
            unidade="kgf/cm2",
        )

    def create_calibration(self, **overrides):
        data = {
            "instrumento": self.instrumento,
            "cliente": self.cliente,
            "tipo_dispositivo": "valvula_seguranca_alivio",
            "tipo_documento": "ensaio_ajuste",
            "data_calibracao": date(2026, 4, 17),
            "unidade": "kgf/cm2",
            "criterio_tipo": "absoluto",
            "criterio_valor": Decimal("0.15"),
            "regra_decisao": "banda_guarda",
        }
        data.update(overrides)
        return CalibracaoDispositivoSegurancaPressao.objects.create(**data)

    def test_standard_snapshot_and_validity_are_preserved(self):
        calibration = self.create_calibration()
        used = DispositivoSegurancaPadraoUtilizado.objects.create(
            calibracao=calibration, ordem=1, padrao=self.padrao
        )
        self.assertEqual(used.codigo, "DSP-010")
        self.assertEqual(used.numero_certificado, "455883/26")
        self.assertEqual(used.situacao_na_data, "valido")
        self.padrao.numero_certificado = "ALTERADO"
        self.padrao.save(update_fields=("numero_certificado",))
        used.refresh_from_db()
        self.assertEqual(used.numero_certificado, "455883/26")

    def test_emission_flags_standard_unit_mismatch(self):
        calibration = self.create_calibration(unidade="bar")
        DispositivoSegurancaPadraoUtilizado.objects.create(
            calibracao=calibration, ordem=1, padrao=self.padrao
        )
        self.assertTrue(any("Unidade do padrão" in item for item in calibration.pendencias_emissao()))

    def test_point_calculates_vim_terms_and_guard_band_result(self):
        calibration = self.create_calibration()
        DispositivoSegurancaPadraoUtilizado.objects.create(
            calibracao=calibration, ordem=1, padrao=self.padrao
        )
        point = DispositivoSegurancaPonto.objects.create(
            calibracao=calibration,
            ordem=1,
            condicao="deixado",
            pressao_referencia=Decimal("4.08"),
            atuacao_1=Decimal("4.18"),
            atuacao_2=Decimal("4.20"),
            atuacao_3=Decimal("4.22"),
            rearme_1=Decimal("3.90"),
            rearme_2=Decimal("3.91"),
            rearme_3=Decimal("3.89"),
        )
        self.assertEqual(point.media_atuacao, Decimal("4.200000000"))
        self.assertEqual(point.erro, Decimal("0.120000000"))
        self.assertEqual(point.correcao, Decimal("-0.120000000"))
        self.assertEqual(point.repetitividade, Decimal("0.040000000"))
        self.assertEqual(point.histerese, Decimal("0.300000000"))

        uncertainty = DispositivoSegurancaIncertezaPonto.objects.create(
            calibracao=calibration,
            ordem=1,
            condicao="deixado",
            resolucao_dispositivo=Decimal("0.01"),
        )
        point.refresh_from_db()
        self.assertIsNotNone(uncertainty.incerteza_expandida)
        self.assertEqual(point.resultado, "reprovado")
        calibration.refresh_from_db()
        self.assertEqual(calibration.resultado_final, "nao_conforme")

    def test_certificate_lists_pending_items_and_renders_for_authenticated_user(self):
        calibration = self.create_calibration()
        self.assertIn("Fluido de teste", calibration.pendencias_emissao())
        user = User.objects.create_superuser("safety-admin", "safety@example.com", "pass123")
        client = Client()
        client.force_login(user)
        response = client.get(reverse("pdf_calibracao_dispositivo_seguranca", args=(calibration.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, calibration.numero_certificado)
        self.assertContains(response, "Documento não liberado para emissão")

    def test_current_expired_status_does_not_rewrite_historical_validity(self):
        calibration = self.create_calibration()
        self.padrao.status = "vencido"
        self.padrao.save(update_fields=("status",))
        used = DispositivoSegurancaPadraoUtilizado.objects.create(
            calibracao=calibration, ordem=1, padrao=self.padrao
        )
        self.assertEqual(used.situacao_na_data, "valido")

    def test_certificate_requires_model_view_permission(self):
        calibration = self.create_calibration()
        user = User.objects.create_user("safety-no-access", password="pass123")
        client = Client()
        client.force_login(user)
        response = client.get(
            reverse("pdf_calibracao_dispositivo_seguranca", args=(calibration.pk,))
        )
        self.assertEqual(response.status_code, 403)
