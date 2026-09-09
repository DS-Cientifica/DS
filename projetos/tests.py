from io import StringIO

from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente, ContatoCliente
from comercial.models import Prospecto
from projetos.marketing import preparar_envios_campanha, processar_envio_campanha
from projetos.management.commands.preencher_projeto_retrofit_banho import (
    ACCEPTANCE,
    CHECKS,
    COSTS,
    MATERIALS,
    PROJECT_CODE,
    RISKS,
    STAGES,
)
from projetos.models import (
    CampanhaMarketing,
    EnvioCampanha,
    MidiaMarketing,
    Projeto,
    ProjetoCusto,
    ProjetoTarefa,
    ProjetoTeste,
)


class PreencherProjetoRetrofitBanhoCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="diego",
            email="diego@example.com",
            password="test-123",
        )
        self.cliente_ds = Cliente.objects.create(
            codigo="CL-DS",
            razao_social="DS Cientifica",
            nome_empresa="DS Cientifica",
            cnpj="63.669.660/0001-80",
        )

    def test_dry_run_nao_cria_projeto(self):
        output = StringIO()

        call_command("preencher_projeto_retrofit_banho", stdout=output)

        self.assertFalse(Projeto.objects.filter(codigo=PROJECT_CODE).exists())
        self.assertIn("Nenhum dado foi gravado", output.getvalue())

    def test_apply_cria_projeto_e_registros(self):
        call_command("preencher_projeto_retrofit_banho", "--apply", stdout=StringIO())

        projeto = Projeto.objects.get(codigo=PROJECT_CODE)
        self.assertEqual(projeto.nome, "Retrofit de banho termostatizado")
        self.assertEqual(projeto.tipo, "retrofit")
        self.assertEqual(projeto.status, "em_desenvolvimento")
        self.assertEqual(projeto.prioridade, "alta")
        self.assertEqual(projeto.responsavel, self.user)
        self.assertEqual(projeto.cliente, self.cliente_ds)
        self.assertEqual(ProjetoTarefa.objects.filter(projeto=projeto).count(), len(STAGES))
        self.assertEqual(ProjetoCusto.objects.filter(projeto=projeto).count(), len(MATERIALS) + len(COSTS))
        self.assertEqual(ProjetoTeste.objects.filter(projeto=projeto, tipo_teste__startswith="Risco ").count(), len(RISKS))
        self.assertEqual(ProjetoTeste.objects.filter(projeto=projeto, tipo_teste__startswith="Verificacao ").count(), len(CHECKS))
        self.assertEqual(ProjetoTeste.objects.filter(projeto=projeto, tipo_teste__startswith="Criterio de aceite ").count(), len(ACCEPTANCE))

    def test_apply_e_idempotente(self):
        call_command("preencher_projeto_retrofit_banho", "--apply", stdout=StringIO())
        call_command("preencher_projeto_retrofit_banho", "--apply", stdout=StringIO())

        projeto = Projeto.objects.get(codigo=PROJECT_CODE)
        self.assertEqual(Projeto.objects.filter(codigo=PROJECT_CODE).count(), 1)
        self.assertEqual(ProjetoTarefa.objects.filter(projeto=projeto).count(), len(STAGES))
        self.assertEqual(ProjetoCusto.objects.filter(projeto=projeto).count(), len(MATERIALS) + len(COSTS))
        self.assertEqual(
            ProjetoTeste.objects.filter(projeto=projeto).count(),
            len(RISKS) + len(CHECKS) + len(ACCEPTANCE),
        )

    def test_preserva_registro_manual_nao_relacionado(self):
        projeto = Projeto.objects.create(codigo=PROJECT_CODE, nome="Nome antigo")
        ProjetoTarefa.objects.create(
            projeto=projeto,
            titulo="Tarefa manual",
            descricao="Nao deve ser removida.",
            responsavel=self.user,
        )

        call_command("preencher_projeto_retrofit_banho", "--apply", stdout=StringIO())

        self.assertTrue(ProjetoTarefa.objects.filter(projeto=projeto, titulo="Tarefa manual").exists())


class CampanhaMarketingEnvioTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("marketing", password="test-123")
        self.cliente = Cliente.objects.create(
            codigo="CL-MKT",
            razao_social="Cliente Marketing",
            nome_empresa="Cliente Marketing",
            cnpj="11.111.111/0001-11",
        )
        self.contato = ContatoCliente.objects.create(
            cliente=self.cliente,
            nome="Contato Autorizado",
            email="contato@example.com",
            telefone="(11) 99999-9999",
            marketing_email_autorizado=True,
            marketing_whatsapp_autorizado=True,
            marketing_base_legal="consentimento",
            marketing_origem="Formulário MKT-OPTIN-001",
        )

    def criar_campanha(self, **campos):
        dados = {
            "nome": "Campanha teste",
            "status": "aprovada",
            "enviar_email": True,
            "assunto_email": "Assunto de teste",
            "conteudo_email": "Conteúdo de teste",
            "aprovada_por": self.usuario,
            "aprovada_em": timezone.now(),
            "autorizar_disparo": True,
        }
        dados.update(campos)
        campanha = CampanhaMarketing.objects.create(**dados)
        campanha.destinatarios.add(self.contato)
        return campanha

    def test_campanha_nao_aprovada_nao_pode_autorizar_disparo(self):
        campanha = CampanhaMarketing(
            nome="Rascunho",
            status="planejada",
            enviar_email=True,
            assunto_email="Assunto",
            conteudo_email="Conteúdo",
            autorizar_disparo=True,
        )

        with self.assertRaises(ValidationError):
            campanha.full_clean()

    def test_contato_exige_evidencia_para_autorizar_marketing(self):
        contato = ContatoCliente(
            cliente=self.cliente,
            nome="Sem evidência",
            email="sem-evidencia@example.com",
            marketing_email_autorizado=True,
        )

        with self.assertRaises(ValidationError):
            contato.full_clean()

    def test_prospecto_exige_evidencia_para_autorizar_email(self):
        prospecto = Prospecto(
            razao_social="Prospect sem evidência",
            email="prospect@example.com",
            marketing_email_autorizado=True,
        )

        with self.assertRaises(ValidationError):
            prospecto.full_clean()

    def test_selecionar_todos_inclui_somente_prospectos_autorizados(self):
        autorizado = Prospecto.objects.create(
            razao_social="Prospect autorizado",
            contato_nome="Comprador",
            email="comprador@prospect.example",
            marketing_email_autorizado=True,
            marketing_base_legal="consentimento",
            marketing_origem="Formulário PROS-OPTIN-001",
        )
        Prospecto.objects.create(
            razao_social="Prospect sem autorização",
            email="sem-autorizacao@prospect.example",
        )
        descartado = Prospecto.objects.create(
            razao_social="Prospect descartado",
            email="descartado@prospect.example",
            status="descartado",
            marketing_email_autorizado=True,
            marketing_base_legal="consentimento",
            marketing_origem="Formulário PROS-OPTIN-002",
        )
        campanha = self.criar_campanha(
            enviar_todos_prospectos_email_autorizados=True,
        )

        resultado = preparar_envios_campanha(campanha.pk)

        self.assertEqual(resultado["criados"], 2)
        self.assertTrue(
            EnvioCampanha.objects.filter(campanha=campanha, prospecto=autorizado).exists()
        )
        self.assertFalse(
            EnvioCampanha.objects.filter(campanha=campanha, prospecto=descartado).exists()
        )

    def test_destino_duplicado_entre_cliente_e_prospecto_e_ignorado(self):
        prospecto = Prospecto.objects.create(
            razao_social="Prospect duplicado",
            email=self.contato.email,
            marketing_email_autorizado=True,
            marketing_base_legal="consentimento",
            marketing_origem="Formulário PROS-OPTIN-003",
        )
        campanha = self.criar_campanha()
        campanha.destinatarios_prospectos.add(prospecto)

        resultado = preparar_envios_campanha(campanha.pk)

        self.assertEqual(resultado["criados"], 1)
        self.assertEqual(resultado["ignorados"], 1)
        self.assertEqual(EnvioCampanha.objects.filter(campanha=campanha).count(), 1)

    def test_prepara_fila_multicanal_de_forma_idempotente(self):
        campanha = self.criar_campanha(
            enviar_whatsapp=True,
            whatsapp_template_nome="campanha_ds_cientifica",
            mensagem_whatsapp_referencia="Oferta técnica. Responda SAIR para cancelar.",
        )

        primeiro = preparar_envios_campanha(campanha.pk)
        segundo = preparar_envios_campanha(campanha.pk)

        self.assertEqual(primeiro["criados"], 2)
        self.assertEqual(segundo["existentes"], 2)
        self.assertEqual(EnvioCampanha.objects.filter(campanha=campanha).count(), 2)
        envio_whatsapp = EnvioCampanha.objects.get(campanha=campanha, canal="whatsapp")
        self.assertEqual(envio_whatsapp.destinatario_endereco, "5511999999999")

    def test_nao_duplica_destino_do_mesmo_canal(self):
        outro_contato = ContatoCliente.objects.create(
            cliente=self.cliente,
            nome="Outro contato no mesmo número",
            email="outro@example.com",
            telefone=self.contato.telefone,
            marketing_email_autorizado=True,
            marketing_whatsapp_autorizado=True,
            marketing_base_legal="consentimento",
            marketing_origem="Formulário MKT-OPTIN-002",
        )
        campanha = self.criar_campanha(
            enviar_whatsapp=True,
            whatsapp_template_nome="campanha_ds_cientifica",
        )
        campanha.destinatarios.add(outro_contato)

        resultado = preparar_envios_campanha(campanha.pk)

        self.assertEqual(resultado["criados"], 3)
        self.assertEqual(resultado["ignorados"], 1)
        self.assertEqual(EnvioCampanha.objects.filter(campanha=campanha, canal="email").count(), 2)
        self.assertEqual(EnvioCampanha.objects.filter(campanha=campanha, canal="whatsapp").count(), 1)

    def test_contato_sem_evidencia_de_autorizacao_e_ignorado(self):
        self.contato.marketing_origem = ""
        self.contato.save(update_fields=("marketing_origem",))
        campanha = self.criar_campanha()

        resultado = preparar_envios_campanha(campanha.pk)

        self.assertEqual(resultado["criados"], 0)
        self.assertEqual(resultado["ignorados"], 1)
        self.assertFalse(EnvioCampanha.objects.filter(campanha=campanha).exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_processa_email_e_registra_envio(self):
        campanha = self.criar_campanha()
        preparar_envios_campanha(campanha.pk)
        envio = EnvioCampanha.objects.get(campanha=campanha, canal="email")

        resultado = processar_envio_campanha(envio.pk)

        envio.refresh_from_db()
        self.assertEqual(resultado, "enviado")
        self.assertEqual(envio.status, "enviado")
        self.assertEqual(envio.tentativas, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("solicitando o cancelamento", mail.outbox[0].body)
        html = mail.outbox[0].alternatives[0].content
        self.assertIn("Equipe DS Científica", html)
        self.assertIn("cid:logo-ds@axion", html)

    def test_midia_imagem_rejeita_arquivo_pdf(self):
        campanha = CampanhaMarketing.objects.create(nome="Campanha com mídia inválida")
        midia = MidiaMarketing(
            campanha=campanha,
            titulo="Arquivo incompatível",
            tipo="imagem",
            canal_sugerido="email",
            arquivo=SimpleUploadedFile("nota.pdf", b"%PDF-1.4\n", content_type="application/pdf"),
        )

        with self.assertRaises(ValidationError):
            midia.full_clean()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_revogacao_antes_do_processamento_cancela_envio(self):
        campanha = self.criar_campanha()
        preparar_envios_campanha(campanha.pk)
        envio = EnvioCampanha.objects.get(campanha=campanha, canal="email")
        self.contato.marketing_revogado_em = timezone.now()
        self.contato.marketing_email_autorizado = False
        self.contato.save(update_fields=("marketing_revogado_em", "marketing_email_autorizado"))

        resultado = processar_envio_campanha(envio.pk)

        envio.refresh_from_db()
        self.assertEqual(resultado, "cancelado")
        self.assertEqual(envio.status, "cancelado")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_revogacao_do_prospecto_antes_do_processamento_cancela_envio(self):
        prospecto = Prospecto.objects.create(
            razao_social="Prospect autorizado",
            email="prospect-revogado@example.com",
            marketing_email_autorizado=True,
            marketing_base_legal="consentimento",
            marketing_origem="Formulário PROS-OPTIN-004",
        )
        campanha = CampanhaMarketing.objects.create(
            nome="Campanha para prospect",
            status="aprovada",
            enviar_email=True,
            assunto_email="Assunto",
            conteudo_email="Conteúdo",
            aprovada_por=self.usuario,
            aprovada_em=timezone.now(),
            autorizar_disparo=True,
        )
        campanha.destinatarios_prospectos.add(prospecto)
        preparar_envios_campanha(campanha.pk)
        envio = EnvioCampanha.objects.get(campanha=campanha, prospecto=prospecto)
        prospecto.marketing_email_autorizado = False
        prospecto.marketing_revogado_em = timezone.now()
        prospecto.save(
            update_fields=("marketing_email_autorizado", "marketing_revogado_em")
        )

        resultado = processar_envio_campanha(envio.pk)

        envio.refresh_from_db()
        self.assertEqual(resultado, "cancelado")
        self.assertEqual(envio.status, "cancelado")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_processa_email_individual_para_prospecto_autorizado(self):
        prospecto = Prospecto.objects.create(
            razao_social="Prospect autorizado",
            contato_nome="Responsável de compras",
            email="prospect-envio@example.com",
            marketing_email_autorizado=True,
            marketing_base_legal="consentimento",
            marketing_origem="Formulário PROS-OPTIN-006",
        )
        campanha = CampanhaMarketing.objects.create(
            nome="Campanha para prospect autorizado",
            status="aprovada",
            enviar_email=True,
            assunto_email="Assunto para prospect",
            conteudo_email="Conteúdo para prospect",
            aprovada_por=self.usuario,
            aprovada_em=timezone.now(),
            autorizar_disparo=True,
        )
        campanha.destinatarios_prospectos.add(prospecto)
        preparar_envios_campanha(campanha.pk)
        envio = EnvioCampanha.objects.get(campanha=campanha, prospecto=prospecto)

        resultado = processar_envio_campanha(envio.pk)

        envio.refresh_from_db()
        self.assertEqual(resultado, "enviado")
        self.assertEqual(envio.status, "enviado")
        self.assertEqual(mail.outbox[0].to, ["prospect-envio@example.com"])
        self.assertNotIn(self.contato.email, mail.outbox[0].to)

    @override_settings(WHATSAPP_ACCESS_TOKEN="", WHATSAPP_PHONE_NUMBER_ID="")
    def test_whatsapp_sem_credenciais_falha_sem_disparo(self):
        campanha = self.criar_campanha(
            enviar_email=False,
            enviar_whatsapp=True,
            whatsapp_template_nome="campanha_ds_cientifica",
        )
        preparar_envios_campanha(campanha.pk)
        envio = EnvioCampanha.objects.get(campanha=campanha, canal="whatsapp")

        resultado = processar_envio_campanha(envio.pk)

        envio.refresh_from_db()
        self.assertEqual(resultado, "falha")
        self.assertIn("ainda não está configurada", envio.erro)

    def test_admin_separa_campanha_disparo_e_midias_em_abas(self):
        self.usuario.is_staff = True
        self.usuario.is_superuser = True
        self.usuario.save(update_fields=("is_staff", "is_superuser"))
        campanha = CampanhaMarketing.objects.create(nome="Campanha no admin")
        self.client.force_login(self.usuario)

        resposta = self.client.get(
            reverse("admin:projetos_campanhamarketing_change", args=(campanha.pk,))
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'data-tab-target="dados-campanha"')
        self.assertContains(resposta, 'data-tab-target="disparo-campanha"')
        self.assertContains(resposta, 'data-tab-target="midias-campanha"')
        self.assertContains(resposta, "Duplicar campanha")

        preview = self.client.get(
            reverse("admin:projetos_campanhamarketing_visualizar_email", args=(campanha.pk,))
        )
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Equipe DS Científica")
        self.assertContains(preview, static("img/logo_ds.png"))

    def test_admin_exibe_controle_de_autorizacao_no_prospecto(self):
        self.usuario.is_staff = True
        self.usuario.is_superuser = True
        self.usuario.save(update_fields=("is_staff", "is_superuser"))
        prospecto = Prospecto.objects.create(
            razao_social="Prospect no admin",
            email="prospect-admin@example.com",
        )
        self.client.force_login(self.usuario)

        resposta = self.client.get(
            reverse("admin:comercial_prospecto_change", args=(prospecto.pk,))
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Autoriza prospecção por e-mail")
        self.assertContains(resposta, "Origem/evidência da autorização")

    def test_admin_autoriza_todos_os_prospectos_elegiveis_em_lote_sem_enviar(self):
        self.usuario.is_staff = True
        self.usuario.is_superuser = True
        self.usuario.save(update_fields=("is_staff", "is_superuser"))
        elegivel = Prospecto.objects.create(
            razao_social="Prospect elegível",
            email="elegivel-lote@example.com",
        )
        sem_email = Prospecto.objects.create(razao_social="Prospect sem e-mail")
        revogado = Prospecto.objects.create(
            razao_social="Prospect revogado",
            email="revogado-lote@example.com",
            marketing_revogado_em=timezone.now(),
        )
        self.client.force_login(self.usuario)
        url = reverse("admin:comercial_prospecto_changelist")

        confirmacao = self.client.post(
            url,
            {
                "action": "autorizar_email_em_lote",
                "_selected_action": str(elegivel.pk),
                "select_across": "1",
                "index": "0",
            },
        )

        self.assertEqual(confirmacao.status_code, 200)
        self.assertContains(confirmacao, "Revisão obrigatória antes da autorização")
        self.assertContains(confirmacao, "1</strong> elegível")

        resposta = self.client.post(
            url,
            {
                "action": "autorizar_email_em_lote",
                "_selected_action": str(elegivel.pk),
                "select_across": "1",
                "confirmar_autorizacao_lote": "1",
                "base_legal": "consentimento",
                "origem_evidencia": "Formulário revisado PROS-LOTE-001",
                "referencia_analise": "",
                "observacoes": "Lote piloto.",
                "confirmar": "on",
            },
        )

        self.assertEqual(resposta.status_code, 302)
        elegivel.refresh_from_db()
        sem_email.refresh_from_db()
        revogado.refresh_from_db()
        self.assertTrue(elegivel.marketing_email_autorizado)
        self.assertEqual(elegivel.marketing_base_legal, "consentimento")
        self.assertEqual(elegivel.marketing_autorizado_por, self.usuario)
        self.assertIsNotNone(elegivel.marketing_autorizado_em)
        self.assertIsNotNone(elegivel.marketing_lote_autorizacao)
        self.assertFalse(sem_email.marketing_email_autorizado)
        self.assertFalse(revogado.marketing_email_autorizado)
        self.assertFalse(EnvioCampanha.objects.filter(prospecto=elegivel).exists())

    def test_admin_exige_referencia_para_legitimo_interesse_em_lote(self):
        self.usuario.is_staff = True
        self.usuario.is_superuser = True
        self.usuario.save(update_fields=("is_staff", "is_superuser"))
        prospecto = Prospecto.objects.create(
            razao_social="Prospect legítimo interesse",
            email="legitimo-interesse@example.com",
        )
        self.client.force_login(self.usuario)

        resposta = self.client.post(
            reverse("admin:comercial_prospecto_changelist"),
            {
                "action": "autorizar_email_em_lote",
                "_selected_action": str(prospecto.pk),
                "select_across": "0",
                "confirmar_autorizacao_lote": "1",
                "base_legal": "legitimo_interesse",
                "origem_evidencia": "Lista comercial revisada",
                "referencia_analise": "",
                "observacoes": "",
                "confirmar": "on",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(
            resposta,
            "Informe a referência do teste de balanceamento/legítimo interesse.",
        )
        prospecto.refresh_from_db()
        self.assertFalse(prospecto.marketing_email_autorizado)

    def test_admin_duplica_campanha_sem_aprovacao_disparo_ou_historico(self):
        self.usuario.is_staff = True
        self.usuario.is_superuser = True
        self.usuario.save(update_fields=("is_staff", "is_superuser"))
        campanha = self.criar_campanha(
            enviar_whatsapp=True,
            whatsapp_template_nome="campanha_ds_cientifica",
            agendado_para=timezone.now(),
            enviar_todos_prospectos_email_autorizados=True,
        )
        prospecto = Prospecto.objects.create(
            razao_social="Prospect da campanha",
            email="prospect-campanha@example.com",
            marketing_email_autorizado=True,
            marketing_base_legal="consentimento",
            marketing_origem="Formulário PROS-OPTIN-005",
        )
        campanha.destinatarios_prospectos.add(prospecto)
        MidiaMarketing.objects.create(
            campanha=campanha,
            titulo="Arte aprovada",
            tipo="imagem",
            canal_sugerido="email",
            uso_autorizado=True,
            arquivo=SimpleUploadedFile("arte.png", b"imagem", content_type="image/png"),
        )
        preparar_envios_campanha(campanha.pk)
        self.client.force_login(self.usuario)

        resposta = self.client.post(
            reverse("admin:projetos_campanhamarketing_duplicar", args=(campanha.pk,))
        )

        self.assertEqual(resposta.status_code, 302)
        duplicada = CampanhaMarketing.objects.exclude(pk=campanha.pk).get()
        self.assertRedirects(
            resposta,
            reverse("admin:projetos_campanhamarketing_change", args=(duplicada.pk,)),
        )
        self.assertEqual(duplicada.nome, "Campanha teste - cópia")
        self.assertNotEqual(duplicada.codigo, campanha.codigo)
        self.assertEqual(duplicada.status, "em_criacao")
        self.assertIsNone(duplicada.aprovada_por)
        self.assertIsNone(duplicada.aprovada_em)
        self.assertFalse(duplicada.autorizar_disparo)
        self.assertIsNone(duplicada.disparo_solicitado_em)
        self.assertIsNone(duplicada.agendado_para)
        self.assertEqual(list(duplicada.destinatarios.all()), [self.contato])
        self.assertEqual(list(duplicada.destinatarios_prospectos.all()), [prospecto])
        self.assertTrue(duplicada.enviar_todos_prospectos_email_autorizados)
        self.assertFalse(duplicada.envios.exists())
        self.assertEqual(duplicada.midias.count(), 1)
        midia_duplicada = duplicada.midias.get()
        self.assertEqual(midia_duplicada.titulo, "Arte aprovada")
        self.assertTrue(midia_duplicada.uso_autorizado)
        self.assertEqual(midia_duplicada.arquivo.name, campanha.midias.get().arquivo.name)
