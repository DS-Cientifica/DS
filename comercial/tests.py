from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from io import StringIO
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook, load_workbook

from clientes.models import Cliente
from clientes.models import ContatoCliente
from calibracao.models import OrdemServico
from financeiro.models import ContaReceber, PedidoCompra

from .models import (
    CRMRegistro,
    ItemProposta,
    Proposta,
    PropostaMovimentacao,
    PropostaSequencia,
    ProspeccaoComercial,
    ProspeccaoInteracao,
    Prospecto,
)


class ProspectoComercialTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_superuser(
            username="admin_prospectos",
            email="prospectos@example.com",
            password="teste-seguro",
        )

    def test_prospecto_fica_separado_de_cliente_ate_conversao(self):
        prospecto = Prospecto.objects.create(
            razao_social="Indústria Prospect Ltda",
            cnpj="12.345.678/0001-90",
            contato_nome="Maria",
            email="maria@prospect.example",
        )
        prospeccao = ProspeccaoComercial.objects.create(
            prospecto=prospecto,
            responsavel=self.usuario,
            razao_social="",
        )

        prospecto.refresh_from_db()
        self.assertEqual(Cliente.objects.count(), 0)
        self.assertEqual(prospeccao.razao_social, prospecto.razao_social)
        self.assertEqual(prospecto.status, "em_prospeccao")

    def test_formulario_de_prospeccao_aceita_selecao_apenas_do_prospect(self):
        from .admin import ProspeccaoComercialAdminForm

        prospecto = Prospecto.objects.create(
            razao_social="Empresa Selecionada Ltda",
            contato_nome="Contato Selecionado",
            email="selecionado@example.com",
        )
        form = ProspeccaoComercialAdminForm(data={
            "prospecto": str(prospecto.pk),
            "status": "novo",
            "origem_lead": "outro",
            "razao_social": "",
            "data_cadastro": "2026-08-11 01:00:00",
        })

        self.assertTrue(form.is_valid(), form.errors)
        prospeccao = form.save()
        self.assertEqual(prospeccao.razao_social, prospecto.razao_social)
        self.assertEqual(prospeccao.contato_nome, prospecto.contato_nome)

    def test_codigo_da_prospeccao_nao_reutiliza_lacuna_da_sequencia(self):
        ProspeccaoComercial.objects.create(
            codigo="PSC-0010/26",
            razao_social="Empresa com código existente",
        )

        with patch("comercial.models.timezone.localdate", return_value=date(2026, 8, 27)):
            nova = ProspeccaoComercial.objects.create(
                razao_social="Nova empresa prospectada",
            )

        self.assertEqual(nova.codigo, "PSC-0011/26")

    def test_tela_do_prospecto_tem_botao_para_transformar_em_prospeccao(self):
        prospecto = Prospecto.objects.create(
            razao_social="Empresa pronta para prospecção",
            contato_nome="Contato Comercial",
        )
        self.client.force_login(self.usuario)
        change_url = reverse("admin:comercial_prospecto_change", args=[prospecto.pk])
        iniciar_url = reverse(
            "admin:comercial_prospecto_iniciar_prospeccao",
            args=[prospecto.pk],
        )

        resposta = self.client.get(change_url)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Transformar em Prospecção")
        self.assertContains(resposta, iniciar_url)

        resposta = self.client.get(iniciar_url)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Confirmar transformação")
        self.assertFalse(ProspeccaoComercial.objects.filter(prospecto=prospecto).exists())

        resposta = self.client.post(iniciar_url)
        prospeccao = ProspeccaoComercial.objects.get(prospecto=prospecto)
        self.assertRedirects(
            resposta,
            reverse("admin:comercial_prospeccaocomercial_change", args=[prospeccao.pk]),
        )

    def test_retorno_do_contato_preserva_filtros_pesquisa_pagina_e_ordem(self):
        prospecto = Prospecto.objects.create(
            razao_social="Empresa com navegação preservada",
            cidade="Vinhedo",
            uf="SP",
        )
        self.client.force_login(self.usuario)
        filtros = "cidade=Vinhedo&q=Empresa&p=2&o=4.2.3"
        change_url = reverse("admin:comercial_prospecto_change", args=[prospecto.pk])

        resposta = self.client.get(
            change_url,
            {"_changelist_filters": filtros},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Voltar para lista filtrada")
        self.assertContains(
            resposta,
            reverse("admin:comercial_prospecto_changelist")
            + "?cidade=Vinhedo&amp;q=Empresa&amp;p=2&amp;o=4.2.3",
        )

    def test_agenda_de_prospeccao_usa_somente_o_proximo_passo_mais_recente(self):
        prospecto = Prospecto.objects.create(
            razao_social="Empresa da agenda diária",
            contato_nome="Maria Compras",
            telefone="(11) 99999-1111",
            email="maria@agenda.example",
        )
        prospeccao = ProspeccaoComercial.objects.create(
            prospecto=prospecto,
            responsavel=self.usuario,
            razao_social="",
        )
        ProspeccaoInteracao.objects.create(
            prospeccao=prospeccao,
            tipo="ligacao",
            resultado="sem_resposta",
            descricao="Ação antiga que foi substituída",
            data=timezone.make_aware(datetime(2026, 8, 26, 9, 0)),
            proxima_acao_tipo="ligacao",
            proxima_acao=timezone.make_aware(datetime(2026, 8, 26, 14, 0)),
        )
        ProspeccaoInteracao.objects.create(
            prospeccao=prospeccao,
            tipo="ligacao",
            resultado="aguardando_retorno",
            descricao="Enviar apresentação comercial por e-mail",
            data=timezone.make_aware(datetime(2026, 8, 27, 8, 0)),
            proxima_acao_tipo="email",
            proxima_acao=timezone.make_aware(datetime(2026, 8, 27, 15, 0)),
        )
        self.client.force_login(self.usuario)

        resposta = self.client.get(
            reverse("admin:comercial_prospeccaocomercial_agenda"),
            {"data": "2026-08-27"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Empresa da agenda diária")
        self.assertContains(resposta, "E-mail")
        self.assertContains(resposta, "Enviar apresentação comercial por e-mail")
        self.assertNotContains(resposta, "Ação antiga que foi substituída")

    def test_lista_de_prospeccoes_alerta_quando_existe_acao_hoje(self):
        prospeccao = ProspeccaoComercial.objects.create(
            razao_social="Empresa com ação hoje",
            responsavel=self.usuario,
        )
        ProspeccaoInteracao.objects.create(
            prospeccao=prospeccao,
            tipo="ligacao",
            resultado="aguardando_retorno",
            descricao="Confirmar recebimento da proposta",
            data=timezone.make_aware(datetime(2026, 9, 8, 9, 0)),
            proxima_acao_tipo="ligacao",
            proxima_acao=timezone.make_aware(datetime(2026, 9, 9, 10, 30)),
        )
        self.client.force_login(self.usuario)

        with patch("comercial.admin.timezone.localdate", return_value=date(2026, 9, 9)):
            resposta = self.client.get(
                reverse("admin:comercial_prospeccaocomercial_changelist")
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Ações de prospecção para hoje")
        self.assertContains(resposta, "Há 1")
        self.assertContains(resposta, "ação programada")
        self.assertContains(
            resposta,
            reverse("admin:comercial_prospeccaocomercial_agenda")
            + "?data=2026-09-09",
        )

    def test_lista_de_prospeccoes_nao_alerta_acao_substituida(self):
        prospeccao = ProspeccaoComercial.objects.create(
            razao_social="Empresa com ação reprogramada",
            responsavel=self.usuario,
        )
        ProspeccaoInteracao.objects.create(
            prospeccao=prospeccao,
            tipo="ligacao",
            resultado="sem_resposta",
            descricao="Ação inicialmente prevista para hoje",
            data=timezone.make_aware(datetime(2026, 9, 8, 9, 0)),
            proxima_acao_tipo="ligacao",
            proxima_acao=timezone.make_aware(datetime(2026, 9, 9, 10, 30)),
        )
        ProspeccaoInteracao.objects.create(
            prospeccao=prospeccao,
            tipo="ligacao",
            resultado="aguardando_retorno",
            descricao="Ação reprogramada",
            data=timezone.make_aware(datetime(2026, 9, 9, 11, 0)),
            proxima_acao_tipo="email",
            proxima_acao=timezone.make_aware(datetime(2026, 9, 10, 9, 0)),
        )
        self.client.force_login(self.usuario)

        with patch("comercial.admin.timezone.localdate", return_value=date(2026, 9, 9)):
            resposta = self.client.get(
                reverse("admin:comercial_prospeccaocomercial_changelist")
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "Ações de prospecção para hoje")

    def test_calendario_geral_exibe_proximos_passos_do_mes(self):
        prospecto = Prospecto.objects.create(
            razao_social="Empresa no calendário mensal",
            contato_nome="Carlos Manutenção",
        )
        prospeccao = ProspeccaoComercial.objects.create(
            prospecto=prospecto,
            responsavel=self.usuario,
            razao_social="",
        )
        ProspeccaoInteracao.objects.create(
            prospeccao=prospeccao,
            tipo="ligacao",
            resultado="aguardando_retorno",
            descricao="Enviar catálogo técnico",
            data=timezone.make_aware(datetime(2026, 8, 20, 10, 0)),
            proxima_acao_tipo="email",
            proxima_acao=timezone.make_aware(datetime(2026, 8, 28, 14, 30)),
        )
        self.client.force_login(self.usuario)

        resposta = self.client.get(
            reverse("admin:comercial_prospeccaocomercial_calendario"),
            {"mes": "8", "ano": "2026"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Calendário Geral da Prospecção")
        self.assertContains(resposta, "Empresa no calendário mensal")
        self.assertContains(resposta, "14:30 · E-mail")
        self.assertContains(resposta, "Enviar catálogo técnico")
        lista = self.client.get(
            reverse("admin:comercial_prospeccaocomercial_changelist")
        )
        self.assertContains(lista, "Calendário Geral")

    def test_conversao_cria_cliente_ativo_crm_e_arquiva_prospecto(self):
        prospecto = Prospecto.objects.create(
            razao_social="Empresa Conversão Ltda",
            nome_fantasia="Empresa Conversão",
            cnpj="11.222.333/0001-44",
            contato_nome="João",
            telefone="(11) 3333-4444",
            email="joao@conversao.example",
            cidade="Campinas",
            uf="sp",
        )
        prospeccao = ProspeccaoComercial.objects.create(
            prospecto=prospecto,
            responsavel=self.usuario,
            razao_social="",
        )

        crm = prospeccao.converter_para_crm(usuario=self.usuario)

        prospeccao.refresh_from_db()
        prospecto.refresh_from_db()
        cliente = prospeccao.cliente
        self.assertIsInstance(crm, CRMRegistro)
        self.assertTrue(cliente.ativo)
        self.assertFalse(cliente.cnpj_provisorio)
        self.assertEqual(prospecto.status, "convertido")
        self.assertEqual(prospecto.cliente_convertido, cliente)
        self.assertEqual(prospeccao.status, "convertido")
        self.assertEqual(prospeccao.crm_gerado, crm)
        self.assertEqual(prospeccao.converter_para_crm(usuario=self.usuario).pk, crm.pk)
        self.assertEqual(CRMRegistro.objects.count(), 1)

    def test_conversao_sem_cnpj_marca_cliente_como_provisorio(self):
        prospecto = Prospecto.objects.create(
            razao_social="Empresa sem documento",
            contato_nome="Contato",
            email="contato@semdocumento.example",
        )
        prospeccao = ProspeccaoComercial.objects.create(
            prospecto=prospecto,
            razao_social="",
        )

        prospeccao.converter_para_crm(usuario=self.usuario)
        prospeccao.refresh_from_db()

        self.assertTrue(prospeccao.cliente.cnpj_provisorio)
        self.assertTrue(prospeccao.cliente.cnpj.startswith("PROS-"))
        prospeccao.cliente.cnpj_provisorio = False
        with self.assertRaises(ValidationError):
            prospeccao.cliente.full_clean()

    def test_chave_impede_duplicidade_do_mesmo_contato(self):
        dados = {
            "razao_social": "Empresa Duplicada",
            "contato_nome": "Ana",
            "email": "ANA@EXAMPLE.COM",
        }
        Prospecto.objects.create(**dados)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Prospecto.objects.create(**dados)

    def test_codigo_do_prospecto_e_sequencial_e_preserva_id_original(self):
        primeiro = Prospecto.objects.create(
            referencia_externa="ORIGEM-9001",
            razao_social="Empresa Sequencial Um",
            email="sequencial1@example.com",
        )
        segundo = Prospecto.objects.create(
            referencia_externa="ORIGEM-12",
            razao_social="Empresa Sequencial Dois",
            email="sequencial2@example.com",
        )

        self.assertEqual(primeiro.codigo, "CT-00001")
        self.assertEqual(segundo.codigo, "CT-00002")
        self.assertEqual(primeiro.referencia_externa, "ORIGEM-9001")

    def test_mesmo_email_e_telefone_nao_pode_repetir_em_outra_empresa(self):
        Prospecto.objects.create(
            razao_social="Empresa Um",
            email="CONTATO@example.com",
            telefone="(11) 99999-0000",
        )
        duplicado = Prospecto(
            razao_social="Empresa Dois",
            email="contato@example.com",
            telefone="11 99999-0000",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Já existe um prospect com o mesmo e-mail e telefone.",
        ):
            duplicado.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Prospecto.objects.create(
                    razao_social="Empresa Três",
                    email="contato@example.com",
                    telefone="11999990000",
                )

    def test_edicao_de_registro_antigo_exibe_duplicidade_sem_erro_interno(self):
        primeiro = Prospecto.objects.create(
            razao_social="Empresa Legada",
            contato_nome="Ana",
            email="ana@legada.example",
        )
        segundo = Prospecto.objects.create(
            razao_social="Empresa Legada",
            contato_nome="Bruno",
            email="bruno@legada.example",
        )
        Prospecto.objects.filter(pk=segundo.pk).update(
            contato_nome=primeiro.contato_nome,
            email=primeiro.email,
        )
        segundo.refresh_from_db()
        segundo.observacoes = "Alteração administrativa"

        with self.assertRaisesMessage(
            ValidationError,
            "Já existe um prospect com a mesma empresa e identificação de contato.",
        ):
            segundo.full_clean()

    def test_admin_tem_importacao_com_validacao_e_confirmacao(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["razao_social", "contato_nome", "email", "telefone"])
        worksheet.append(["Empresa Importada", "Carlos", "carlos@importada.example", "11999990000"])
        output = BytesIO()
        workbook.save(output)
        arquivo = SimpleUploadedFile(
            "prospects.xlsx",
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.client.force_login(self.usuario)

        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            resposta = self.client.post(
                reverse("admin:comercial_prospecto_importar_excel"),
                {"validar": "1", "arquivo": arquivo},
            )
            self.assertEqual(resposta.status_code, 200)
            self.assertContains(resposta, "1</strong> contatos válidos", html=False)
            token = resposta.context["token"]
            self.assertTrue(token)

            resposta = self.client.post(
                reverse("admin:comercial_prospecto_importar_excel"),
                {"confirmar": "1", "token": token},
            )
            self.assertRedirects(resposta, reverse("admin:comercial_prospecto_changelist"))

        self.assertTrue(Prospecto.objects.filter(razao_social="Empresa Importada").exists())

    def test_nova_aba_aparece_na_area_comercial(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("admin:app_list", args=["comercial"]))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Base de prospects")
        self.assertContains(resposta, reverse("admin:comercial_prospecto_changelist"))

    def test_base_de_prospects_filtra_empresa_cidade_e_categoria(self):
        Prospecto.objects.create(
            razao_social="Alfa Alimentos Ltda",
            cidade="Campinas",
            uf="SP",
            segmento="Alimentícia",
            email="alfa@example.com",
        )
        Prospecto.objects.create(
            razao_social="Beta Bebidas Ltda",
            cidade="Jundiaí",
            uf="SP",
            segmento="Bebidas",
            email="beta@example.com",
        )
        self.client.force_login(self.usuario)
        url = reverse("admin:comercial_prospecto_changelist")

        resposta = self.client.get(url, {
            "empresa": "Alfa",
            "cidade": "Campinas",
            "segmento__exact": "Alimentícia",
        })

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Alfa Alimentos Ltda")
        self.assertNotContains(resposta, "Beta Bebidas Ltda")
        self.assertContains(resposta, "Digite razão ou nome fantasia")
        self.assertContains(resposta, "Digite a cidade")

    def test_botoes_exportar_e_baixar_modelo_aparecem_na_base(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("admin:comercial_prospecto_changelist"))

        self.assertContains(resposta, "Exportar Excel")
        self.assertContains(resposta, "Baixar modelo")
        self.assertContains(resposta, reverse("admin:comercial_prospecto_exportar_excel"))
        self.assertContains(resposta, reverse("admin:comercial_prospecto_modelo_importacao"))

    def test_exportacao_excel_respeita_filtro_de_empresa(self):
        Prospecto.objects.create(
            razao_social="Alfa Exportação Ltda",
            cidade="Campinas",
            segmento="Alimentícia",
            email="alfa.exportacao@example.com",
        )
        Prospecto.objects.create(
            razao_social="Beta Fora do Filtro Ltda",
            cidade="Jundiaí",
            segmento="Bebidas",
            email="beta.filtro@example.com",
        )
        self.client.force_login(self.usuario)

        resposta = self.client.get(
            reverse("admin:comercial_prospecto_exportar_excel"),
            {"empresa": "Alfa Exportação"},
        )
        workbook = load_workbook(BytesIO(resposta.content), read_only=True, data_only=True)
        worksheet = workbook["Base de prospects"]
        linhas = list(worksheet.iter_rows(values_only=True))
        workbook.close()

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("base_prospects_exportada.xlsx", resposta["Content-Disposition"])
        self.assertEqual(linhas[0][0:3], ("codigo", "referencia_externa", "razao_social"))
        self.assertEqual(len(linhas), 2)
        self.assertEqual(linhas[1][2], "Alfa Exportação Ltda")

    def test_modelo_excel_tem_colunas_compativeis_com_importacao(self):
        from .admin import ProspectoAdmin

        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("admin:comercial_prospecto_modelo_importacao"))
        workbook = load_workbook(BytesIO(resposta.content), read_only=True, data_only=True)
        worksheet = workbook["Prospects"]
        cabecalhos = [celula.value for celula in worksheet[1]]
        exemplo = [celula.value for celula in worksheet[2]]
        workbook.close()

        self.assertEqual(cabecalhos, ProspectoAdmin._headers_importacao())
        self.assertEqual(exemplo[0], "ORIGEM-00001")

    def test_pesquisa_geral_encontra_cidade_e_categoria(self):
        Prospecto.objects.create(
            razao_social="Empresa Pesquisa Ltda",
            cidade="Louveira",
            segmento="Alimentícia",
            email="pesquisa@example.com",
        )
        self.client.force_login(self.usuario)
        url = reverse("admin:comercial_prospecto_changelist")

        self.assertContains(self.client.get(url, {"q": "Louveira"}), "Empresa Pesquisa Ltda")
        self.assertContains(self.client.get(url, {"q": "Alimentícia"}), "Empresa Pesquisa Ltda")

    def test_conversao_admin_exige_confirmacao_post(self):
        prospecto = Prospecto.objects.create(
            razao_social="Empresa Confirmação",
            email="confirmacao@example.com",
        )
        prospeccao = ProspeccaoComercial.objects.create(
            prospecto=prospecto,
            razao_social="",
        )
        self.client.force_login(self.usuario)
        url = reverse(
            "admin:comercial_prospeccaocomercial_converter_crm",
            args=[prospeccao.pk],
        )

        resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Confirmar conversão para CRM")
        self.assertFalse(CRMRegistro.objects.exists())

        resposta = self.client.post(url)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(CRMRegistro.objects.count(), 1)

    def test_analisador_suporta_mais_de_tres_mil_contatos(self):
        workbook = Workbook(write_only=True)
        worksheet = workbook.create_sheet("Prospects")
        worksheet.append(["razao_social", "contato_nome", "email"])
        for indice in range(3005):
            worksheet.append([
                f"Empresa {indice}",
                f"Contato {indice}",
                f"contato{indice}@example.com",
            ])
        output = BytesIO()
        workbook.save(output)
        output.seek(0)

        from .admin import ProspectoAdmin
        from django.contrib import admin

        resultado = ProspectoAdmin(Prospecto, admin.site)._analisar_planilha(output)
        self.assertEqual(len(resultado["validos"]), 3005)
        self.assertEqual(resultado["duplicados"], 0)
        self.assertEqual(resultado["erros"], [])

    def test_comando_importa_planilha_reorganizada_sem_duplicar(self):
        cabecalhos = [
            "ID", "Empresa", "Contato", "Cargo / Departamento", "Telefone",
            "Celular / WhatsApp", "E-mail", "Cidade", "UF", "CNPJ",
            "Categoria / Ramo", "Endereço", "CEP", "Observações", "Fonte",
        ]
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "CONTATOS"
        worksheet.append(cabecalhos)
        worksheet.append([
            "DS-1", "Empresa Importada Ltda", "Ana", "Compras",
            "(11) 3333-4444 Fone 2: (11) 3333-5555", "", "email-invalido",
            "São Paulo", "sp", "12345678000190", "Indústria",
            "Rua Um, 100", "01000-000", "Contato prioritário", "Lista DS",
        ])
        worksheet.append([
            "DS-2", "", "Sem empresa", "", "11999990000", "", "sem@empresa.example",
            "", "", "", "", "", "", "", "Lista DS",
        ])

        with tempfile.TemporaryDirectory() as diretorio:
            arquivo = Path(diretorio) / "contatos.xlsx"
            relatorio = Path(diretorio) / "relatorio.json"
            workbook.save(arquivo)

            call_command(
                "importar_contatos_reorganizados", arquivo,
                relatorio=relatorio, stdout=StringIO(),
            )
            self.assertEqual(Prospecto.objects.count(), 0)

            call_command(
                "importar_contatos_reorganizados", arquivo,
                apply=True, relatorio=relatorio, stdout=StringIO(),
            )
            prospecto = Prospecto.objects.get()
            self.assertEqual(prospecto.referencia_externa, "DS-1")
            self.assertEqual(prospecto.telefone, "(11) 3333-4444 Fone 2: (11) 3333-5555")
            self.assertEqual(prospecto.email, "")
            self.assertIn("email-invalido", prospecto.observacoes)
            self.assertEqual(prospecto.endereco, "Rua Um, 100")

            call_command(
                "importar_contatos_reorganizados", arquivo,
                apply=True, relatorio=relatorio, stdout=StringIO(),
            )
            self.assertEqual(Prospecto.objects.count(), 1)


class PropostaNumeroTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            razao_social="Cliente Numeração Ltda",
            nome_empresa="Cliente Numeração Ltda",
            cnpj="65.432.109/0001-10",
        )

    @patch("comercial.models.timezone.localdate", return_value=date(2026, 8, 10))
    def test_ignora_codigos_historicos_e_continua_apos_0011(self, _localdate):
        Proposta.objects.create(cliente=self.cliente, codigo="CODIGO-HISTORICO")
        Proposta.objects.create(cliente=self.cliente, codigo="PROP-0011/26")

        proposta = Proposta.objects.create(cliente=self.cliente)

        self.assertEqual(proposta.codigo, "CLIENTE NUMERAÇÃO LTDA - PROP-0012/26")
        self.assertEqual(PropostaSequencia.objects.get(pk=1).ultimo_numero, 12)

    def test_mantem_contador_na_mudanca_de_ano(self):
        with patch("comercial.models.timezone.localdate", return_value=date(2026, 12, 31)):
            proposta_2026 = Proposta.objects.create(cliente=self.cliente)
        with patch("comercial.models.timezone.localdate", return_value=date(2027, 1, 1)):
            proposta_2027 = Proposta.objects.create(cliente=self.cliente)

        self.assertEqual(proposta_2026.codigo, "CLIENTE NUMERAÇÃO LTDA - PROP-0001/26")
        self.assertEqual(proposta_2027.codigo, "CLIENTE NUMERAÇÃO LTDA - PROP-0002/27")

    @patch("comercial.models.timezone.localdate", return_value=date(2026, 8, 10))
    def test_limita_nome_fantasia_sem_cortar_numero_da_proposta(self, _localdate):
        self.cliente.nome_empresa = "Nome fantasia muito extenso para identificação comercial do cliente"
        self.cliente.save(update_fields=("nome_empresa",))

        proposta = Proposta.objects.create(cliente=self.cliente)

        self.assertLessEqual(len(proposta.codigo), 50)
        self.assertTrue(proposta.codigo.endswith(" - PROP-0001/26"))


class PropostaResponsavelTests(TestCase):
    def setUp(self):
        self.cliente_a = Cliente.objects.create(
            razao_social="Cliente A Ltda",
            nome_empresa="Cliente A",
            cnpj="10.000.000/0001-10",
        )
        self.cliente_b = Cliente.objects.create(
            razao_social="Cliente B Ltda",
            nome_empresa="Cliente B",
            cnpj="20.000.000/0001-20",
        )
        self.contato_a = ContatoCliente.objects.create(
            cliente=self.cliente_a,
            nome="Contato Principal A",
            email="principal-a@example.com",
            principal=True,
        )
        self.contato_b = ContatoCliente.objects.create(
            cliente=self.cliente_b,
            nome="Contato B",
            email="contato-b@example.com",
        )

    def test_impede_responsavel_de_outro_cliente(self):
        with self.assertRaisesMessage(
            ValidationError,
            "O responsável selecionado não pertence ao cliente da proposta.",
        ):
            Proposta.objects.create(
                cliente=self.cliente_a,
                responsavel=self.contato_b,
            )

    def test_endpoint_admin_retorna_somente_contatos_do_cliente(self):
        usuario = get_user_model().objects.create_superuser(
            username="admin_contatos_proposta",
            email="admin-contatos@example.com",
            password="teste123456",
        )
        self.client.force_login(usuario)

        response = self.client.get(
            reverse("admin:comercial_proposta_contatos_por_cliente"),
            {"cliente": self.cliente_a.pk},
        )

        self.assertEqual(response.status_code, 200)
        contatos = response.json()["contatos"]
        self.assertEqual([contato["id"] for contato in contatos], [str(self.contato_a.pk)])
        self.assertTrue(contatos[0]["principal"])

    def test_formulario_carrega_script_e_botao_para_novo_contato(self):
        usuario = get_user_model().objects.create_superuser(
            username="admin_form_proposta",
            email="admin-form@example.com",
            password="teste123456",
        )
        self.client.force_login(usuario)

        response = self.client.get(reverse("admin:comercial_proposta_add"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/proposta_contatos_cliente.js")
        self.assertContains(response, 'id="add_id_responsavel"', html=False)


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
        self.assertEqual(conta.ordem_servico, proposta.ordens_servico.get())

    def test_proposta_aprovada_positiva_cria_uma_unica_os(self):
        proposta = Proposta.objects.create(
            cliente=self.cliente,
            total=Decimal("1200.00"),
            status="aprovado",
        )

        ordem = OrdemServico.objects.get(proposta=proposta)
        self.assertEqual(ordem.cliente, self.cliente)
        self.assertEqual(ordem.status, "aberta")

        proposta.observacoes = "Edição posterior"
        proposta.save()

        self.assertEqual(OrdemServico.objects.filter(proposta=proposta).count(), 1)

    def test_resultado_positivo_sem_aprovacao_nao_cria_os(self):
        proposta = Proposta.objects.create(
            cliente=self.cliente,
            total=Decimal("1200.00"),
            status="enviado",
            resultado_fechamento="positivo",
        )

        self.assertFalse(OrdemServico.objects.filter(proposta=proposta).exists())

    def test_os_concluida_cria_conta_para_faturamento_apos_execucao(self):
        proposta = Proposta.objects.create(
            cliente=self.cliente,
            prazo_pagamento="28 DDL",
            total=Decimal("2100.00"),
            gera_conta_receber_automaticamente=True,
            tipo_faturamento="apos_execucao",
            status="aprovado",
        )
        ordem = OrdemServico.objects.get(proposta=proposta)
        self.assertFalse(ContaReceber.objects.filter(proposta=proposta).exists())

        ordem.status = "concluida"
        ordem.data_conclusao = date(2026, 9, 1)
        ordem.save()

        conta = ContaReceber.objects.get(ordem_servico=ordem)
        self.assertEqual(conta.proposta, proposta)
        self.assertEqual(conta.cliente, self.cliente)
        self.assertEqual(conta.valor, Decimal("2100.00"))
        self.assertEqual(conta.vencimento, date(2026, 9, 29))

        ordem.save()
        self.assertEqual(ContaReceber.objects.filter(ordem_servico=ordem).count(), 1)

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


class MigrarClientesInativosParaProspeccaoTests(TestCase):
    def setUp(self):
        self.cliente_novo = Cliente.objects.create(
            razao_social="Cliente Inativo Novo Ltda",
            nome_empresa="Cliente Novo",
            cnpj="11.222.333/0001-44",
            telefone="(11) 4000-1000",
            telefone2="(11) 99999-1000",
            email="compras@cliente-novo.example",
            cidade="Jundiaí",
            uf="SP",
            ativo=False,
        )
        self.cliente_existente = Cliente.objects.create(
            razao_social="Empresa Já Prospectada Ltda",
            nome_empresa="Empresa Prospectada",
            cnpj="55.666.777/0001-88",
            telefone="(11) 4000-2000",
            email="contato@empresa-prospectada.example",
            ativo=False,
        )
        self.prospecto_existente = Prospecto.objects.create(
            razao_social=self.cliente_existente.razao_social,
            email=self.cliente_existente.email,
            telefone="",
            origem="CRM",
            status="disponivel",
        )

    def test_previa_nao_grava_e_apply_e_idempotente(self):
        saida = StringIO()
        call_command("migrar_clientes_inativos_para_prospeccao", stdout=saida)
        self.assertEqual(Prospecto.objects.count(), 1)
        self.assertIn('"novos_prospects": 1', saida.getvalue())
        self.assertIn('"prospects_existentes_vinculados": 1', saida.getvalue())

        call_command("migrar_clientes_inativos_para_prospeccao", "--apply", stdout=StringIO())
        self.assertEqual(Prospecto.objects.count(), 2)
        self.assertEqual(Cliente.objects.filter(ativo=False).count(), 2)

        criado = Prospecto.objects.get(origem="Cliente inativo AXION")
        self.assertEqual(criado.referencia_externa, str(self.cliente_novo.pk))
        self.assertEqual(criado.status, "disponivel")
        self.assertIn("Telefone secundário", criado.observacoes)

        self.prospecto_existente.refresh_from_db()
        self.assertEqual(self.prospecto_existente.cnpj, self.cliente_existente.cnpj)
        self.assertEqual(self.prospecto_existente.telefone, self.cliente_existente.telefone)
        self.assertEqual(self.prospecto_existente.origem, "CRM")
        self.assertIn(str(self.cliente_existente.pk), self.prospecto_existente.observacoes)

        call_command("migrar_clientes_inativos_para_prospeccao", "--apply", stdout=StringIO())
        self.assertEqual(Prospecto.objects.count(), 2)


class RemoverClientesInativosPosProspeccaoTests(TestCase):
    def test_remove_cliente_e_preserva_pedido_e_historico(self):
        cliente = Cliente.objects.create(
            razao_social="Fornecedor Inativo Ltda",
            nome_empresa="Fornecedor Inativo",
            cnpj="77.888.999/0001-00",
            telefone="(11) 4000-3000",
            email="compras@fornecedor-inativo.example",
            ativo=False,
        )
        pedido = PedidoCompra.objects.create(fornecedor=cliente)
        prospeccao = ProspeccaoComercial.objects.create(
            cliente=cliente,
            razao_social=cliente.razao_social,
            status="tentativa_contato",
        )
        call_command("migrar_clientes_inativos_para_prospeccao", "--apply", stdout=StringIO())
        prospecto = Prospecto.objects.get(origem="Cliente inativo AXION")

        with tempfile.TemporaryDirectory() as temporario:
            backup = Path(temporario) / "clientes-inativos.json"
            call_command(
                "remover_clientes_inativos_pos_prospeccao",
                "--apply",
                "--backup",
                str(backup),
                stdout=StringIO(),
            )
            self.assertTrue(backup.exists())

        self.assertFalse(Cliente.objects.filter(pk=cliente.pk).exists())
        pedido.refresh_from_db()
        self.assertIsNone(pedido.fornecedor_id)
        self.assertEqual(pedido.fornecedor_razao_social_snapshot, cliente.razao_social)
        self.assertEqual(pedido.fornecedor_cnpj_snapshot, cliente.cnpj)
        prospeccao.refresh_from_db()
        self.assertIsNone(prospeccao.cliente_id)
        self.assertEqual(prospeccao.prospecto_id, prospecto.pk)
