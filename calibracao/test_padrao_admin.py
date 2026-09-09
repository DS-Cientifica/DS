from datetime import date, timedelta

from django.contrib.admin.sites import AdminSite
from django.test import SimpleTestCase, TestCase

from .admin import PadraoAdmin
from .dilution_models import PreparacaoPadrao, PreparacaoPadraoResultado
from .models import Padrao


class PadraoAdminTests(SimpleTestCase):
    def setUp(self):
        self.model_admin = PadraoAdmin(Padrao, AdminSite())

    def test_quadro_exibe_somente_colunas_operacionais(self):
        self.assertEqual(
            self.model_admin.list_display,
            (
                "codigo",
                "descricao_objetiva",
                "numero_certificado",
                "data_calibracao",
                "vencimento",
                "situacao_operacional",
                "ver_certificado",
            ),
        )

    def test_situacao_considera_vencimento_mesmo_com_status_valido(self):
        padrao = Padrao(
            codigo="TESTE",
            descricao="Padrão de teste",
            status="valido",
            vencimento=date.today() - timedelta(days=1),
        )

        resultado = str(self.model_admin.situacao_operacional(padrao))

        self.assertIn("Vencido", resultado)
        self.assertIn("is-expired", resultado)


class PadraoAdminQuerysetTests(TestCase):
    def test_resultados_da_diluicao_nao_aparecem_no_cadastro_geral(self):
        padrao_mae = Padrao.objects.create(
            descricao="Solução padrão de turbidez 4000 NTU",
            vencimento=date.today() + timedelta(days=30),
        )
        padrao_diluido = Padrao.objects.create(
            descricao="Padrão preparado de turbidez 100 NTU",
            vencimento=date.today() + timedelta(days=7),
        )
        preparacao = PreparacaoPadrao.objects.create(
            aplicacao="turbidez",
            data_preparacao=date.today(),
            validade=date.today() + timedelta(days=7),
            padrao_origem=padrao_mae,
            unidade="NTU",
        )
        resultado = PreparacaoPadraoResultado.objects.create(
            preparacao=preparacao,
            ordem=1,
            valor_alvo=100,
            volume_final=100,
        )
        PreparacaoPadraoResultado.objects.filter(pk=resultado.pk).update(
            padrao_gerado=padrao_diluido
        )

        queryset = PadraoAdmin(Padrao, AdminSite()).get_queryset(None)

        self.assertIn(padrao_mae, queryset)
        self.assertNotIn(padrao_diluido, queryset)
