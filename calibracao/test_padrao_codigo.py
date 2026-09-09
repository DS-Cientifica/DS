from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Padrao, PadraoSequencia


class PadraoCodigoAutomaticoTests(TestCase):
    def criar_padrao(self, **dados):
        valores = {
            "descricao": "Padrão de teste",
            "vencimento": date(2027, 8, 21),
        }
        valores.update(dados)
        return Padrao.objects.create(**valores)

    def test_gera_codigo_dsp_sequencial_a_partir_do_maior_existente(self):
        self.criar_padrao(codigo="DSP-028", descricao="Padrão existente")

        primeiro = self.criar_padrao(descricao="Primeiro automático")
        segundo = self.criar_padrao(descricao="Segundo automático")

        self.assertEqual(primeiro.codigo, "DSP-029")
        self.assertEqual(segundo.codigo, "DSP-030")
        self.assertEqual(PadraoSequencia.objects.get(pk=1).ultimo_numero, 30)

    def test_preserva_codigo_historico_informado(self):
        padrao = self.criar_padrao(codigo="MRC-PH-001")

        self.assertEqual(padrao.codigo, "MRC-PH-001")
        self.assertFalse(PadraoSequencia.objects.exists())

    def test_codigo_nao_e_editavel_no_admin(self):
        usuario = User.objects.create_superuser(
            "admin-padrao-codigo",
            "admin-padrao@example.com",
            "secret",
        )
        self.client.force_login(usuario)

        resposta = self.client.get(reverse("admin:calibracao_padrao_add"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Gerado automaticamente no formato DSP-001")
        self.assertNotContains(resposta, 'name="codigo"', html=False)
