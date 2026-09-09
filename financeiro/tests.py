from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente

from .models import ContaPagar, ItemNotaFiscal, NotaFiscal


class ContaPagarRecorrenciaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="admin_financeiro",
            email="financeiro@example.com",
            password="teste-seguro",
        )

    def test_conta_parcelada_divide_total_sem_perder_centavos(self):
        primeira = ContaPagar.objects.create(
            descricao="Equipamento parcelado",
            fornecedor="Fornecedor A",
            valor=Decimal("100.00"),
            vencimento=date(2027, 1, 31),
            tipo_recorrencia="parcelada",
            total_ocorrencias=3,
        )

        contas = list(
            ContaPagar.objects.filter(serie_recorrencia=primeira.serie_recorrencia)
            .order_by("numero_ocorrencia")
        )
        self.assertEqual(len(contas), 3)
        self.assertEqual([conta.valor for conta in contas], [
            Decimal("33.34"), Decimal("33.33"), Decimal("33.33")
        ])
        self.assertEqual(sum((conta.valor for conta in contas), Decimal("0.00")), Decimal("100.00"))
        self.assertEqual(
            [conta.vencimento for conta in contas],
            [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31)],
        )
        self.assertTrue(all(conta.valor_total_serie == Decimal("100.00") for conta in contas))

    def test_conta_fixa_repete_valor_mensal(self):
        primeira = ContaPagar.objects.create(
            descricao="Aluguel",
            fornecedor="Fornecedor B",
            valor=Decimal("250.00"),
            vencimento=date(2027, 4, 10),
            tipo_recorrencia="fixa_mensal",
            total_ocorrencias=4,
        )

        contas = ContaPagar.objects.filter(
            serie_recorrencia=primeira.serie_recorrencia
        ).order_by("numero_ocorrencia")
        self.assertEqual(contas.count(), 4)
        self.assertEqual(list(contas.values_list("valor", flat=True)), [Decimal("250.00")] * 4)
        self.assertTrue(all(conta.valor_total_serie == Decimal("1000.00") for conta in contas))

    def test_editar_ocorrencia_nao_gera_nova_serie(self):
        primeira = ContaPagar.objects.create(
            descricao="Serviço mensal",
            fornecedor="Fornecedor C",
            valor=Decimal("75.00"),
            vencimento=date(2027, 5, 5),
            tipo_recorrencia="fixa_mensal",
            total_ocorrencias=2,
        )
        primeira.descricao = "Serviço mensal revisado"
        primeira.save()

        self.assertEqual(
            ContaPagar.objects.filter(serie_recorrencia=primeira.serie_recorrencia).count(),
            2,
        )

    def test_serie_exige_ao_menos_duas_ocorrencias(self):
        with self.assertRaises(ValidationError):
            ContaPagar.objects.create(
                descricao="Inválida",
                fornecedor="Fornecedor D",
                valor=Decimal("10.00"),
                vencimento=date(2027, 6, 1),
                tipo_recorrencia="parcelada",
                total_ocorrencias=1,
            )

    def test_conta_unica_mantem_comportamento_anterior(self):
        conta = ContaPagar.objects.create(
            descricao="Conta avulsa",
            fornecedor="Fornecedor E",
            valor=Decimal("50.00"),
            vencimento=date(2027, 7, 1),
        )
        self.assertIsNone(conta.serie_recorrencia)
        self.assertEqual(conta.total_ocorrencias, 1)
        self.assertEqual(ContaPagar.objects.count(), 1)

    def test_admin_exibe_opcoes_de_recorrencia(self):
        self.client.force_login(self.admin)
        resposta = self.client.get(reverse("admin:financeiro_contapagar_add"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Conta parcelada")
        self.assertContains(resposta, "Conta fixa mensal")
        self.assertContains(resposta, "financeiro/js/conta_pagar_recorrencia.js")

    def test_admin_bloqueia_estrutura_de_serie_existente(self):
        conta = ContaPagar.objects.create(
            descricao="Contrato",
            fornecedor="Fornecedor F",
            valor=Decimal("120.00"),
            vencimento=date(2027, 8, 1),
            tipo_recorrencia="fixa_mensal",
            total_ocorrencias=2,
        )
        self.client.force_login(self.admin)
        resposta = self.client.get(
            reverse("admin:financeiro_contapagar_change", args=[conta.pk])
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, str(conta.serie_recorrencia))
        self.assertNotContains(resposta, 'name="tipo_recorrencia"')


class NotaFiscalTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            razao_social="Cliente Fiscal Ltda",
            nome_empresa="Cliente Fiscal",
            cnpj="98.765.432/0001-10",
        )

    def test_item_atualiza_valor_total_da_nota(self):
        nota = NotaFiscal.objects.create(
            tipo_nota="venda_produto",
            cliente=self.cliente,
            numero="123",
        )

        ItemNotaFiscal.objects.create(
            nota_fiscal=nota,
            descricao="Produto A",
            quantidade=Decimal("2"),
            valor_unitario=Decimal("15.50"),
        )

        nota.refresh_from_db()
        self.assertEqual(nota.valor_total, Decimal("31.00"))

    def test_propriedades_de_classificacao(self):
        remessa = NotaFiscal.objects.create(tipo_nota="remessa_conserto", cliente=self.cliente)
        retorno = NotaFiscal.objects.create(tipo_nota="retorno_conserto", cliente=self.cliente)
        devolucao = NotaFiscal.objects.create(tipo_nota="devolucao_venda", cliente=self.cliente)

        self.assertTrue(remessa.eh_remessa)
        self.assertTrue(retorno.eh_retorno)
        self.assertTrue(devolucao.eh_devolucao)
