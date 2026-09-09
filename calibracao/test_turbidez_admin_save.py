from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente

from .dilution_models import PreparacaoPadrao, PreparacaoPadraoResultado
from .models import CalibracaoTurbidez, Instrumento, OrdemServico, Padrao


class CalibracaoTurbidezAdminSaveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            "admin-salvar-turbidez",
            "admin-turbidez@example.com",
            "secret",
        )
        cls.cliente = Cliente.objects.create(
            razao_social="Cliente Turbidez Ltda",
            nome_empresa="Cliente Turbidez",
            cnpj="31.222.333/0001-40",
        )
        cls.instrumento = Instrumento.objects.create(
            codigo="TURB-SAVE-001",
            descricao="Turbidímetro",
            cliente=cls.cliente,
        )
        cls.ordem = OrdemServico.objects.create(
            cliente=cls.cliente,
            status="em_andamento",
        )
        cls.ordem.instrumentos.add(cls.instrumento)

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_admin_salva_calibracao_de_turbidez_sem_pontos(self):
        url = reverse("admin:calibracao_calibracaoturbidez_add")
        resposta_get = self.client.get(url)
        self.assertContains(resposta_get, "Preparação de padrão utilizada")
        dados = {
            "ordem_servico": "",
            "data_calibracao": date(2026, 8, 22).isoformat(),
            "data_emissao": date(2026, 8, 22).isoformat(),
            "revisao": "00",
            "instrumento": str(self.instrumento.pk),
            "cliente": str(self.cliente.pk),
            "local_calibracao": "ds_cientifica",
            "equipamento_calibrado": "Turbidímetro",
            "unidade_leitura": "NTU",
            "_save": "Salvar",
        }
        for inline in resposta_get.context["inline_admin_formsets"]:
            prefixo = inline.formset.prefix
            dados[f"{prefixo}-TOTAL_FORMS"] = "0"
            dados[f"{prefixo}-INITIAL_FORMS"] = "0"
            dados[f"{prefixo}-MIN_NUM_FORMS"] = "0"
            dados[f"{prefixo}-MAX_NUM_FORMS"] = "1000"

        resposta_post = self.client.post(url, dados)

        self.assertEqual(resposta_post.status_code, 302)
        calibracao = CalibracaoTurbidez.objects.get()
        self.assertEqual(calibracao.ordem_servico, self.ordem.numero)

    def test_sincronizacao_cria_incerteza_sem_apagar_valores_informados(self):
        calibracao = CalibracaoTurbidez.objects.create(
            instrumento=self.instrumento,
            cliente=self.cliente,
            data_calibracao=date(2026, 8, 22),
        )
        calibracao.pontos_calibracao.create(
            ordem=1,
            valor_referencia=Decimal("10.000"),
            leitura_1=Decimal("10.100"),
            leitura_2=Decimal("10.000"),
            leitura_3=Decimal("9.900"),
        )

        calibracao.sincronizar_pontos_incerteza()

        ponto = calibracao.pontos_incerteza.get(ordem=1)
        self.assertIsNotNone(ponto.repetibilidade)

    def test_importa_padrao_mae_e_resultados_de_preparacao_aprovada(self):
        padrao_mae = Padrao.objects.create(
            descricao="Solução padrão de turbidez 4000 NTU",
            numero_certificado="CERT-MAE-001",
            laboratorio_emitente="Laboratório rastreável",
            data_calibracao=date(2026, 1, 10),
            vencimento=date(2027, 1, 10),
            valor_nominal=Decimal("4000"),
            incerteza=Decimal("8"),
            fator_k=Decimal("2"),
            unidade="NTU",
        )
        padrao_preparado = Padrao.objects.create(
            descricao="Padrão preparado - Turbidez - 100 NTU",
            numero_certificado="DIL-TUR-200826-01-P01/26",
            laboratorio_emitente="DS Científica",
            data_calibracao=date(2026, 8, 20),
            vencimento=date(2026, 8, 27),
            valor_nominal=Decimal("100"),
            incerteza=Decimal("0.5"),
            fator_k=Decimal("2"),
            unidade="NTU",
        )
        preparacao = PreparacaoPadrao.objects.create(
            aplicacao="turbidez",
            status="aprovado",
            data_preparacao=date(2026, 8, 20),
            validade=date(2026, 8, 27),
            padrao_origem=padrao_mae,
            unidade="NTU",
            responsavel_preparo="Técnico",
        )
        resultado = PreparacaoPadraoResultado.objects.create(
            preparacao=preparacao,
            ordem=1,
            valor_alvo=Decimal("100"),
            volume_final=Decimal("100"),
        )
        PreparacaoPadraoResultado.objects.filter(pk=resultado.pk).update(
            padrao_gerado=padrao_preparado,
            valor_calculado=Decimal("100"),
            incerteza_expandida=Decimal("0.5"),
            fator_abrangencia=Decimal("2"),
        )
        resultado.refresh_from_db()

        calibracao = CalibracaoTurbidez.objects.create(
            instrumento=self.instrumento,
            cliente=self.cliente,
            data_calibracao=date(2026, 8, 22),
            preparacao_padrao=preparacao,
        )

        self.assertEqual(calibracao.importar_padroes_da_preparacao(), 2)
        self.assertEqual(calibracao.importar_padroes_da_preparacao(), 0)
        mae = calibracao.padroes_utilizados.get(tipo="padrao_mae")
        preparado = calibracao.padroes_utilizados.get(tipo="padrao_diluicao")
        self.assertEqual(mae.padrao, padrao_mae)
        self.assertIsNone(preparado.padrao)
        self.assertEqual(preparado.resultado_preparacao, resultado)
        self.assertEqual(preparado.codigo, resultado.codigo_resultado)
        self.assertEqual(preparado.numero_certificado, resultado.codigo_resultado)
        self.assertEqual(preparado.valor_nominal, Decimal("100"))
        self.assertEqual(
            preparado.descricao,
            "Padrão secundário preparado por diluição - 100.000000000 NTU",
        )

    def test_rejeita_preparacao_nao_aprovada(self):
        padrao_mae = Padrao.objects.create(
            descricao="Solução padrão de turbidez",
            vencimento=date(2027, 1, 10),
        )
        preparacao = PreparacaoPadrao.objects.create(
            aplicacao="turbidez",
            status="em_revisao",
            data_preparacao=date(2026, 8, 20),
            validade=date(2026, 8, 27),
            padrao_origem=padrao_mae,
            unidade="NTU",
            responsavel_preparo="Técnico",
        )
        calibracao = CalibracaoTurbidez(
            instrumento=self.instrumento,
            cliente=self.cliente,
            data_calibracao=date(2026, 8, 22),
            preparacao_padrao=preparacao,
        )
        resposta = self.client.get(reverse("admin:calibracao_calibracaoturbidez_add"))

        self.assertContains(resposta, preparacao.codigo)
        with self.assertRaisesMessage(ValidationError, "A preparação deve estar aprovada"):
            calibracao.full_clean()
