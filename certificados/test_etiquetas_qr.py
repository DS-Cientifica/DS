from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.test import RequestFactory
from django.urls import reverse
from django.http import HttpResponse

from calibracao.models import Calibracao, Instrumento, NumeroCertificadoEmitido
from clientes.models import Cliente
from certificados.models import CertificadoCalibracao, EtiquetaCalibracaoQR
from certificados.services import _vincular_etiqueta_reservada
from core.public_certificate_middleware import PublicCertificateHostMiddleware


class EtiquetaCalibracaoQRTests(TestCase):
    def setUp(self):
        self.cliente_obj = Cliente.objects.create(
            razao_social="Cliente Etiqueta Ltda",
            nome_empresa="Cliente Etiqueta",
            cnpj="11.111.111/0001-11",
        )
        self.instrumento = Instrumento.objects.create(
            codigo="INST-ETQ-001",
            descricao="Instrumento para etiqueta",
            cliente=self.cliente_obj,
        )
        self.etiqueta = EtiquetaCalibracaoQR.objects.create(
            codigo="A1B2C3",
            lote="PILOTO-2026-01",
            sequencia=1,
        )

    def criar_calibracao_reservada(self):
        calibracao = Calibracao(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 11, 4),
            origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
        )
        calibracao._etiqueta_qr_selecionada_id = self.etiqueta.pk
        calibracao.save()
        self.etiqueta.refresh_from_db()
        return calibracao

    def criar_certificado(self, calibracao, *, publicado=True):
        return CertificadoCalibracao.objects.create(
            numero=calibracao.certificado_numero,
            calibracao_content_type=ContentType.objects.get_for_model(calibracao),
            calibracao_object_id=str(calibracao.pk),
            instrumento=self.instrumento,
            cliente=self.cliente_obj,
            data_calibracao=calibracao.data_calibracao,
            status=CertificadoCalibracao.Status.VALIDO,
            publicado=publicado,
        )

    def test_etiqueta_disponivel_nao_expoe_dados_internos(self):
        resposta = self.client.get(
            reverse("certificados:consulta_etiqueta", args=[self.etiqueta.token_publico])
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "ainda não vinculada")
        self.assertNotContains(resposta, self.cliente_obj.razao_social)
        self.assertNotContains(resposta, "/admin/")

    def test_etiqueta_vinculada_redireciona_somente_para_consulta_publica(self):
        calibracao = self.criar_calibracao_reservada()
        certificado = self.criar_certificado(calibracao)
        _vincular_etiqueta_reservada(certificado, calibracao)
        self.etiqueta.refresh_from_db()

        resposta = self.client.get(
            reverse("certificados:consulta_etiqueta", args=[self.etiqueta.token_publico])
        )
        self.assertRedirects(
            resposta,
            reverse("certificados:consulta", args=[certificado.uuid_publico]),
            fetch_redirect_response=False,
        )

    def test_nao_vincula_certificado_nao_publicado(self):
        calibracao = self.criar_calibracao_reservada()
        certificado = self.criar_certificado(calibracao, publicado=False)
        self.etiqueta.certificado = certificado
        self.etiqueta.status = EtiquetaCalibracaoQR.Status.VINCULADA
        with self.assertRaisesMessage(ValidationError, "Somente certificados publicados"):
            self.etiqueta.full_clean()

    def test_selecao_automatica_gera_numero_novo_sem_consumir_etiqueta(self):
        calibracao = Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 11, 4),
            origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
        )
        self.etiqueta.refresh_from_db()
        self.assertNotEqual(calibracao.certificado_numero, self.etiqueta.codigo)
        self.assertRegex(calibracao.certificado_numero, r"^[A-Z0-9]{6}$")
        self.assertEqual(self.etiqueta.status, EtiquetaCalibracaoQR.Status.DISPONIVEL)
        self.assertIsNone(self.etiqueta.calibracao_object_id)
        self.assertIsNone(self.etiqueta.calibracao_content_type_id)
        self.assertTrue(
            NumeroCertificadoEmitido.objects.filter(
                codigo=calibracao.certificado_numero,
                objeto_id=str(calibracao.pk),
            ).exists()
        )

    def test_calibracao_reserva_exatamente_a_etiqueta_escolhida(self):
        outra_etiqueta = EtiquetaCalibracaoQR.objects.create(
            codigo="Z9Y8X7",
            lote="PILOTO-2026-01",
            sequencia=2,
        )
        calibracao = Calibracao(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 11, 5),
            origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
        )
        calibracao._etiqueta_qr_selecionada_id = outra_etiqueta.pk
        calibracao.save()

        self.etiqueta.refresh_from_db()
        outra_etiqueta.refresh_from_db()
        self.assertEqual(calibracao.certificado_numero, outra_etiqueta.codigo)
        self.assertEqual(self.etiqueta.status, EtiquetaCalibracaoQR.Status.DISPONIVEL)
        self.assertEqual(outra_etiqueta.status, EtiquetaCalibracaoQR.Status.RESERVADA)
        self.assertEqual(outra_etiqueta.calibracao_object_id, str(calibracao.pk))

    def test_calibracao_nao_substitui_etiqueta_escolhida_indisponivel(self):
        outra_etiqueta = EtiquetaCalibracaoQR.objects.create(
            codigo="Q1W2E3",
            lote="PILOTO-2026-01",
            sequencia=2,
            status=EtiquetaCalibracaoQR.Status.AGUARDANDO_IMPRESSAO,
        )
        calibracao = Calibracao(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 11, 5),
            origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
        )
        calibracao._etiqueta_qr_selecionada_id = outra_etiqueta.pk

        with self.assertRaisesMessage(ValidationError, "não está mais disponível"):
            calibracao.save()

        self.etiqueta.refresh_from_db()
        self.assertEqual(self.etiqueta.status, EtiquetaCalibracaoQR.Status.DISPONIVEL)
        self.assertFalse(Calibracao.objects.filter(pk=calibracao.pk).exists())

    def test_admin_calibracao_exibe_selecao_da_etiqueta_fisica(self):
        usuario = User.objects.create_superuser(
            username="admin-selecao-etiqueta",
            email="admin-selecao-etiqueta@example.com",
            password="senha-teste",
        )
        self.client.force_login(usuario)

        resposta = self.client.get(reverse("admin:calibracao_calibracao_add"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Forma de definição do número e da etiqueta QR")
        self.assertContains(resposta, "Gerar novo número de certificado")
        self.assertContains(resposta, "Escolher uma etiqueta física já criada")
        self.assertContains(resposta, "Pesquisar etiqueta física QR")
        self.assertContains(resposta, "js-etiqueta-qr-select")
        self.assertContains(resposta, "admin_calibracao_etiqueta_qr.js")
        self.assertContains(resposta, self.etiqueta.codigo)
        self.assertContains(resposta, self.etiqueta.lote)

    def test_formulario_manual_exige_e_reserva_a_etiqueta_pesquisada(self):
        from calibracao.admin import CalibracaoAdminForm

        dados = {
            "instrumento": str(self.instrumento.pk),
            "data_calibracao": "04/11/2026",
            "status": "aberta",
            "resultado": "aprovado",
            "local_calibracao": "laboratorio",
            "origem_certificado": Calibracao.OrigemCertificado.EMITIDO_DS,
            "modo_etiqueta_qr": "manual",
        }
        sem_etiqueta = CalibracaoAdminForm(data=dados)
        self.assertFalse(sem_etiqueta.is_valid())
        self.assertIn("etiqueta_qr_selecionada", sem_etiqueta.errors)

        com_etiqueta = CalibracaoAdminForm(
            data={**dados, "etiqueta_qr_selecionada": str(self.etiqueta.pk)}
        )
        self.assertTrue(com_etiqueta.is_valid(), com_etiqueta.errors)
        calibracao = com_etiqueta.save()
        self.etiqueta.refresh_from_db()
        self.assertEqual(calibracao.certificado_numero, self.etiqueta.codigo)
        self.assertEqual(self.etiqueta.status, EtiquetaCalibracaoQR.Status.RESERVADA)

    def test_formulario_automatico_ignora_etiqueta_enviada_e_gera_numero_novo(self):
        from calibracao.admin import CalibracaoAdminForm

        formulario = CalibracaoAdminForm(
            data={
                "instrumento": str(self.instrumento.pk),
                "data_calibracao": "04/11/2026",
                "status": "aberta",
                "resultado": "aprovado",
                "local_calibracao": "laboratorio",
                "origem_certificado": Calibracao.OrigemCertificado.EMITIDO_DS,
                "modo_etiqueta_qr": "automatico",
                "etiqueta_qr_selecionada": str(self.etiqueta.pk),
            }
        )

        self.assertTrue(formulario.is_valid(), formulario.errors)
        calibracao = formulario.save()
        self.etiqueta.refresh_from_db()
        self.assertNotEqual(calibracao.certificado_numero, self.etiqueta.codigo)
        self.assertEqual(self.etiqueta.status, EtiquetaCalibracaoQR.Status.DISPONIVEL)

    @override_settings(
        PUBLIC_CERTIFICATE_BASE_URL="https://certificados.dscientifica.com.br"
    )
    @patch("certificados.admin.gerar_qr_svg", return_value="<svg></svg>")
    def test_impressao_respeita_60_por_30_mm_e_qr_de_20_mm(self, gerar_qr):
        usuario = User.objects.create_superuser(
            username="admin-impressao-etiqueta",
            email="admin-impressao@example.com",
            password="senha-teste",
        )
        self.client.force_login(usuario)
        resposta = self.client.post(
            reverse("admin:certificados_etiquetacalibracaoqr_changelist"),
            {
                "action": "imprimir_etiquetas",
                "_selected_action": [str(self.etiqueta.pk)],
            },
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "width:60mm")
        self.assertContains(resposta, "height:30mm")
        self.assertContains(resposta, "width:20mm")
        self.assertContains(resposta, "height:20mm")
        self.assertNotContains(resposta, "www.dscientifica.com.br")
        self.assertContains(resposta, "(11) 98859-9577")
        self.assertContains(resposta, ".datas{min-height:0;display:grid")
        self.assertContains(resposta, ".contato-item{grid-column:2")
        self.assertContains(resposta, self.etiqueta.codigo)
        self.assertContains(resposta, "<svg", html=False)
        self.assertEqual(
            gerar_qr.call_args.args[0],
            "https://certificados.dscientifica.com.br/etiquetas/"
            f"{self.etiqueta.token_publico}/",
        )

    @override_settings(
        PUBLIC_CERTIFICATE_BASE_URL="https://certificados.dscientifica.com.br"
    )
    @patch("certificados.admin.gerar_qr_svg", return_value="<svg></svg>")
    def test_etiqueta_individual_do_certificado_usa_layout_fisico(self, gerar_qr):
        usuario = User.objects.create_superuser(
            username="admin-etiqueta-individual",
            email="admin-etiqueta-individual@example.com",
            password="senha-teste",
        )
        self.client.force_login(usuario)
        calibracao = self.criar_calibracao_reservada()
        certificado = self.criar_certificado(calibracao)

        resposta = self.client.get(
            reverse(
                "admin:certificados_certificadocalibracao_etiqueta",
                args=[certificado.pk],
            )
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "width:60mm")
        self.assertContains(resposta, "height:30mm")
        self.assertContains(resposta, "width:20mm")
        self.assertContains(resposta, "height:20mm")
        self.assertNotContains(resposta, "www.dscientifica.com.br")
        self.assertContains(resposta, "(11) 98859-9577")
        self.assertContains(resposta, ".datas{min-height:0;display:grid")
        self.assertContains(resposta, ".contato-item{grid-column:2")
        self.assertContains(resposta, "size:60mm 30mm")
        self.assertContains(resposta, certificado.numero, count=4)
        self.assertContains(resposta, self.instrumento.codigo)
        self.assertNotContains(resposta, certificado.codigo_curto)
        self.assertNotContains(resposta, "qr-url")
        self.assertEqual(
            gerar_qr.call_args.args[0],
            "https://certificados.dscientifica.com.br/verificar/"
            f"{certificado.uuid_publico}/",
        )

    def test_geracao_de_lote_exige_apply_e_e_idempotente(self):
        simulacao = StringIO()
        call_command(
            "gerar_lote_etiquetas_qr",
            lote="LOTE-TESTE",
            quantidade=5,
            stdout=simulacao,
        )
        self.assertFalse(EtiquetaCalibracaoQR.objects.filter(lote="LOTE-TESTE").exists())
        self.assertIn("SIMULAÇÃO", simulacao.getvalue())

        call_command(
            "gerar_lote_etiquetas_qr",
            lote="LOTE-TESTE",
            quantidade=5,
            apply=True,
            stdout=StringIO(),
        )
        self.assertEqual(EtiquetaCalibracaoQR.objects.filter(lote="LOTE-TESTE").count(), 5)
        self.assertEqual(
            set(
                EtiquetaCalibracaoQR.objects.filter(lote="LOTE-TESTE").values_list(
                    "status", flat=True
                )
            ),
            {EtiquetaCalibracaoQR.Status.AGUARDANDO_IMPRESSAO},
        )
        codigos = list(
            EtiquetaCalibracaoQR.objects.filter(lote="LOTE-TESTE").values_list("codigo", flat=True)
        )
        self.assertEqual(len(codigos), len(set(codigos)))
        for codigo in codigos:
            self.assertRegex(codigo, r"^(?=(?:.*[A-Z]){3})(?=(?:.*\d){3})[A-Z0-9]{6}$")

        call_command(
            "gerar_lote_etiquetas_qr",
            lote="LOTE-TESTE",
            quantidade=5,
            apply=True,
            stdout=StringIO(),
        )
        self.assertEqual(EtiquetaCalibracaoQR.objects.filter(lote="LOTE-TESTE").count(), 5)

        call_command(
            "ativar_lote_etiquetas_qr",
            lote="LOTE-TESTE",
            stdout=StringIO(),
        )
        self.assertFalse(
            EtiquetaCalibracaoQR.objects.filter(
                lote="LOTE-TESTE",
                status=EtiquetaCalibracaoQR.Status.DISPONIVEL,
            ).exists()
        )
        call_command(
            "ativar_lote_etiquetas_qr",
            lote="LOTE-TESTE",
            apply=True,
            stdout=StringIO(),
        )
        self.assertEqual(
            EtiquetaCalibracaoQR.objects.filter(
                lote="LOTE-TESTE",
                status=EtiquetaCalibracaoQR.Status.DISPONIVEL,
            ).count(),
            5,
        )

    def test_lote_ativado_so_e_consumido_por_escolha_manual(self):
        self.etiqueta.status = EtiquetaCalibracaoQR.Status.AGUARDANDO_IMPRESSAO
        self.etiqueta.save(update_fields=("status", "atualizado_em"))
        call_command(
            "gerar_lote_etiquetas_qr",
            lote="LOTE-INATIVO",
            quantidade=2,
            apply=True,
            stdout=StringIO(),
        )
        codigos_lote = set(
            EtiquetaCalibracaoQR.objects.filter(lote="LOTE-INATIVO").values_list(
                "codigo", flat=True
            )
        )
        calibracao_sem_lote = Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 11, 4),
            origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
        )
        self.assertNotIn(calibracao_sem_lote.certificado_numero, codigos_lote)

        call_command(
            "ativar_lote_etiquetas_qr",
            lote="LOTE-INATIVO",
            apply=True,
            stdout=StringIO(),
        )
        etiqueta_escolhida = EtiquetaCalibracaoQR.objects.filter(
            lote="LOTE-INATIVO",
            status=EtiquetaCalibracaoQR.Status.DISPONIVEL,
        ).order_by("sequencia").first()
        calibracao_automatica = Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 11, 5),
            origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
        )
        self.assertNotIn(calibracao_automatica.certificado_numero, codigos_lote)
        etiqueta_escolhida.refresh_from_db()
        self.assertEqual(etiqueta_escolhida.status, EtiquetaCalibracaoQR.Status.DISPONIVEL)

        calibracao_manual = Calibracao(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 11, 6),
            origem_certificado=Calibracao.OrigemCertificado.EMITIDO_DS,
        )
        calibracao_manual._etiqueta_qr_selecionada_id = etiqueta_escolhida.pk
        calibracao_manual.save()
        etiqueta_escolhida.refresh_from_db()
        self.assertEqual(calibracao_manual.certificado_numero, etiqueta_escolhida.codigo)
        self.assertEqual(etiqueta_escolhida.status, EtiquetaCalibracaoQR.Status.RESERVADA)

    def test_certificado_de_terceiro_nao_consume_etiqueta_ds(self):
        calibracao = Calibracao.objects.create(
            instrumento=self.instrumento,
            data_calibracao=date(2026, 11, 4),
            origem_certificado=Calibracao.OrigemCertificado.EMITIDO_TERCEIRO,
        )
        self.etiqueta.refresh_from_db()
        self.assertNotEqual(calibracao.certificado_numero, self.etiqueta.codigo)
        self.assertEqual(self.etiqueta.status, EtiquetaCalibracaoQR.Status.DISPONIVEL)

    def test_admin_superusuario_gera_e_ativa_lote_com_rastreabilidade(self):
        usuario = User.objects.create_superuser(
            username="admin-lotes-etiqueta",
            email="admin-lotes@example.com",
            password="senha-teste",
        )
        self.client.force_login(usuario)
        url = reverse("admin:certificados_etiquetacalibracaoqr_lotes")
        pagina = self.client.get(url)
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "PILOTO-2026-01")
        self.assertContains(pagina, "certificados futuros da aba Calibração")

        resposta = self.client.post(
            url,
            {
                "acao": "gerar",
                "lote": "PILOTO-ADMIN",
                "quantidade": "5",
                "confirmar": "sim",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        lote = EtiquetaCalibracaoQR.objects.filter(lote="PILOTO-ADMIN")
        self.assertEqual(lote.count(), 5)
        self.assertEqual(
            set(lote.values_list("status", flat=True)),
            {EtiquetaCalibracaoQR.Status.AGUARDANDO_IMPRESSAO},
        )
        self.assertEqual(set(lote.values_list("criada_por", flat=True)), {usuario.pk})

        resposta = self.client.post(
            url,
            {
                "acao": "ativar",
                "lote": "PILOTO-ADMIN",
                "confirmar": "sim",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(
            set(lote.values_list("status", flat=True)),
            {EtiquetaCalibracaoQR.Status.DISPONIVEL},
        )
        self.assertEqual(set(lote.values_list("ativada_por", flat=True)), {usuario.pk})
        self.assertFalse(lote.filter(ativada_em__isnull=True).exists())

    def test_admin_lotes_exige_superusuario_e_confirmacao(self):
        operador = User.objects.create_user(
            username="operador-lotes-etiqueta",
            password="senha-teste",
            is_staff=True,
        )
        self.client.force_login(operador)
        url = reverse("admin:certificados_etiquetacalibracaoqr_lotes")
        self.assertEqual(self.client.get(url).status_code, 403)

        superusuario = User.objects.create_superuser(
            username="supervisor-lotes-etiqueta",
            email="supervisor-lotes@example.com",
            password="senha-teste",
        )
        self.client.force_login(superusuario)
        resposta = self.client.post(
            url,
            {"acao": "gerar", "lote": "SEM-CONFIRMACAO", "quantidade": "5"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(
            EtiquetaCalibracaoQR.objects.filter(lote="SEM-CONFIRMACAO").exists()
        )


class DominioPublicoCertificadosTests(TestCase):
    host_publico = "certificados.exemplo.com.br"

    @override_settings(
        ALLOWED_HOSTS=["testserver", "certificados.exemplo.com.br"],
        PUBLIC_CERTIFICATE_HOSTS=["certificados.exemplo.com.br"],
    )
    def test_dominio_publico_bloqueia_admin_antes_do_login(self):
        resposta = self.client.get("/admin/login/", HTTP_HOST=self.host_publico)
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(resposta["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertEqual(resposta["X-Frame-Options"], "DENY")

    @override_settings(
        ALLOWED_HOSTS=["testserver", "certificados.exemplo.com.br"],
        PUBLIC_CERTIFICATE_HOSTS=["certificados.exemplo.com.br"],
    )
    def test_dominio_publico_permite_somente_rota_de_etiqueta(self):
        etiqueta = EtiquetaCalibracaoQR.objects.create(
            codigo="D4E5F6",
            lote="SEGURANCA",
            sequencia=1,
        )
        resposta = self.client.get(
            reverse("certificados:consulta_etiqueta", args=[etiqueta.token_publico]),
            HTTP_HOST=self.host_publico,
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("default-src 'none'", resposta["Content-Security-Policy"])
        self.assertEqual(resposta["Referrer-Policy"], "no-referrer")

    @override_settings(
        ALLOWED_HOSTS=["testserver", "certificados.exemplo.com.br"],
        PUBLIC_CERTIFICATE_HOSTS=["certificados.exemplo.com.br"],
    )
    def test_dominio_publico_libera_somente_o_logo_institucional(self):
        middleware = PublicCertificateHostMiddleware(
            lambda _request: HttpResponse("arquivo-estatico", status=200)
        )
        factory = RequestFactory()

        logo = middleware(
            factory.get(
                "/static/img/logo_ds.png",
                HTTP_HOST=self.host_publico,
            )
        )
        outro_arquivo = middleware(
            factory.get(
                "/static/css/custom.css",
                HTTP_HOST=self.host_publico,
            )
        )

        self.assertEqual(logo.status_code, 200)
        self.assertIn("img-src 'self' data:", logo["Content-Security-Policy"])
        self.assertEqual(outro_arquivo.status_code, 404)

    @override_settings(
        ALLOWED_HOSTS=["testserver", "certificados.exemplo.com.br"],
        PUBLIC_CERTIFICATE_HOSTS=["certificados.exemplo.com.br"],
    )
    def test_host_interno_continua_com_login_normal(self):
        resposta = self.client.get("/admin/login/", HTTP_HOST="testserver")
        self.assertEqual(resposta.status_code, 200)
