from datetime import date

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from certificados.models import CertificadoCalibracao
from clientes.models import Cliente
from documentos.models import DocumentoArquivo

from .admin import CalibracaoAdmin
from .models import Calibracao, CalibracaoAnexo, Instrumento


class CalibracaoDeletionProtectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            razao_social="Cliente VAL-002",
            nome_empresa="Cliente VAL-002",
            cnpj="10.000.000/0001-02",
        )
        cls.instrumento = Instrumento.objects.create(
            codigo="VAL002-001",
            descricao="Instrumento de teste VAL-002",
            cliente=cls.cliente,
        )
        cls.usuario_sem_permissao = get_user_model().objects.create_user(
            username="val002-sem-delete",
            password="valor-apenas-de-teste",
            is_staff=True,
        )
        cls.usuario_autorizado = get_user_model().objects.create_user(
            username="val002-com-delete",
            password="valor-apenas-de-teste",
            is_staff=True,
        )
        permissao = Permission.objects.get(
            content_type__app_label="calibracao",
            codename="delete_calibracao",
        )
        cls.usuario_autorizado.user_permissions.add(permissao)
        permissoes_consulta = Permission.objects.filter(
            content_type__app_label="calibracao",
            codename__in=("view_calibracao", "change_calibracao"),
        )
        cls.usuario_autorizado.user_permissions.add(*permissoes_consulta)
        cls.usuario_sem_permissao.user_permissions.add(*permissoes_consulta)

    def setUp(self):
        self.factory = RequestFactory()
        self.model_admin = CalibracaoAdmin(Calibracao, admin.site)

    def _request(self, user):
        request = self.factory.post("/admin/calibracao/calibracao/")
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def _rascunho_sem_resultado_oficial(self):
        calibracao = Calibracao(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 10, 3),
            status="aberta",
            certificado_numero="",
        )
        Calibracao.objects.bulk_create([calibracao])
        return Calibracao.objects.get(pk=calibracao.pk)

    def test_usuario_sem_delete_permission_nao_exclui_rascunho(self):
        calibracao = self._rascunho_sem_resultado_oficial()
        request = self._request(self.usuario_sem_permissao)

        self.assertFalse(self.model_admin.has_delete_permission(request, calibracao))

    def test_usuario_autorizado_exclui_rascunho_sem_resultado_oficial(self):
        calibracao = self._rascunho_sem_resultado_oficial()
        anexo = CalibracaoAnexo.objects.create(
            calibracao=calibracao,
            arquivo="testes/val002/rascunho.txt",
        )
        request = self._request(self.usuario_autorizado)

        self.assertTrue(self.model_admin.has_delete_permission(request, calibracao))
        self.model_admin.delete_model(request, calibracao)

        self.assertFalse(Calibracao.objects.filter(pk=calibracao.pk).exists())
        self.assertFalse(CalibracaoAnexo.objects.filter(pk=anexo.pk).exists())

    def test_calibracao_com_numero_de_certificado_nao_pode_ser_excluida(self):
        calibracao = Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 10, 3),
        )
        request = self._request(self.usuario_autorizado)

        self.assertFalse(self.model_admin.has_delete_permission(request, calibracao))
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_model(request, calibracao)

        self.assertTrue(Calibracao.objects.filter(pk=calibracao.pk).exists())

    def test_calibracao_publicada_nao_pode_ser_excluida(self):
        calibracao = self._rascunho_sem_resultado_oficial()
        content_type = ContentType.objects.get_for_model(
            Calibracao,
            for_concrete_model=False,
        )
        CertificadoCalibracao.objects.create(
            numero="VAL-002-PUBLICADO",
            calibracao_content_type=content_type,
            calibracao_object_id=str(calibracao.pk),
            instrumento=self.instrumento,
            cliente=self.cliente,
            data_calibracao=calibracao.data_calibracao,
            status=CertificadoCalibracao.Status.VALIDO,
            publicado=True,
        )
        request = self._request(self.usuario_autorizado)

        self.assertFalse(self.model_admin.has_delete_permission(request, calibracao))
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_model(request, calibracao)

        self.assertTrue(Calibracao.objects.filter(pk=calibracao.pk).exists())

    def test_exclusao_em_massa_nao_contorna_protecao(self):
        rascunho = self._rascunho_sem_resultado_oficial()
        protegida = Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 10, 4),
        )
        request = self._request(self.usuario_autorizado)

        self.model_admin.delete_queryset(
            request,
            Calibracao.objects.filter(pk__in=(rascunho.pk, protegida.pk)),
        )

        self.assertTrue(Calibracao.objects.filter(pk=rascunho.pk).exists())
        self.assertTrue(Calibracao.objects.filter(pk=protegida.pk).exists())
        mensagens = [str(message) for message in get_messages(request)]
        self.assertTrue(any("Nenhuma calibração foi excluída" in item for item in mensagens))

    def test_queryset_nao_remove_certificado_nem_documento_por_cascade(self):
        calibracao = self._rascunho_sem_resultado_oficial()
        anexo = CalibracaoAnexo.objects.create(
            calibracao=calibracao,
            arquivo="testes/val002/protegido.txt",
        )
        content_type = ContentType.objects.get_for_model(
            Calibracao,
            for_concrete_model=False,
        )
        documento = DocumentoArquivo.objects.create(
            tipo_documento="certificado_calibracao",
            nome_original="resultado-oficial.pdf",
            chave_armazenamento="testes/val002/resultado-oficial.pdf",
            sha256="a" * 64,
            tamanho=100,
            imutavel=True,
            content_type=content_type,
            object_id=str(calibracao.pk),
        )
        certificado = CertificadoCalibracao.objects.create(
            numero="VAL-002-INTEGRIDADE",
            calibracao_content_type=content_type,
            calibracao_object_id=str(calibracao.pk),
            instrumento=self.instrumento,
            cliente=self.cliente,
            documento=documento,
            data_calibracao=calibracao.data_calibracao,
            status=CertificadoCalibracao.Status.VALIDO,
            publicado=True,
        )

        with self.assertRaises(ProtectedError), transaction.atomic():
            Calibracao.objects.filter(pk=calibracao.pk).delete()

        self.assertTrue(Calibracao.objects.filter(pk=calibracao.pk).exists())
        self.assertTrue(CertificadoCalibracao.objects.filter(pk=certificado.pk).exists())
        self.assertTrue(DocumentoArquivo.objects.filter(pk=documento.pk).exists())
        self.assertTrue(CalibracaoAnexo.objects.filter(pk=anexo.pk).exists())

    def test_exclusao_do_instrumento_pai_preserva_calibracao(self):
        calibracao = Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 10, 5),
        )

        with self.assertRaises(ProtectedError), transaction.atomic():
            Instrumento.objects.filter(pk=self.instrumento.pk).delete()

        self.assertTrue(Instrumento.objects.filter(pk=self.instrumento.pk).exists())
        self.assertTrue(Calibracao.objects.filter(pk=calibracao.pk).exists())

    def test_admin_oculta_excluir_para_usuario_sem_permissao(self):
        calibracao = self._rascunho_sem_resultado_oficial()
        self.client.force_login(self.usuario_sem_permissao)

        response = self.client.get(
            reverse("admin:calibracao_calibracao_change", args=(calibracao.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="deletelink"')

    def test_admin_bloqueia_url_de_exclusao_e_exibe_mensagem(self):
        calibracao = Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 10, 6),
        )
        self.client.force_login(self.usuario_autorizado)

        change_url = reverse(
            "admin:calibracao_calibracao_change",
            args=(calibracao.pk,),
        )
        change_response = self.client.get(change_url)
        self.assertEqual(change_response.status_code, 200)
        self.assertNotContains(change_response, 'class="deletelink"')

        delete_response = self.client.get(
            reverse("admin:calibracao_calibracao_delete", args=(calibracao.pk,)),
            follow=True,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertContains(delete_response, "não pode ser excluída")
        self.assertTrue(Calibracao.objects.filter(pk=calibracao.pk).exists())

    def test_admin_exibe_excluir_para_rascunho_autorizado(self):
        calibracao = self._rascunho_sem_resultado_oficial()
        self.client.force_login(self.usuario_autorizado)

        response = self.client.get(
            reverse("admin:calibracao_calibracao_change", args=(calibracao.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="deletelink"')
