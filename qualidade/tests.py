from datetime import date

from django.contrib.admin.sites import site
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .admin import DocumentoAnexoInline
from .models import Documento, DocumentoAnexo


class DocumentoEmElaboracaoTests(TestCase):
    def test_rascunho_preserva_campos_de_aprovacao_e_emissao_em_branco(self):
        documento = Documento.objects.create(
            titulo="Formulário em elaboração",
            tipo="formulario",
            revisao="RASCUNHO",
            status="em_elaboracao",
            aprovado_por="",
            data_emissao=None,
            data_ultima_revisao=None,
            arquivo="documentos/formulario-teste.ods",
        )

        documento.refresh_from_db()
        self.assertEqual(documento.aprovado_por, "")
        self.assertIsNone(documento.data_emissao)
        self.assertIsNone(documento.data_ultima_revisao)
        self.assertIsNone(documento.data_proxima_revisao)
        self.assertFalse(documento.vencido)
        historico = documento.historico_revisoes.get()
        self.assertEqual(historico.status, "em_elaboracao")
        self.assertEqual(historico.data, date.today())
        self.assertEqual(historico.alteracao, "Documento cadastrado em elaboração")


class DocumentoAnexoTests(TestCase):
    def setUp(self):
        self.documento = Documento.objects.create(
            codigo="TR-001",
            titulo="Treinamento realizado para cliente",
            tipo="treinamento",
            arquivo="documentos/treinamento-principal.pdf",
        )

    def test_documento_de_treinamento_aceita_varios_anexos(self):
        tipos = ("foto", "video", "lista_presenca", "certificado")
        for numero, tipo in enumerate(tipos, start=1):
            DocumentoAnexo.objects.create(
                documento=self.documento,
                tipo=tipo,
                titulo=f"Anexo {numero}",
                arquivo=f"documentos/anexos/anexo-{numero}",
            )

        self.assertEqual(self.documento.anexos.count(), 4)
        self.assertSetEqual(
            set(self.documento.anexos.values_list("tipo", flat=True)),
            set(tipos),
        )

    def test_tipo_treinamento_aparece_no_filtro_e_admin_exibe_anexos(self):
        self.assertIn(
            ("treinamento", "Treinamento de cliente"),
            Documento.TIPO_CHOICES,
        )
        self.assertIn(DocumentoAnexoInline, site._registry[Documento].inlines)

        usuario = User.objects.create_superuser(
            username="admin_documento_anexo",
            email="admin-documento-anexo@example.com",
            password="senha-segura",
        )
        self.client.force_login(usuario)
        response = self.client.get(
            reverse("admin:qualidade_documento_change", args=[self.documento.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fotos, vídeos e outros documentos")
        self.assertContains(response, 'name="anexos-0-arquivo"', html=False)
        self.assertContains(response, "Treinamento de cliente")

    def test_grupo_qualidade_pode_incluir_anexo_do_documento(self):
        grupo = Group.objects.get(name="Qualidade")

        self.assertTrue(
            grupo.permissions.filter(
                content_type__app_label="qualidade",
                codename="add_documentoanexo",
            ).exists()
        )

# Create your tests here.
