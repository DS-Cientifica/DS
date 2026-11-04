import re
from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from clientes.models import Cliente

from .models import (
    Calibracao,
    CalibracaoTurbidez,
    Instrumento,
    HistoricoNumeroCertificado,
    NumeroCertificadoEmitido,
)


class NumeroCertificadoGlobalTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            razao_social="Cliente Certificados Ltda",
            nome_empresa="Cliente Certificados",
            cnpj="72.345.678/0001-10",
        )
        self.instrumento = Instrumento.objects.create(
            codigo="CERT-INST-001",
            descricao="Instrumento de teste",
            cliente=self.cliente,
        )

    def assert_formato_novo(self, numero):
        self.assertRegex(numero, r"^[A-Z0-9]{6}$")
        self.assertEqual(len(re.findall(r"[A-Z]", numero)), 3)
        self.assertEqual(len(re.findall(r"\d", numero)), 3)
        self.assertFalse(numero.endswith("DS"))

    def test_modalidades_diferentes_usam_formato_e_reserva_globais(self):
        geral = Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 8, 11),
        )
        turbidez = CalibracaoTurbidez.objects.create(
            instrumento=self.instrumento,
            cliente=self.cliente,
            data_calibracao=date(2026, 8, 11),
        )

        self.assert_formato_novo(geral.certificado_numero)
        self.assert_formato_novo(turbidez.numero_certificado)
        self.assertNotEqual(geral.certificado_numero, turbidez.numero_certificado)
        self.assertEqual(NumeroCertificadoEmitido.objects.count(), 2)

    def test_numero_historico_nao_pode_repetir_em_outra_modalidade(self):
        geral = Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 8, 11),
            certificado_numero="CERTIFICADO-HISTORICO-001",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Este número de certificado já foi utilizado em outra calibração.",
        ):
            CalibracaoTurbidez.objects.create(
                instrumento=self.instrumento,
                cliente=self.cliente,
                data_calibracao=date(2026, 8, 11),
                numero_certificado=geral.certificado_numero,
            )

    def test_numero_registrado_e_imutavel(self):
        calibracao = Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 8, 11),
        )
        calibracao.certificado_numero = "OUTRO-NUMERO"

        with self.assertRaisesMessage(
            ValidationError,
            "O número de um certificado registrado não pode ser alterado.",
        ):
            calibracao.save()

    def test_numero_anterior_renumerado_nao_pode_ser_reutilizado(self):
        HistoricoNumeroCertificado.objects.create(
            numero_anterior="CERTIFICADO-ANTIGO-001",
            numero_novo="A1B2C3DS",
            app_label="calibracao",
            modelo="calibracao",
            objeto_id="999999",
            motivo="Teste de rastreabilidade.",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Este número pertence ao histórico de outro certificado.",
        ):
            Calibracao.objects.create(
                instrumento=self.instrumento,
                data_calibracao=date(2026, 8, 11),
                certificado_numero="CERTIFICADO-ANTIGO-001",
            )

    def test_numero_legado_com_ds_permanece_valido_e_imutavel(self):
        calibracao = Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 8, 11),
            certificado_numero="A1B2C3DS",
        )

        registro = NumeroCertificadoEmitido.objects.get(codigo="A1B2C3DS")
        self.assertEqual(calibracao.certificado_numero, "A1B2C3DS")
        self.assertFalse(registro.historico)

    def test_formato_novo_nao_pode_reutilizar_base_de_numero_legado(self):
        Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 8, 11),
            certificado_numero="A1B2C3DS",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Este número de certificado já foi utilizado em outra calibração.",
        ):
            CalibracaoTurbidez.objects.create(
                instrumento=self.instrumento,
                cliente=self.cliente,
                data_calibracao=date(2026, 8, 11),
                numero_certificado="A1B2C3",
            )
