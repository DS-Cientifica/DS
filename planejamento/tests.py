from datetime import date, time

from django.core import mail
from django.test import TestCase, override_settings

from clientes.models import Cliente, ContatoCliente

from .email_notifications import enviar_email_agendamento
from .models import PlanejamentoServico


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="contato@dscientifica.com.br",
)
class EmailAgendamentoTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            razao_social="Cliente Teste Ltda.",
            nome_empresa="Cliente Teste",
            cnpj="12.345.678/0001-90",
            email="geral@cliente.example",
            endereco="Rua das Indústrias",
            numero="100",
            cidade="Campinas",
            uf="SP",
        )
        self.contato = ContatoCliente.objects.create(
            cliente=self.cliente,
            nome="Maria Responsável",
            email="maria@cliente.example",
            principal=True,
        )
        self.planejamento = PlanejamentoServico.objects.create(
            cliente=self.cliente,
            contato=self.contato,
            titulo="Calibração em campo",
            status="agendado",
            data_inicio=date(2026, 8, 25),
            data_fim=date(2026, 8, 25),
            hora_inicio=time(9, 0),
            hora_fim=time(11, 30),
            local_servico="Laboratório do cliente",
        )

    def test_envia_email_html_e_texto_ao_contato(self):
        resultado = enviar_email_agendamento(self.planejamento)

        self.assertEqual(resultado, "enviado")
        self.assertEqual(len(mail.outbox), 1)
        mensagem = mail.outbox[0]
        self.assertEqual(mensagem.to, ["maria@cliente.example"])
        self.assertIn(self.planejamento.codigo, mensagem.subject)
        self.assertIn("25/08/2026", mensagem.body)
        self.assertIn("Laboratório do cliente", mensagem.body)
        self.assertEqual(mensagem.alternatives[0].mimetype, "text/html")
        convite = next(anexo for anexo in mensagem.attachments if anexo.filename.endswith(".ics"))
        self.assertIn("METHOD:REQUEST", convite.content)
        self.assertIn("ATTENDEE", convite.content)
        self.assertIn("DTSTART:20260825T120000Z", convite.content)

        self.planejamento.refresh_from_db()
        self.assertIsNotNone(self.planejamento.email_agendamento_enviado_em)
        self.assertEqual(
            self.planejamento.email_agendamento_destinatario,
            "maria@cliente.example",
        )
        self.assertEqual(self.planejamento.email_agendamento_erro, "")

    def test_nao_duplica_email_sem_alteracao_relevante(self):
        self.assertEqual(enviar_email_agendamento(self.planejamento), "enviado")
        self.planejamento.refresh_from_db()

        self.assertEqual(enviar_email_agendamento(self.planejamento), "duplicado")
        self.assertEqual(len(mail.outbox), 1)

    def test_alteracao_de_local_gera_email_atualizado(self):
        self.assertEqual(enviar_email_agendamento(self.planejamento), "enviado")
        self.planejamento.refresh_from_db()
        self.planejamento.local_servico = "Nova unidade do cliente"
        self.planejamento.save(update_fields=("local_servico", "updated_at"))

        self.assertEqual(enviar_email_agendamento(self.planejamento), "enviado")
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("Nova unidade do cliente", mail.outbox[1].body)

    def test_rascunho_nao_envia(self):
        self.planejamento.status = "rascunho"
        self.planejamento.save(update_fields=("status", "updated_at"))

        self.assertEqual(
            enviar_email_agendamento(self.planejamento),
            "status_ignorado",
        )
        self.assertEqual(len(mail.outbox), 0)
