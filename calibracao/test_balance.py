from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from clientes.models import Cliente

from .balance_models import (
    BalancaExcentricidadePonto,
    BalancaIncertezaPonto,
    BalancaPadraoUtilizado,
    BalancaPontoIndicacao,
    BalancaRepetibilidade,
    CalibracaoBalanca,
)
from .models import Padrao
from .services.balance_calculation import (
    correction_from_error,
    decimal_places_from_resolution,
    format_by_resolution,
    indication_error,
    sample_standard_deviation,
    select_significant_components,
    standard_uncertainty_from_resolution,
)


class BalanceCalculationTests(TestCase):
    def test_core_metrological_equations(self):
        error = indication_error(Decimal("100.003"), Decimal("100.001"))
        self.assertEqual(error, Decimal("0.002"))
        self.assertEqual(correction_from_error(error), Decimal("-0.002"))
        self.assertEqual(sample_standard_deviation([Decimal("1"), Decimal("2"), Decimal("3")]), Decimal("1"))
        self.assertAlmostEqual(
            float(standard_uncertainty_from_resolution(Decimal("0.001"))),
            0.000288675,
            places=9,
        )

    def test_significance_filter_limits_cumulative_discarded_variance(self):
        result = select_significant_components({
            "dominant": Decimal("1"),
            "small_a": Decimal("0.05"),
            "small_b": Decimal("0.08"),
            "relevant": Decimal("0.10"),
        }, Decimal("1"))
        self.assertEqual(set(result["discarded"]), {"small_a", "small_b"})
        self.assertEqual(set(result["included"]), {"dominant", "relevant"})
        self.assertLessEqual(result["discarded_variance_percent"], Decimal("1"))
        self.assertGreater(result["complete_combined"], result["adopted_combined"])

    def test_result_format_follows_resolution_decimal_places(self):
        self.assertEqual(decimal_places_from_resolution(Decimal("0.001")), 3)
        self.assertEqual(decimal_places_from_resolution(Decimal("0.01")), 2)
        self.assertEqual(decimal_places_from_resolution(Decimal("1")), 0)
        self.assertEqual(format_by_resolution(Decimal("12.3"), Decimal("0.001")), "12,300")
        self.assertEqual(format_by_resolution(Decimal("12.3456"), Decimal("0.01")), "12,35")


class CalibracaoBalancaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            razao_social="Cliente Massa LTDA",
            nome_empresa="Cliente Massa LTDA",
            cnpj="22.345.678/0001-99",
            endereco="Rua da Massa",
            numero="10",
            cidade="Jundiai",
            uf="SP",
        )
        cls.instrumento = cls.cliente.instrumentos.create(
            codigo="BAL-001",
            descricao="Balança eletrônica",
            marca="Marca",
            modelo="Modelo",
        )
        cls.padrao = Padrao.objects.create(
            codigo="PESO-100G",
            descricao="Peso padrão 100 g",
            numero_certificado="MASSA-001",
            laboratorio_emitente="Laboratório RBC",
            data_calibracao=date(2026, 1, 2),
            vencimento=date(2027, 1, 2),
            incerteza=Decimal("0.002"),
            fator_k=Decimal("2"),
            unidade="g",
            valor_nominal=Decimal("100"),
        )

    def create_calibration(self, **overrides):
        data = {
            "instrumento": self.instrumento,
            "cliente": self.cliente,
            "data_calibracao": date(2026, 8, 7),
            "capacidade_maxima": Decimal("220"),
            "capacidade_minima": Decimal("0.01"),
            "divisao_escala": Decimal("0.001"),
            "unidade": "g",
        }
        data.update(overrides)
        return CalibracaoBalanca.objects.create(**data)

    def test_standard_snapshot_preserves_traceability(self):
        calibration = self.create_calibration()
        used = BalancaPadraoUtilizado.objects.create(
            calibracao=calibration,
            ordem=1,
            padrao=self.padrao,
            correcao=Decimal("0.001"),
        )
        self.assertEqual(used.codigo, "PESO-100G")
        self.assertEqual(used.numero_certificado, "MASSA-001")
        self.assertEqual(used.valor_nominal, Decimal("100"))
        self.assertEqual(used.massa_convencional, Decimal("100.001"))
        self.assertEqual(used.validade_status, "Válido")

    def test_indication_point_calculates_error_and_correction(self):
        calibration = self.create_calibration()
        point = BalancaPontoIndicacao.objects.create(
            calibracao=calibration,
            ordem=1,
            carga_nominal=Decimal("100"),
            correcao_padroes=Decimal("0.001"),
            indicacao_1=Decimal("100.003"),
        )
        point.refresh_from_db()
        self.assertEqual(point.massa_referencia, Decimal("100.001000000"))
        self.assertEqual(point.erro, Decimal("0.002000000"))
        self.assertEqual(point.correcao, Decimal("-0.002000000"))
        self.assertEqual(point.resultado, "")
        self.assertEqual(point.massa_referencia_formatada, "100,001")
        self.assertEqual(point.erro_formatado, "0,002")

    def test_repeatability_eccentricity_and_uncertainty_budget(self):
        calibration = self.create_calibration()
        repeatability = BalancaRepetibilidade.objects.create(
            calibracao=calibration,
            carga_teste=Decimal("100"),
            leitura_1=Decimal("100.000"),
            leitura_2=Decimal("100.001"),
            leitura_3=Decimal("99.999"),
            leitura_4=Decimal("100.000"),
            leitura_5=Decimal("100.000"),
        )
        center = BalancaExcentricidadePonto.objects.create(
            calibracao=calibration,
            ordem=1,
            posicao="centro",
            carga_teste=Decimal("100"),
            indicacao=Decimal("100.000"),
        )
        off_center = BalancaExcentricidadePonto.objects.create(
            calibracao=calibration,
            ordem=2,
            posicao="frente_esquerda",
            carga_teste=Decimal("100"),
            indicacao=Decimal("100.002"),
        )
        point = BalancaPontoIndicacao.objects.create(
            calibracao=calibration,
            ordem=1,
            carga_nominal=Decimal("100"),
            indicacao_1=Decimal("100.001"),
        )
        used = BalancaPadraoUtilizado.objects.create(
            calibracao=calibration,
            ordem=1,
            padrao=self.padrao,
            limite_deriva=Decimal("0.003"),
        )
        point.padroes_aplicados.add(used)
        uncertainty = BalancaIncertezaPonto.objects.create(
            ponto=point,
            repetibilidade=repeatability,
            fator_k=Decimal("2"),
        )
        center.refresh_from_db()
        off_center.refresh_from_db()
        uncertainty.refresh_from_db()
        self.assertEqual(center.diferenca_centro, Decimal("0E-9"))
        self.assertEqual(off_center.diferenca_centro, Decimal("0.002000000"))
        self.assertIsNotNone(uncertainty.u_repetibilidade)
        self.assertIsNotNone(uncertainty.u_excentricidade)
        self.assertEqual(uncertainty.u_certificados_pesos, Decimal("0.001000000"))
        self.assertIsNotNone(uncertainty.incerteza_expandida)
        self.assertIsNotNone(uncertainty.incerteza_padrao_combinada_completa)
        self.assertLessEqual(
            uncertainty.percentual_variancia_desconsiderada,
            uncertainty.limite_variancia_desconsiderada_percentual,
        )
        self.assertTrue(uncertainty.componentes_significativos)

    def test_admin_and_certificate_pages_are_available(self):
        calibration = self.create_calibration()
        user = User.objects.create_superuser("balance-admin", "admin@example.com", "secret")
        client = Client()
        client.force_login(user)
        list_response = client.get(reverse("admin:calibracao_calibracaobalanca_changelist"))
        certificate_response = client.get(
            reverse("admin:calibracao_calibracaobalanca_certificado", args=[calibration.pk])
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(certificate_response.status_code, 200)
        self.assertContains(certificate_response, "RASCUNHO")
        self.assertContains(certificate_response, "220,000")

    def test_metrology_group_receives_balance_permissions(self):
        group = Group.objects.get(name="Metrologia")
        codenames = set(group.permissions.values_list("codename", flat=True))
        self.assertIn("view_calibracaobalanca", codenames)
        self.assertIn("add_calibracaobalanca", codenames)
        self.assertIn("change_balancaincertezaponto", codenames)
        self.assertNotIn("delete_calibracaobalanca", codenames)

    def test_certificate_pending_items_cover_required_tests(self):
        calibration = self.create_calibration()
        pending = calibration.certificate_pending_items()
        self.assertIn("padrões não informados", pending)
        self.assertIn("ensaio de indicação não informado", pending)
        self.assertIn("ensaio de repetibilidade não informado", pending)
        self.assertIn("ensaio de excentricidade não informado", pending)

    def test_default_groups_receive_controlled_document_permissions(self):
        metrology = Group.objects.get(name="Metrologia")
        metrology_codenames = set(
            metrology.permissions.values_list("codename", flat=True)
        )
        administrator = Group.objects.get(name="Administrador")
        administrator_codenames = set(
            administrator.permissions.values_list("codename", flat=True)
        )
        self.assertIn("add_certificadocalibracao", metrology_codenames)
        self.assertIn("view_documentoarquivo", metrology_codenames)
        self.assertIn("change_certificadocalibracao", administrator_codenames)
        self.assertIn("view_documentoarquivo", administrator_codenames)

    def test_emitted_calibration_is_read_only_in_admin(self):
        calibration = self.create_calibration()
        point = BalancaPontoIndicacao.objects.create(
            calibracao=calibration,
            ordem=1,
            carga_nominal=Decimal("100"),
            indicacao_1=Decimal("100"),
        )
        uncertainty = BalancaIncertezaPonto.objects.create(ponto=point)
        calibration.status = "emitida"
        calibration.save(update_fields=("status", "updated_at"))
        user = User.objects.create_superuser(
            "balance-issued-admin", "issued@example.com", "secret"
        )
        client = Client()
        client.force_login(user)
        url = reverse(
            "admin:calibracao_calibracaobalanca_change", args=[calibration.pk]
        )
        self.assertEqual(client.get(url).status_code, 200)
        self.assertEqual(client.post(url, {}).status_code, 403)
        uncertainty_url = reverse(
            "admin:calibracao_balancaincertezaponto_change", args=[uncertainty.pk]
        )
        self.assertEqual(client.get(uncertainty_url).status_code, 200)
        self.assertEqual(client.post(uncertainty_url, {}).status_code, 403)
