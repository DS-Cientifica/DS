import shutil
import tempfile

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .admin import ClienteAdmin, ClienteAnexoInline
from .models import Cliente, ClienteAnexo


TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class ClienteAnexoTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser(
            username="admin-clientes",
            email="admin@example.com",
            password="senha-teste",
        )
        self.cliente = Cliente.objects.create(
            razao_social="Cliente com anexos",
            nome_empresa="Cliente com anexos",
            cnpj="12.345.678/0001-90",
        )

    def test_cliente_aceita_varios_anexos(self):
        ClienteAnexo.objects.create(
            cliente=self.cliente,
            nome="Contrato",
            arquivo=SimpleUploadedFile("contrato.pdf", b"contrato"),
        )
        ClienteAnexo.objects.create(
            cliente=self.cliente,
            nome="Cadastro",
            arquivo=SimpleUploadedFile("cadastro.pdf", b"cadastro"),
        )

        self.assertEqual(self.cliente.anexos.count(), 2)
        self.assertSetEqual(
            set(self.cliente.anexos.values_list("nome", flat=True)),
            {"Contrato", "Cadastro"},
        )

    def test_admin_exibe_inline_de_anexos_adicionais(self):
        cliente_admin = ClienteAdmin(Cliente, admin.site)

        self.assertIn(ClienteAnexoInline, cliente_admin.inlines)

        self.client.force_login(self.usuario)
        resposta = self.client.get(
            reverse("admin:clientes_cliente_change", args=(self.cliente.pk,))
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Anexos adicionais")
        self.assertContains(resposta, 'name="anexos-0-nome"', html=False)

# Create your tests here.
