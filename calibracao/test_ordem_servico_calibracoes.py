from datetime import date
from pathlib import Path

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente

from .balance_models import CalibracaoBalanca
from .models import (
    Calibracao,
    CalibracaoColorimetro,
    CalibracaoCondutividade,
    CalibracaoPressao,
    CalibracaoTurbidez,
    Instrumento,
    OrdemServico,
)
from .ph_models import CalibracaoPH
from .safety_models import CalibracaoDispositivoSegurancaPressao
from .services.ordem_servico import preencher_ordem_servico_da_calibracao
from .sphyg_models import CalibracaoEsfigmomanometro


class OrdemServicoAutomaticaCalibracoesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            razao_social="Cliente da OS Ltda",
            nome_empresa="Cliente da OS",
            cnpj="11.222.333/0001-44",
        )
        cls.outro_cliente = Cliente.objects.create(
            razao_social="Outro Cliente Ltda",
            nome_empresa="Outro Cliente",
            cnpj="55.666.777/0001-88",
        )
        cls.instrumento = Instrumento.objects.create(
            codigo="INST-OS-AUTO-001",
            descricao="Instrumento para OS automática",
            cliente=cls.cliente,
        )
        cls.ordem_concluida = OrdemServico.objects.create(
            cliente=cls.cliente,
            status="concluida",
        )
        cls.ordem_concluida.instrumentos.add(cls.instrumento)
        cls.ordem_ativa = OrdemServico.objects.create(
            cliente=cls.cliente,
            status="em_andamento",
        )
        cls.ordem_ativa.instrumentos.add(cls.instrumento)

    def test_todas_as_modalidades_recebem_a_mesma_os_vinculada(self):
        modelos = (
            Calibracao,
            CalibracaoTurbidez,
            CalibracaoColorimetro,
            CalibracaoPressao,
            CalibracaoCondutividade,
            CalibracaoPH,
            CalibracaoBalanca,
            CalibracaoDispositivoSegurancaPressao,
            CalibracaoEsfigmomanometro,
        )

        for modelo in modelos:
            with self.subTest(modelo=modelo._meta.label):
                dados = dict(
                    instrumento=self.instrumento,
                    ordem_servico="",
                )
                if any(campo.name == "cliente" for campo in modelo._meta.fields):
                    dados["cliente"] = self.cliente
                calibracao = modelo(**dados)
                preencher_ordem_servico_da_calibracao(calibracao)
                self.assertEqual(calibracao.ordem_servico, self.ordem_ativa.numero)

    def test_todas_as_modalidades_carregam_o_script_no_admin(self):
        modelos = (
            Calibracao,
            CalibracaoTurbidez,
            CalibracaoColorimetro,
            CalibracaoPressao,
            CalibracaoCondutividade,
            CalibracaoPH,
            CalibracaoBalanca,
            CalibracaoDispositivoSegurancaPressao,
            CalibracaoEsfigmomanometro,
        )

        for modelo in modelos:
            with self.subTest(modelo=modelo._meta.label):
                self.assertIn(
                    "js/calibracao_ordem_servico.js",
                    admin.site._registry[modelo].media._js,
                )

    def test_script_trata_selecao_dinamica_do_instrumento(self):
        caminho_script = (
            Path(__file__).resolve().parent.parent
            / "static"
            / "js"
            / "calibracao_ordem_servico.js"
        )

        conteudo = caminho_script.read_text(encoding="utf-8")

        self.assertIn('"select2:select"', conteudo)
        self.assertIn("atualizarOrdemServico", conteudo)

    def test_sinal_pre_save_persiste_a_os_automaticamente(self):
        calibracao = CalibracaoTurbidez.objects.create(
            instrumento=self.instrumento,
            cliente=self.cliente,
            data_calibracao=date(2026, 8, 21),
        )

        self.assertEqual(calibracao.ordem_servico, self.ordem_ativa.numero)

    def test_valor_manual_nao_e_substituido(self):
        calibracao = CalibracaoPH(
            instrumento=self.instrumento,
            cliente=self.cliente,
            ordem_servico="OS-MANUAL",
        )

        preencher_ordem_servico_da_calibracao(calibracao)

        self.assertEqual(calibracao.ordem_servico, "OS-MANUAL")

    def test_nao_usa_os_de_cliente_diferente(self):
        calibracao = CalibracaoPH(
            instrumento=self.instrumento,
            cliente=self.outro_cliente,
            ordem_servico="",
        )

        preencher_ordem_servico_da_calibracao(calibracao)

        self.assertEqual(calibracao.ordem_servico, "")

    def test_endpoint_retorna_os_prioritaria(self):
        usuario = User.objects.create_superuser(
            "admin-os-calibracao",
            "admin-os@example.com",
            "secret",
        )
        self.client.force_login(usuario)

        resposta = self.client.get(
            reverse("ordem_servico_do_instrumento"),
            {
                "instrumento_id": self.instrumento.pk,
                "cliente_id": self.cliente.pk,
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["numero"], self.ordem_ativa.numero)
        self.assertEqual(resposta.json()["status"], "em_andamento")

    def test_endpoint_trata_identificador_invalido_sem_erro_interno(self):
        usuario = User.objects.create_superuser(
            "admin-os-invalida",
            "admin-os-invalida@example.com",
            "secret",
        )
        self.client.force_login(usuario)

        resposta = self.client.get(
            reverse("ordem_servico_do_instrumento"),
            {"instrumento_id": "identificador-invalido"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"encontrada": False, "numero": ""})
