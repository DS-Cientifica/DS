from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente

from .models import Instrumento, InstrumentoTecnico, Padrao, Periodicidade


class InstrumentoDuplicateAdminTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser(
            username="admin-copia-instrumento",
            email="admin@example.com",
            password="senha-teste",
        )
        self.client.force_login(self.usuario)
        self.cliente = Cliente.objects.create(
            codigo="CL-DUP",
            razao_social="Cliente Teste Duplicação",
            nome_empresa="Cliente Teste",
            cnpj="12.345.678/0001-90",
        )
        self.padrao = Padrao.objects.create(
            codigo="DSP-DUP",
            descricao="Padrão de teste",
            vencimento=date(2030, 1, 1),
        )
        self.origem = Instrumento.objects.create(
            codigo="INST-ORIGEM",
            descricao="Manômetro analógico",
            marca="Marca A",
            modelo="Modelo X",
            local_instalacao="Linha 1",
            numero_serie="SERIE-ORIGEM",
            tag="PT-101",
            cliente=self.cliente,
            status="inativo",
            proxima_calibracao=date(2027, 1, 1),
            ativo=False,
            nome_anexo="Certificado anterior",
            anexo="instrumentos/original.pdf",
        )
        self.origem.padroes.add(self.padrao)
        InstrumentoTecnico.objects.create(
            instrumento=self.origem,
            faixa_medicao="0 a 10 bar",
            capacidade_total="10 bar",
            menor_resolucao=Decimal("0.1000"),
            unidade="bar",
            classe="A",
            observacoes="Configuração técnica de teste",
        )
        Periodicidade.objects.create(
            instrumento=self.origem,
            tipo="calibracao",
            intervalo_meses=12,
        )
        self.url = reverse(
            "admin:calibracao_instrumento_duplicar",
            args=[self.origem.pk],
        )

    def test_copia_dados_tecnicos_sem_herdar_historico_ou_identidade_fisica(self):
        response = self.client.post(
            self.url,
            {
                "codigo": "INST-NOVO",
                "tag": "PT-102",
                "numero_serie": "SERIE-NOVA",
                "local_instalacao": "Linha 2",
            },
        )

        novo = Instrumento.objects.get(codigo="INST-NOVO")
        self.assertRedirects(
            response,
            reverse("admin:calibracao_instrumento_change", args=[novo.pk]),
        )
        self.assertEqual(novo.tag, "PT-102")
        self.assertEqual(novo.numero_serie, "SERIE-NOVA")
        self.assertEqual(novo.local_instalacao, "Linha 2")
        self.assertEqual(novo.descricao, self.origem.descricao)
        self.assertEqual(novo.marca, self.origem.marca)
        self.assertEqual(novo.modelo, self.origem.modelo)
        self.assertEqual(novo.status, "ativo")
        self.assertTrue(novo.ativo)
        self.assertIsNone(novo.proxima_calibracao)
        self.assertFalse(bool(novo.anexo))
        self.assertEqual(novo.nome_anexo, "")
        self.assertEqual(list(novo.padroes.all()), [self.padrao])
        self.assertEqual(novo.tecnico.faixa_medicao, "0 a 10 bar")
        self.assertEqual(novo.tecnico.menor_resolucao, Decimal("0.1000"))
        self.assertTrue(
            novo.periodicidades.filter(tipo="calibracao", intervalo_meses=12).exists()
        )

    def test_exige_novo_codigo_e_nova_tag(self):
        response = self.client.post(
            self.url,
            {
                "codigo": self.origem.codigo,
                "tag": self.origem.tag,
                "numero_serie": "SERIE-NOVA",
                "local_instalacao": "Linha 1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Já existe um instrumento com este código.")
        self.assertContains(response, "Esta TAG já está cadastrada para o mesmo cliente.")
        self.assertFalse(Instrumento.objects.filter(numero_serie="SERIE-NOVA").exists())

    def test_exige_numero_de_serie_ou_confirmacao_explicita(self):
        response = self.client.post(
            self.url,
            {
                "codigo": "INST-SEM-SERIE",
                "tag": "PT-103",
                "numero_serie": "",
                "local_instalacao": "Linha 3",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Informe o número de série ou confirme explicitamente que ele não é identificável.",
        )
        self.assertFalse(Instrumento.objects.filter(codigo="INST-SEM-SERIE").exists())

    def test_permite_instrumento_sem_numero_de_serie_com_confirmacao(self):
        response = self.client.post(
            self.url,
            {
                "codigo": "INST-SEM-SERIE",
                "tag": "PT-104",
                "numero_serie": "",
                "confirmar_sem_numero_serie": "on",
                "local_instalacao": "Linha 4",
            },
        )

        novo = Instrumento.objects.get(codigo="INST-SEM-SERIE")
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(novo.numero_serie)
