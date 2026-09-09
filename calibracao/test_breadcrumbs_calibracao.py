from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class CalibracaoBreadcrumbTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            "admin-breadcrumb-calibracao",
            "admin-breadcrumb@example.com",
            "secret",
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_listas_das_modalidades_retornam_para_central_de_calibracoes(self):
        nomes_urls = (
            "admin:calibracao_calibracao_changelist",
            "admin:calibracao_calibracaoturbidez_changelist",
            "admin:calibracao_calibracaocolorimetro_changelist",
            "admin:calibracao_calibracaopressao_changelist",
            "admin:calibracao_calibracaocondutividade_changelist",
            "admin:calibracao_calibracaoph_changelist",
            "admin:calibracao_calibracaobalanca_changelist",
            "admin:calibracao_calibracaodispositivosegurancapressao_changelist",
            "admin:calibracao_calibracaoesfigmomanometro_changelist",
        )
        url_calibracoes = reverse("admin:calibracoes_index")

        for nome_url in nomes_urls:
            with self.subTest(nome_url=nome_url):
                resposta = self.client.get(reverse(nome_url))
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(
                    resposta,
                    f'<a href="{url_calibracoes}">Calibrações</a>',
                    html=True,
                )

    def test_formulario_de_turbidez_mantem_retorno_para_calibracoes(self):
        resposta = self.client.get(
            reverse("admin:calibracao_calibracaoturbidez_add")
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(
            resposta,
            f'<a href="{reverse("admin:calibracoes_index")}">Calibrações</a>',
            html=True,
        )

    def test_padrao_continua_retornando_para_gestao_metrologica(self):
        resposta = self.client.get(reverse("admin:calibracao_padrao_changelist"))

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(
            resposta,
            f'<a href="{reverse("admin:calibracoes_index")}">Calibrações</a>',
            html=True,
        )
