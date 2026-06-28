from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from clientes.models import Cliente

from .models import Padrao
from .ph_models import (
    CalibracaoPH,
    CalibracaoPHPadraoUtilizado,
    CalibracaoPHIncertezaPonto,
    CalibracaoPHPonto,
)
from .services.ph_meter_calculation import (
    average as ph_average,
    calcular_incerteza as ph_calcular_incerteza,
    error as ph_error,
    stdev as ph_stdev,
    teorico_ph_from_mv as ph_teorico_ph_from_mv,
)


class PHMeterCalculationTests(TestCase):
    def test_service_helpers(self):
        self.assertEqual(ph_average([1, 2, 3]), Decimal("2"))
        self.assertEqual(ph_error(Decimal("5"), Decimal("4")), Decimal("1"))
        self.assertEqual(ph_teorico_ph_from_mv(0, 25), Decimal("7"))
        self.assertAlmostEqual(float(ph_stdev([1, 2, 3])), 1.0, places=6)

        resultado = ph_calcular_incerteza([0.01, 0.02, 0.03], fator_k=2)
        self.assertIsNotNone(resultado["incerteza_padrao_combinada"])
        self.assertAlmostEqual(float(resultado["incerteza_padrao_combinada"]), 0.037416, places=5)
        self.assertAlmostEqual(float(resultado["incerteza_expandida"]), 0.074833, places=5)


class CalibracaoPHTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            razao_social="Cliente Teste LTDA",
            nome_empresa="Cliente Teste LTDA",
            cnpj="12.345.678/0001-99",
            endereco="Rua A",
            numero="100",
            bairro="Centro",
            cidade="Jundiai",
            uf="SP",
            email="teste@cliente.com",
        )
        cls.instrumento = cls.cliente.instrumentos.create(
            codigo="PH-001",
            descricao="Medidor de pH",
            marca="Marca X",
            modelo="Modelo Y",
        )
        cls.padrao = Padrao.objects.create(
            codigo="MRC-PH-001",
            descricao="Buffer pH 7,00",
            numero_certificado="CERT-001",
            laboratorio_emitente="Lab Teste",
            data_calibracao=date(2026, 1, 1),
            vencimento=date(2026, 12, 31),
            resolucao=Decimal("0.01"),
            incerteza=Decimal("0.02"),
            fator_k=Decimal("2"),
            graus_liberdade=Decimal("50"),
            unidade="pH",
            valor_nominal=Decimal("7.00"),
        )

    def _criar_calibracao(self):
        return CalibracaoPH.objects.create(
            instrumento=self.instrumento,
            cliente=self.cliente,
            data_calibracao=date(2026, 6, 15),
            tipo_calibracao="calibracao_ph_completa",
            tipo_indicacao="digital",
        )

    def test_snapshot_de_padrao_utilizado(self):
        calibracao = self._criar_calibracao()
        padrao_utilizado = CalibracaoPHPadraoUtilizado.objects.create(
            calibracao=calibracao,
            tipo="mrc_neutra",
            ordem=1,
            padrao=self.padrao,
        )

        self.assertEqual(padrao_utilizado.codigo, self.padrao.codigo)
        self.assertEqual(padrao_utilizado.numero_certificado, self.padrao.numero_certificado)
        self.assertEqual(padrao_utilizado.unidade, self.padrao.unidade)
        self.assertEqual(padrao_utilizado.valor_nominal, self.padrao.valor_nominal)

    def test_ponto_calcula_media_erro_e_status_final(self):
        calibracao = self._criar_calibracao()

        ponto_acido = CalibracaoPHPonto.objects.create(
            calibracao=calibracao,
            tipo="quimica_acida",
            ordem=1,
            valor_padrao_ph=Decimal("4.00"),
            leitura_1=Decimal("10.00"),
            leitura_2=Decimal("10.00"),
            leitura_3=Decimal("10.00"),
            criterio="<= 10",
        )
        ponto_basico = CalibracaoPHPonto.objects.create(
            calibracao=calibracao,
            tipo="quimica_basica",
            ordem=2,
            valor_padrao_ph=Decimal("7.00"),
            leitura_1=Decimal("4.00"),
            leitura_2=Decimal("4.00"),
            leitura_3=Decimal("4.00"),
            criterio="<= 10",
        )

        calibracao.refresh_from_db()

        self.assertEqual(ponto_acido.media, Decimal("10.000000"))
        self.assertEqual(ponto_acido.erro, Decimal("6.000000"))
        self.assertEqual(ponto_acido.resultado, "OK")
        self.assertEqual(ponto_basico.erro, Decimal("-3.000000"))
        self.assertEqual(calibracao.resultado_final_status, "conforme")
        self.assertIn("slope real", calibracao.resultado_final)
        self.assertIn("pH0", calibracao.resultado_final)

    def test_ponto_eletrico_usa_referencia_em_mv(self):
        calibracao = self._criar_calibracao()

        ponto = CalibracaoPHPonto.objects.create(
            calibracao=calibracao,
            tipo="eletrica_mv",
            ordem=1,
            valor_padrao_mv=Decimal("12.50"),
            leitura_1=Decimal("0.00"),
            leitura_2=Decimal("0.00"),
            leitura_3=Decimal("0.00"),
        )

        self.assertIsNone(ponto.valor_padrao_ph)
        self.assertEqual(ponto.media, Decimal("0.000000"))
        self.assertEqual(ponto.erro, Decimal("-12.500000"))

    def test_incerteza_calcula_combinada_e_ema(self):
        calibracao = self._criar_calibracao()
        ponto = CalibracaoPHPonto.objects.create(
            calibracao=calibracao,
            tipo="quimica_acida",
            ordem=1,
            valor_padrao_ph=Decimal("4.00"),
            leitura_1=Decimal("10.00"),
            leitura_2=Decimal("10.00"),
            leitura_3=Decimal("10.00"),
            criterio="<= 10",
        )

        incerteza = CalibracaoPHIncertezaPonto.objects.create(
            calibracao=calibracao,
            ordem=1,
            repetibilidade=Decimal("0.010000"),
            resolucao_instrumento=Decimal("0.020000"),
            resolucao_padrao=Decimal("0.030000"),
            incerteza_padrao=Decimal("0.040000"),
            incerteza_curva=Decimal("0.050000"),
            incerteza_temperatura=Decimal("0.010000"),
            incerteza_constante_faraday=Decimal("0.010000"),
            incerteza_constante_gas=Decimal("0.010000"),
            incerteza_phx=Decimal("0.010000"),
        )

        ponto.refresh_from_db()

        self.assertIsNotNone(incerteza.incerteza_padrao_combinada)
        self.assertIsNotNone(incerteza.incerteza_expandida)
        self.assertIsNotNone(ponto.ema)
        self.assertGreater(ponto.ema, abs(ponto.erro))

    def test_slope_teorico_e_contexto_pdf(self):
        calibracao = self._criar_calibracao()
        calibracao.temperatura_referencia = Decimal("25.00")
        calibracao.slope_indicado = Decimal("58.90")
        calibracao.save(update_fields=["temperatura_referencia", "slope_indicado"])

        self.assertAlmostEqual(float(calibracao.slope_teorico()), 59.16, places=2)

    def test_pdf_view_responde_para_usuario_logado(self):
        calibracao = self._criar_calibracao()
        CalibracaoPHPonto.objects.create(
            calibracao=calibracao,
            tipo="quimica_acida",
            ordem=1,
            valor_padrao_ph=Decimal("4.00"),
            leitura_1=Decimal("10.00"),
            leitura_2=Decimal("10.00"),
            leitura_3=Decimal("10.00"),
            criterio="<= 10",
        )
        CalibracaoPHPonto.objects.create(
            calibracao=calibracao,
            tipo="quimica_basica",
            ordem=2,
            valor_padrao_ph=Decimal("7.00"),
            leitura_1=Decimal("4.00"),
            leitura_2=Decimal("4.00"),
            leitura_3=Decimal("4.00"),
            criterio="<= 10",
        )

        user = User.objects.create_user(username="admin-ph", password="senha123")
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])

        client = Client()
        self.assertTrue(client.login(username="admin-ph", password="senha123"))

        response = client.get(reverse("admin:calibracao_calibracaoph_pdf", args=[calibracao.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Certificado de Calibracao de Medidor de pH")
