from datetime import datetime, timedelta, timezone as datetime_timezone
from io import BytesIO
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from reportlab.pdfgen import canvas
from pyhanko.pdf_utils.reader import PdfFileReader

from .models import AssinaturaDigitalDocumento, DocumentoArquivo
from .services.assinaturas import (
    assinatura_atual_para_pdf,
    assinar_pdf_a1,
    registrar_assinatura_pdf_a1,
)
from .services.documentos import verificar_integridade


def criar_certificado_a1_teste(senha=b"senha-teste"):
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Signatário de Teste")])
    agora = datetime.now(datetime_timezone.utc)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(days=1))
        .not_valid_after(agora + timedelta(days=30))
        .sign(chave, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        name=b"teste-axion",
        key=chave,
        cert=certificado,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(senha),
    )


def criar_pdf_teste(texto="Documento AXION"):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, invariant=1)
    pdf.drawString(72, 760, texto)
    pdf.save()
    return buffer.getvalue()


class AssinaturaDigitalA1Tests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser(
            username="assinante_a1",
            email="assinante@example.com",
            password="senha-login-teste",
        )
        self.a1 = criar_certificado_a1_teste()
        self.pdf = criar_pdf_teste()

    def test_assina_pades_e_verifica_integridade_criptografica(self):
        resultado = assinar_pdf_a1(
            self.pdf,
            self.a1,
            "senha-teste",
            motivo="Teste automatizado AXION",
        )

        self.assertTrue(resultado.pdf_assinado.startswith(b"%PDF"))
        self.assertTrue(resultado.integridade_verificada)
        self.assertEqual(resultado.signatario_nome, "Signatário de Teste")
        self.assertNotEqual(resultado.pdf_assinado, self.pdf)

    def test_senha_incorreta_e_rejeitada_sem_expor_detalhe(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Não foi possível abrir o certificado A1",
        ):
            assinar_pdf_a1(
                self.pdf,
                self.a1,
                "senha-incorreta",
                motivo="Teste automatizado AXION",
            )

    def test_assinatura_visivel_cria_carimbo_na_ultima_pagina(self):
        resultado = assinar_pdf_a1(
            self.pdf,
            self.a1,
            "senha-teste",
            motivo="Teste de aparência AXION",
            assinatura_visivel=True,
        )

        leitor = PdfFileReader(BytesIO(resultado.pdf_assinado))
        assinatura = leitor.embedded_signatures[0]
        self.assertEqual(
            [int(valor) for valor in assinatura.sig_field["/Rect"]],
            [280, 10, 555, 38],
        )
        self.assertIn("/N", assinatura.sig_field["/AP"])
        self.assertEqual(assinatura.evaluate_signature_coverage().name, "ENTIRE_FILE")

    def test_registro_preserva_original_assinado_e_rastreabilidade(self):
        with tempfile.TemporaryDirectory() as documentos_root:
            with override_settings(
                DOCUMENT_LOCAL_ROOT=documentos_root,
                DOCUMENT_STORAGE_MODE="local",
                DOCUMENT_R2_ENABLED=False,
            ):
                assinatura = registrar_assinatura_pdf_a1(
                    objeto=self.usuario,
                    pdf=self.pdf,
                    certificado_a1=self.a1,
                    senha="senha-teste",
                    usuario=self.usuario,
                    nome_arquivo="documento.pdf",
                    revisao_referencia="01",
                    motivo="Teste automatizado AXION",
                )

                self.assertEqual(AssinaturaDigitalDocumento.objects.count(), 1)
                self.assertEqual(DocumentoArquivo.objects.count(), 2)
                self.assertTrue(assinatura.documento_original.imutavel)
                self.assertTrue(assinatura.documento_assinado.imutavel)
                self.assertTrue(assinatura_atual_para_pdf(self.usuario, self.pdf))
                self.assertIsNone(
                    assinatura_atual_para_pdf(self.usuario, criar_pdf_teste("Alterado"))
                )
                integro, motivo = verificar_integridade(assinatura.documento_assinado)
                self.assertTrue(integro)
                self.assertEqual(motivo, "ok")

                nomes_campos = {campo.name for campo in AssinaturaDigitalDocumento._meta.fields}
                self.assertNotIn("senha", nomes_campos)
                self.assertNotIn("certificado_a1", nomes_campos)

                nova_assinatura = registrar_assinatura_pdf_a1(
                    objeto=self.usuario,
                    pdf=self.pdf,
                    certificado_a1=self.a1,
                    senha="senha-teste",
                    usuario=self.usuario,
                    nome_arquivo="documento.pdf",
                    revisao_referencia="01",
                    motivo="Nova assinatura do mesmo documento",
                )
                assinatura.refresh_from_db()
                self.assertEqual(
                    assinatura.status,
                    AssinaturaDigitalDocumento.Status.SUBSTITUIDA,
                )
                self.assertEqual(
                    nova_assinatura.status,
                    AssinaturaDigitalDocumento.Status.VALIDA,
                )
                self.assertEqual(
                    AssinaturaDigitalDocumento.objects.filter(
                        status=AssinaturaDigitalDocumento.Status.VALIDA
                    ).count(),
                    1,
                )
