import re
import tempfile
from datetime import date
from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from calibracao.models import Calibracao, CalibracaoTurbidez, Instrumento, Padrao
from clientes.models import Cliente
from documentos.models import AssinaturaDigitalDocumento
from documentos.tests import criar_certificado_a1_teste, criar_pdf_teste
from .models import CertificadoCalibracao, PadraoUtilizado
from .services import (
    assinar_calibracao_a1,
    publicar_calibracao_existente,
    substituir_certificado,
    vincular_padrao,
)


class CertificadoPublicoTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            "signatario-certificado",
            "signatario@example.com",
            "senha-login",
        )
        self.cliente = Cliente.objects.create(
            razao_social="Cliente Teste Ltda",
            nome_empresa="Cliente Teste",
            cnpj="00.000.000/0001-00",
        )
        self.instrumento = Instrumento.objects.create(
            codigo="INST-001", descricao="Instrumento de teste", cliente=self.cliente
        )
        self.calibracao = Calibracao.objects.create(
            instrumento=self.instrumento, data_calibracao=date(2026, 7, 18)
        )
        self.content_type = ContentType.objects.get_for_model(self.calibracao)

    def criar_certificado(self, numero, **kwargs):
        dados = {
            "numero": numero,
            "calibracao_content_type": self.content_type,
            "calibracao_object_id": str(self.calibracao.pk),
            "instrumento": self.instrumento,
            "cliente": self.cliente,
            "data_calibracao": self.calibracao.data_calibracao,
        }
        dados.update(kwargs)
        return CertificadoCalibracao.objects.create(**dados)

    def test_codigo_publico_nao_e_sequencial_nem_usa_caracteres_ambiguos(self):
        certificado = self.criar_certificado("CERT-001")
        self.assertRegex(certificado.codigo_curto, re.compile(r"^[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$"))

    def test_rastreabilidade_usa_padrao_cadastrado_e_preserva_snapshot(self):
        certificado = self.criar_certificado("CERT-002")
        padrao = Padrao.objects.create(
            codigo="PAD-001", descricao="Padrão de referência",
            numero_certificado="LAB-123", laboratorio_emitente="Laboratório RBC",
            data_calibracao=date(2026, 1, 10), vencimento=date(2026, 12, 31), status="valido",
        )
        uso = vincular_padrao(certificado, padrao)
        self.assertEqual(uso.situacao_na_data, PadraoUtilizado.Situacao.VALIDO)
        padrao.numero_certificado = "LAB-999"
        padrao.save(update_fields=("numero_certificado",))
        uso.refresh_from_db()
        self.assertEqual(uso.numero_certificado, "LAB-123")

    def test_validade_e_avaliada_na_data_real_da_calibracao(self):
        certificado = self.criar_certificado("CERT-003")
        padrao = Padrao.objects.create(
            codigo="PAD-002", descricao="Padrão histórico", numero_certificado="LAB-456",
            vencimento=date(2026, 7, 30), status="vencido",
        )
        uso = vincular_padrao(certificado, padrao)
        self.assertEqual(uso.situacao_na_data, PadraoUtilizado.Situacao.VALIDO)

    def test_substituicao_bloqueia_download_do_certificado_anterior(self):
        anterior = self.criar_certificado(
            "CERT-004", status=CertificadoCalibracao.Status.VALIDO,
            publicado=True, permitir_download_publico=True,
        )
        substituto = self.criar_certificado(
            "CERT-004-R1", status=CertificadoCalibracao.Status.VALIDO,
            publicado=True, revisao=1,
        )
        substituir_certificado(anterior, substituto, justificativa="Correção controlada")
        anterior.refresh_from_db()
        self.assertEqual(anterior.status, CertificadoCalibracao.Status.SUBSTITUIDO)
        self.assertFalse(anterior.permitir_download_publico)
        resposta = self.client.get(f"/verificar/{anterior.uuid_publico}/arquivo/", HTTP_HOST="127.0.0.1:8000")
        self.assertEqual(resposta.status_code, 410)

    def test_nao_permite_alterar_padroes_apos_aprovacao(self):
        certificado = self.criar_certificado("CERT-005", status=CertificadoCalibracao.Status.APROVADO)
        padrao = Padrao.objects.create(codigo="PAD-003", descricao="Padrão", vencimento=date(2027, 1, 1))
        with self.assertRaises(ValidationError):
            vincular_padrao(certificado, padrao)

    def test_consulta_publica_exibe_qr_code(self):
        certificado = self.criar_certificado(
            "CERT-006",
            status=CertificadoCalibracao.Status.VALIDO,
            publicado=True,
        )
        resposta = self.client.get(
            f"/verificar/{certificado.uuid_publico}/",
            HTTP_HOST="127.0.0.1:8000",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "<svg", html=False)
        self.assertContains(resposta, "/static/img/logo_ds.png")
        self.assertContains(resposta, "https://www.dscientifica.com.br/")
        self.assertContains(resposta, "tel:+5511988599577")
        self.assertContains(resposta, "https://wa.me/5511988599577")

    def test_publicacao_da_calibracao_legada_e_idempotente_e_imutavel(self):
        with tempfile.TemporaryDirectory() as media_root, tempfile.TemporaryDirectory() as documentos_root:
            with override_settings(
                MEDIA_ROOT=media_root,
                DOCUMENT_LOCAL_ROOT=documentos_root,
                DOCUMENT_STORAGE_MODE="local",
                DOCUMENT_R2_ENABLED=False,
            ):
                padrao = Padrao.objects.create(
                    codigo="PAD-010",
                    descricao="Padrão de publicação",
                    numero_certificado="RBC-010",
                    vencimento=date(2027, 1, 31),
                    status="valido",
                )
                self.instrumento.padroes.add(padrao)
                calibracao = Calibracao.objects.create(
                    instrumento=self.instrumento,
                    data_calibracao=date(2026, 7, 18),
                    status="concluida",
                    certificado_numero="CERT-PUBLICADO-001",
                    origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
                    padroes=padrao.codigo,
                )
                calibracao.certificado_arquivo.save(
                    "certificado-final.pdf",
                    ContentFile(criar_pdf_teste("Certificado controlado")),
                    save=True,
                )

                assinatura = assinar_calibracao_a1(
                    calibracao,
                    certificado_a1=criar_certificado_a1_teste(),
                    senha="senha-teste",
                    usuario=self.usuario,
                )

                certificado, criado = publicar_calibracao_existente(
                    calibracao,
                    usuario=self.usuario,
                )
                repetido, criado_novamente = publicar_calibracao_existente(calibracao)

                self.assertTrue(criado)
                self.assertFalse(criado_novamente)
                self.assertEqual(repetido.pk, certificado.pk)
                self.assertTrue(certificado.publicado)
                self.assertTrue(certificado.documento.imutavel)
                self.assertEqual(certificado.documento, assinatura.documento_assinado)
                self.assertEqual(certificado.padroes_utilizados.get().padrao, padrao)

                consulta = self.client.get(
                    reverse("certificados:consulta", args=[certificado.uuid_publico]),
                    HTTP_HOST="127.0.0.1:8000",
                )
                self.assertContains(consulta, "PAdES — integridade verificada")
                download = self.client.get(
                    reverse("certificados:download", args=[certificado.uuid_publico]),
                    HTTP_HOST="127.0.0.1:8000",
                )
                self.assertEqual(download.status_code, 200)
                self.assertIn(b"/ETSI.CAdES.detached", b"".join(download.streaming_content))

    def test_publicacao_exige_assinatura_digital_do_pdf_atual(self):
        with tempfile.TemporaryDirectory() as media_root, tempfile.TemporaryDirectory() as documentos_root:
            with override_settings(
                MEDIA_ROOT=media_root,
                DOCUMENT_LOCAL_ROOT=documentos_root,
                DOCUMENT_STORAGE_MODE="local",
                DOCUMENT_R2_ENABLED=False,
            ):
                padrao = Padrao.objects.create(
                    codigo="PAD-SEM-ASSINATURA",
                    descricao="Padrão válido",
                    numero_certificado="RBC-020",
                    vencimento=date(2027, 1, 31),
                    status="valido",
                )
                self.instrumento.padroes.add(padrao)
                calibracao = Calibracao.objects.create(
                    instrumento=self.instrumento,
                    data_calibracao=date(2026, 7, 18),
                    status="concluida",
                    certificado_numero="CERT-SEM-ASSINATURA",
                    origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
                    padroes=padrao.codigo,
                )
                calibracao.certificado_arquivo.save(
                    "certificado-sem-assinatura.pdf",
                    ContentFile(criar_pdf_teste("Sem assinatura")),
                    save=True,
                )

                with self.assertRaisesMessage(ValidationError, "Assine digitalmente"):
                    publicar_calibracao_existente(calibracao, usuario=self.usuario)

    def test_assinatura_bloqueia_certificado_emitido_por_terceiro(self):
        calibracao = Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 7, 18),
            status="concluida",
            certificado_numero="CERT-TERCEIRO-001",
            origem_certificado=Calibracao.OrigemCertificado.EMITIDO_TERCEIRO,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "emitidos pela DS Científica",
        ):
            assinar_calibracao_a1(
                calibracao,
                certificado_a1=criar_certificado_a1_teste(),
                senha="senha-teste",
                usuario=self.usuario,
            )
        self.assertFalse(
            AssinaturaDigitalDocumento.objects.filter(object_id=str(calibracao.pk)).exists()
        )

    def test_alteracao_do_pdf_depois_da_assinatura_bloqueia_publicacao(self):
        with tempfile.TemporaryDirectory() as media_root, tempfile.TemporaryDirectory() as documentos_root:
            with override_settings(
                MEDIA_ROOT=media_root,
                DOCUMENT_LOCAL_ROOT=documentos_root,
                DOCUMENT_STORAGE_MODE="local",
                DOCUMENT_R2_ENABLED=False,
            ):
                padrao = Padrao.objects.create(
                    codigo="PAD-PDF-ALTERADO",
                    descricao="Padrão válido",
                    numero_certificado="RBC-021",
                    vencimento=date(2027, 1, 31),
                    status="valido",
                )
                self.instrumento.padroes.add(padrao)
                calibracao = Calibracao.objects.create(
                    instrumento=self.instrumento,
                    data_calibracao=date(2026, 7, 18),
                    status="concluida",
                    certificado_numero="CERT-PDF-ALTERADO",
                    origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
                    padroes=padrao.codigo,
                )
                calibracao.certificado_arquivo.save(
                    "certificado-original.pdf",
                    ContentFile(criar_pdf_teste("Versão assinada")),
                    save=True,
                )
                assinar_calibracao_a1(
                    calibracao,
                    certificado_a1=criar_certificado_a1_teste(),
                    senha="senha-teste",
                    usuario=self.usuario,
                )
                calibracao.certificado_arquivo.save(
                    "certificado-alterado.pdf",
                    ContentFile(criar_pdf_teste("Versão alterada")),
                    save=True,
                )

                with self.assertRaisesMessage(ValidationError, "alterado depois da assinatura"):
                    publicar_calibracao_existente(calibracao, usuario=self.usuario)

    def test_publicacao_bloqueia_padrao_vencido_na_data_de_uso(self):
        with tempfile.TemporaryDirectory() as media_root, tempfile.TemporaryDirectory() as documentos_root:
            with override_settings(MEDIA_ROOT=media_root, DOCUMENT_LOCAL_ROOT=documentos_root):
                padrao = Padrao.objects.create(
                    codigo="PAD-011",
                    descricao="Padrão vencido",
                    numero_certificado="RBC-011",
                    vencimento=date(2026, 6, 30),
                    status="vencido",
                )
                self.instrumento.padroes.add(padrao)
                calibracao = Calibracao.objects.create(
                    instrumento=self.instrumento,
                    data_calibracao=date(2026, 7, 18),
                    status="concluida",
                    certificado_numero="CERT-BLOQUEADO-001",
                    origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
                    padroes=padrao.codigo,
                )
                calibracao.certificado_arquivo.save(
                    "certificado-bloqueado.pdf",
                    ContentFile(b"%PDF-1.4\nnao publicar"),
                    save=True,
                )

                with self.assertRaisesMessage(ValidationError, "Publicação bloqueada"):
                    publicar_calibracao_existente(calibracao)

    def test_admin_does_not_allow_manual_certificate_publication(self):
        user = User.objects.create_superuser(
            "certificate-admin", "certificate@example.com", "pass123"
        )
        self.client.force_login(user)
        response = self.client.get(
            reverse("admin:certificados_certificadocalibracao_add")
        )
        self.assertEqual(response.status_code, 403)

    def test_fluxo_admin_assina_revisa_e_publica_certificado(self):
        user = User.objects.create_superuser(
            "certificate-sign-admin",
            "certificate-sign@example.com",
            "pass123",
        )
        with tempfile.TemporaryDirectory() as media_root, tempfile.TemporaryDirectory() as documentos_root:
            with override_settings(
                MEDIA_ROOT=media_root,
                DOCUMENT_LOCAL_ROOT=documentos_root,
                DOCUMENT_STORAGE_MODE="local",
                DOCUMENT_R2_ENABLED=False,
            ):
                padrao = Padrao.objects.create(
                    codigo="PAD-ADMIN-A1",
                    descricao="Padrão do fluxo administrativo",
                    numero_certificado="RBC-ADMIN-A1",
                    vencimento=date(2027, 1, 31),
                    status="valido",
                )
                self.instrumento.padroes.add(padrao)
                calibracao = Calibracao.objects.create(
                    instrumento=self.instrumento,
                    data_calibracao=date(2026, 7, 18),
                    status="concluida",
                    certificado_numero="CERT-ADMIN-A1",
                    origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
                    padroes=padrao.codigo,
                )
                calibracao.certificado_arquivo.save(
                    "certificado-admin.pdf",
                    ContentFile(criar_pdf_teste("Certificado administrativo")),
                    save=True,
                )
                self.client.force_login(user)

                formulario = self.client.get(
                    reverse("admin:calibracao_calibracao_change", args=[calibracao.pk])
                )
                self.assertContains(formulario, "Assinar certificado A1")
                self.assertNotContains(formulario, "Publicar certificado / QR")

                resposta_assinatura = self.client.post(
                    reverse(
                        "admin:calibracao_calibracao_assinar_certificado",
                        args=[calibracao.pk],
                    ),
                    {
                        "certificado_a1": SimpleUploadedFile(
                            "certificado-teste.pfx",
                            criar_certificado_a1_teste(),
                            content_type="application/x-pkcs12",
                        ),
                        "senha": "senha-teste",
                        "confirmacao": "on",
                    },
                )
                self.assertEqual(resposta_assinatura.status_code, 302)

                formulario_assinado = self.client.get(
                    reverse("admin:calibracao_calibracao_change", args=[calibracao.pk])
                )
                self.assertContains(formulario_assinado, "Revisar PDF assinado")
                self.assertContains(formulario_assinado, "Publicar certificado / QR")

                download = self.client.get(
                    reverse(
                        "admin:calibracao_calibracao_download_certificado_assinado",
                        args=[calibracao.pk],
                    )
                )
                self.assertEqual(download.status_code, 200)
                self.assertIn(b"/ETSI.CAdES.detached", b"".join(download.streaming_content))

                publicacao = self.client.post(
                    reverse(
                        "admin:calibracao_calibracao_publicar_certificado",
                        args=[calibracao.pk],
                    )
                )
                self.assertEqual(publicacao.status_code, 302)
                certificado = CertificadoCalibracao.objects.get(numero="CERT-ADMIN-A1")
                self.assertTrue(certificado.publicado)

    def test_admin_localiza_certificado_por_cliente_e_exibe_contexto(self):
        user = User.objects.create_superuser(
            "certificate-search-admin", "search@example.com", "pass123"
        )
        certificado = self.criar_certificado("CERT-EDLAB-001")
        self.client.force_login(user)

        response = self.client.get(
            reverse("admin:certificados_certificadocalibracao_changelist"),
            {"q": "Cliente Teste"},
            HTTP_HOST="127.0.0.1:8000",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, certificado.numero)
        self.assertContains(response, self.cliente.razao_social)
        self.assertContains(response, self.instrumento.codigo)

    def test_lista_geral_exibe_certificado_de_calibracao_especializada(self):
        user = User.objects.create_superuser(
            "calibration-list-admin", "calibration-list@example.com", "pass123"
        )
        calibracao_especializada = CalibracaoTurbidez.objects.create(
            instrumento=self.instrumento,
            cliente=self.cliente,
            data_calibracao=date(2026, 8, 11),
        )
        content_type = ContentType.objects.get_for_model(
            calibracao_especializada, for_concrete_model=False
        )
        certificado = CertificadoCalibracao.objects.create(
            numero=calibracao_especializada.numero_certificado,
            calibracao_content_type=content_type,
            calibracao_object_id=str(calibracao_especializada.pk),
            instrumento=self.instrumento,
            cliente=self.cliente,
            data_calibracao=calibracao_especializada.data_calibracao,
            status=CertificadoCalibracao.Status.EM_REVISAO,
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("admin:calibracao_calibracao_changelist"),
            {"q": "Cliente Teste"},
            HTTP_HOST="127.0.0.1:8000",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Certificados de calibrações especializadas")
        self.assertContains(response, certificado.numero)
        self.assertContains(response, self.instrumento.codigo)

    def test_falha_na_publicacao_preserva_documentos_assinados_preexistentes(self):
        with tempfile.TemporaryDirectory() as media_root, tempfile.TemporaryDirectory() as documentos_root:
            with override_settings(
                MEDIA_ROOT=media_root,
                DOCUMENT_LOCAL_ROOT=documentos_root,
                DOCUMENT_STORAGE_MODE="local",
                DOCUMENT_R2_ENABLED=False,
            ):
                padrao = Padrao.objects.create(
                    codigo="PAD-012",
                    descricao="Padrão para rollback",
                    numero_certificado="RBC-012",
                    vencimento=date(2027, 1, 31),
                    status="valido",
                )
                self.instrumento.padroes.add(padrao)
                self.criar_certificado("CERT-DUPLICADO")
                calibracao = Calibracao.objects.create(
                    instrumento=self.instrumento,
                    data_calibracao=date(2026, 7, 18),
                    status="concluida",
                    certificado_numero="CERT-DUPLICADO",
                    origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
                    padroes=padrao.codigo,
                )
                calibracao.certificado_arquivo.save(
                    "certificado-rollback.pdf",
                    ContentFile(criar_pdf_teste("Rollback controlado")),
                    save=True,
                )
                assinar_calibracao_a1(
                    calibracao,
                    certificado_a1=criar_certificado_a1_teste(),
                    senha="senha-teste",
                    usuario=self.usuario,
                )
                with self.assertRaises(IntegrityError):
                    publicar_calibracao_existente(calibracao, usuario=self.usuario)
                arquivos = [
                    path for path in Path(documentos_root).rglob("*") if path.is_file()
                ]
                self.assertEqual(len(arquivos), 2)
                self.assertEqual(AssinaturaDigitalDocumento.objects.count(), 1)
