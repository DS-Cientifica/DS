from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from clientes.models import Cliente
from clientes.models import ContatoCliente
from financeiro.models import ContaReceber

from .models import ItemProposta, Proposta, PropostaMovimentacao


class PropostaContaReceberTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            razao_social="Cliente Teste Ltda",
            nome_empresa="Cliente Teste Ltda",
            cnpj="12.345.678/0001-90",
        )

    def test_cria_conta_receber_quando_proposta_e_aprovada(self):
        proposta = Proposta.objects.create(
            cliente=self.cliente,
            prazo_pagamento="28 DDL",
            total=Decimal("1500.00"),
            gera_conta_receber_automaticamente=True,
            tipo_faturamento="imediato",
            status="aprovado",
        )

        conta = ContaReceber.objects.get(proposta=proposta)

        self.assertEqual(conta.status, "pendente")
        self.assertEqual(conta.cliente, self.cliente)
        self.assertEqual(conta.valor, Decimal("1500.00"))
        self.assertEqual(conta.descricao, f"Proposta {proposta.codigo}")
        self.assertEqual(conta.vencimento, proposta.data_emissao + timedelta(days=28))

    def test_nao_duplica_conta_receber_em_edicoes_posteriores(self):
        proposta = Proposta.objects.create(
            cliente=self.cliente,
            total=Decimal("2500.00"),
            gera_conta_receber_automaticamente=True,
            tipo_faturamento="imediato",
            status="aprovado",
        )

        self.assertEqual(ContaReceber.objects.filter(proposta=proposta).count(), 1)

        proposta.observacoes = "Ajuste interno"
        proposta.save()

        self.assertEqual(ContaReceber.objects.filter(proposta=proposta).count(), 1)

    def test_nao_cria_segunda_conta_quando_ja_existe_vinculo_manual(self):
        proposta = Proposta.objects.create(
            cliente=self.cliente,
            total=Decimal("3200.00"),
            status="rascunho",
        )

        ContaReceber.objects.create(
            proposta=proposta,
            cliente=self.cliente,
            descricao="Conta manual",
            valor=Decimal("3200.00"),
            vencimento=proposta.data_emissao,
            status="pendente",
        )

        proposta.status = "aprovado"
        proposta.save()

        self.assertEqual(ContaReceber.objects.filter(proposta=proposta).count(), 1)

    def test_nao_cria_conta_automatica_quando_opcao_esta_desabilitada(self):
        proposta = Proposta.objects.create(
            cliente=self.cliente,
            total=Decimal("1800.00"),
            status="aprovado",
        )

        self.assertFalse(ContaReceber.objects.filter(proposta=proposta).exists())

    def test_nao_cria_conta_automatica_para_faturamento_apos_execucao(self):
        proposta = Proposta.objects.create(
            cliente=self.cliente,
            total=Decimal("2100.00"),
            gera_conta_receber_automaticamente=True,
            tipo_faturamento="apos_execucao",
            status="aprovado",
        )

        self.assertFalse(ContaReceber.objects.filter(proposta=proposta).exists())

    def test_total_da_proposta_considera_desconto_geral_margem_e_despesas(self):
        proposta = Proposta.objects.create(
            cliente=self.cliente,
            desconto_geral=Decimal("100.00"),
            frete_valor=Decimal("50.00"),
            outras_despesas=Decimal("20.00"),
            seguro_valor=Decimal("10.00"),
            margem_percentual=Decimal("10.00"),
        )

        ItemProposta.objects.create(
            proposta=proposta,
            descricao="Servico A",
            quantidade=2,
            valor_unitario=Decimal("100.00"),
            desconto=Decimal("20.00"),
        )

        proposta.refresh_from_db()

        self.assertEqual(proposta.total, Decimal("182.22"))

    def test_item_calcula_valores_com_margem_da_proposta(self):
        proposta = Proposta.objects.create(
            cliente=self.cliente,
            margem_percentual=Decimal("20.00"),
        )

        item = ItemProposta.objects.create(
            proposta=proposta,
            descricao="Servico B",
            quantidade=2,
            valor_unitario=Decimal("100.00"),
            desconto=Decimal("10.00"),
        )

        self.assertEqual(item.valor_unitario_com_margem(), Decimal("125.00"))
        self.assertEqual(item.valor_total_com_margem(), Decimal("240.00"))

    def test_criar_revisao_incrementa_revisao_sem_movimentacao(self):
        proposta = Proposta.objects.create(cliente=self.cliente)

        revisao = proposta.criar_revisao(descricao="Revisao criada no teste.")

        proposta.refresh_from_db()
        self.assertEqual(revisao, "01")
        self.assertEqual(proposta.revisao, "01")
        self.assertFalse(PropostaMovimentacao.objects.filter(proposta=proposta).exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PropostaEmailTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin_email",
            email="admin@teste.com",
            password="teste123456",
        )
        self.cliente = Cliente.objects.create(
            razao_social="Cliente Email Ltda",
            nome_empresa="Cliente Email Ltda",
            cnpj="22.333.444/0001-55",
            email="cliente@teste.com",
        )
        self.contato = ContatoCliente.objects.create(
            cliente=self.cliente,
            nome="Compras",
            email="compras@cliente.com",
            principal=True,
        )
        self.proposta = Proposta.objects.create(
            cliente=self.cliente,
            responsavel=self.contato,
            status="enviado",
        )
        ItemProposta.objects.create(
            proposta=self.proposta,
            descricao="Servico Email",
            quantidade=1,
            valor_unitario=Decimal("100.00"),
            desconto=Decimal("0.00"),
        )

    @override_settings(
        EMAIL_HOST="smtp.zoho.com",
        EMAIL_HOST_USER="contato@dscientifica.com.br",
        EMAIL_HOST_PASSWORD="senha-app",
        DEFAULT_FROM_EMAIL="contato@dscientifica.com.br",
    )
    def test_envia_proposta_por_email_com_anexo_pdf(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("enviar_proposta_email", args=[self.proposta.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["compras@cliente.com"])
        self.assertIn(self.proposta.codigo, email.subject)
        self.assertEqual(len(email.attachments), 1)
        nome_anexo, conteudo, mimetype = email.attachments[0]
        self.assertTrue(nome_anexo.endswith(".pdf"))
        self.assertEqual(mimetype, "application/pdf")
        self.assertTrue(conteudo.startswith(b"%PDF"))
