from decimal import Decimal

from django.test import TestCase

from clientes.models import Cliente

from .models import ItemNotaFiscal, NotaFiscal


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
