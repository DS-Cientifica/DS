from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente

from .models import OrdemServico, OrdemServicoSequencia


class OrdemServicoNumeroTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            razao_social="Cliente OS LTDA",
            nome_empresa="Cliente OS LTDA",
            cnpj="55.345.678/0001-77",
        )

    @patch("calibracao.models.timezone.localdate", return_value=date(2026, 8, 10))
    def test_numero_is_generated_sequentially(self, _localdate):
        first = OrdemServico.objects.create(cliente=self.cliente)
        second = OrdemServico.objects.create(cliente=self.cliente)

        self.assertEqual(first.numero, "0001/26")
        self.assertEqual(second.numero, "0002/26")
        self.assertEqual(
            OrdemServicoSequencia.objects.get(ano=2026).ultimo_numero,
            2,
        )

    @patch("calibracao.models.timezone.localdate", return_value=date(2026, 8, 10))
    def test_existing_numbers_are_preserved_and_define_next_sequence(self, _localdate):
        existing = OrdemServico.objects.create(
            numero="0005/26",
            cliente=self.cliente,
        )
        generated = OrdemServico.objects.create(cliente=self.cliente)

        existing.refresh_from_db()
        self.assertEqual(existing.numero, "0005/26")
        self.assertEqual(generated.numero, "0006/26")

    def test_sequence_continues_in_new_year_and_only_suffix_changes(self):
        with patch("calibracao.models.timezone.localdate", return_value=date(2026, 12, 31)):
            last_2026 = OrdemServico.objects.create(cliente=self.cliente)
        with patch("calibracao.models.timezone.localdate", return_value=date(2027, 1, 1)):
            first_2027 = OrdemServico.objects.create(cliente=self.cliente)

        self.assertEqual(last_2026.numero, "0001/26")
        self.assertEqual(first_2027.numero, "0002/27")
        self.assertEqual(
            OrdemServicoSequencia.objects.get(ano=2027).ultimo_numero,
            2,
        )

    @patch("calibracao.models.timezone.localdate", return_value=date(2027, 1, 1))
    def test_historical_number_from_previous_year_defines_next_sequence(self, _localdate):
        OrdemServico.objects.create(numero="0125/26", cliente=self.cliente)

        generated = OrdemServico.objects.create(cliente=self.cliente)

        self.assertEqual(generated.numero, "0126/27")

    def test_admin_exposes_number_as_read_only(self):
        from django.contrib.auth.models import User

        user = User.objects.create_superuser("os-admin", "os@example.com", "secret")
        self.client.force_login(user)
        response = self.client.get(reverse("admin:calibracao_ordemservico_add"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gerado automaticamente ao salvar")
        self.assertContains(response, "A sequência é contínua")
        self.assertNotContains(response, 'name="numero"', html=False)
