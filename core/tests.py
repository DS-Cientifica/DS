from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from financeiro.models import ContaPagar

from .admin import _agrupar_modelos_metrologicos, _separar_calibracoes_da_gestao


class OrdenacaoAdminTests(TestCase):
    def test_modelos_metrologicos_da_mesma_familia_ficam_juntos(self):
        app_list = [
            {
                "app_label": "calibracao",
                "models": [
                    {"object_name": "Calibracao"},
                    {"object_name": "CalibracaoDispositivoSegurancaPressao"},
                    {"object_name": "CalibracaoEsfigmomanometro"},
                    {"object_name": "Instrumento"},
                    {"object_name": "DispositivoSegurancaIncertezaPonto"},
                    {"object_name": "EsfigmomanometroIncertezaPonto"},
                    {"object_name": "Padrao"},
                    {"object_name": "DispositivoSegurancaPadraoUtilizado"},
                    {"object_name": "EsfigmomanometroPadraoUtilizado"},
                    {"object_name": "DispositivoSegurancaPonto"},
                    {"object_name": "EsfigmomanometroPonto"},
                    {"object_name": "EsfigmomanometroEnsaioVazamento"},
                ],
            }
        ]

        result = _agrupar_modelos_metrologicos(app_list)

        self.assertEqual(
            [model["object_name"] for model in result[0]["models"]],
            [
                "Calibracao",
                "CalibracaoDispositivoSegurancaPressao",
                "DispositivoSegurancaPadraoUtilizado",
                "DispositivoSegurancaPonto",
                "DispositivoSegurancaIncertezaPonto",
                "CalibracaoEsfigmomanometro",
                "EsfigmomanometroPadraoUtilizado",
                "EsfigmomanometroPonto",
                "EsfigmomanometroIncertezaPonto",
                "EsfigmomanometroEnsaioVazamento",
                "Instrumento",
                "Padrao",
            ],
        )
        self.assertEqual(
            result[0]["models"][1]["group_label"],
            "Dispositivos de segurança — pressão",
        )
        self.assertEqual(
            result[0]["models"][5]["group_label"],
            "Esfigmomanômetros",
        )
        self.assertEqual(
            result[0]["models"][10]["group_label"],
            "Cadastros metrológicos e apoio",
        )

    def test_calibracoes_e_cadastros_ficam_em_areas_separadas(self):
        app_list = [
            {
                "app_label": "calibracao",
                "name": "Gestão Metrológica",
                "app_url": "/admin/calibracao/",
                "models": [
                    {"object_name": "CalibracaoPressao"},
                    {"object_name": "Instrumento", "group_label": None},
                    {"object_name": "Padrao", "group_label": None},
                ],
            }
        ]

        result = _separar_calibracoes_da_gestao(app_list)

        self.assertEqual([app["name"] for app in result], ["Calibrações", "Gestão Metrológica"])
        self.assertEqual(
            [model["object_name"] for model in result[0]["models"]],
            ["CalibracaoPressao"],
        )
        self.assertEqual(
            [model["object_name"] for model in result[1]["models"]],
            ["Instrumento", "Padrao"],
        )

    def test_pagina_exclusiva_de_calibracoes_e_acessivel(self):
        user = User.objects.create_superuser(
            "admin_calibracoes", "calibracoes@example.com", "senha-segura"
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin:calibracoes_index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Calibrações")
        self.assertContains(response, "Calibração de pressão")
        self.assertNotContains(response, "Instrumentos")


class PaginaInicialTests(TestCase):
    def test_usuario_anonimo_e_redirecionado_para_login(self):
        response = self.client.get(reverse("inicio"))

        self.assertRedirects(
            response,
            f"/admin/login/?next={reverse('inicio')}",
            fetch_redirect_response=False,
        )

    def test_superusuario_visualiza_central_com_modulos_reais(self):
        user = User.objects.create_superuser("admin_teste", "admin@example.com", "senha-segura")
        self.client.force_login(user)

        response = self.client.get(reverse("inicio"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bem-vindo, admin_teste!")
        self.assertContains(response, "Gestão Metrológica")
        self.assertContains(response, "Planejamento e Logística")
        self.assertContains(response, "Projetos e Desenvolvimento")
        self.assertContains(response, "Manutenções")
        self.assertTemplateUsed(response, "home.html")
        self.assertEqual(
            [modulo["titulo"] for modulo in response.context["grupos"][0]["modulos"]],
            [
                "Comercial",
                "Financeiro",
                "Gestão",
                "Gestão Metrológica",
                "Planejamento e Logística",
                "Projetos e Desenvolvimento",
            ],
        )

    def test_icones_e_acesso_area_abrem_o_indice_de_cada_area(self):
        user = User.objects.create_superuser("admin_areas", "areas@example.com", "senha-segura")
        self.client.force_login(user)

        response = self.client.get(reverse("inicio"))
        modulos = {
            modulo["titulo"]: modulo
            for grupo in response.context["grupos"]
            for modulo in grupo["modulos"]
        }
        apps_esperados = {
            "Comercial": "comercial",
            "Financeiro": "financeiro",
            "Gestão": "gestao",
            "Gestão Metrológica": "calibracao",
            "Planejamento e Logística": "planejamento",
            "Projetos e Desenvolvimento": "projetos",
        }

        for titulo, app_label in apps_esperados.items():
            url_esperada = reverse("admin:app_list", kwargs={"app_label": app_label})
            self.assertEqual(modulos[titulo]["url"], url_esperada)
            self.assertContains(
                response,
                f'class="module-header" href="{url_esperada}"',
            )

    def test_calibracoes_e_um_unico_atalho_destacado_na_gestao_metrologica(self):
        user = User.objects.create_superuser(
            "admin_central_calibracoes",
            "central-calibracoes@example.com",
            "senha-segura",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("inicio"))
        modulo = next(
            modulo
            for modulo in response.context["grupos"][0]["modulos"]
            if modulo["titulo"] == "Gestão Metrológica"
        )
        calibracoes = next(item for item in modulo["itens"] if item["rotulo"] == "Calibrações")

        self.assertEqual(calibracoes["url"], reverse("admin:calibracoes_index"))
        self.assertTrue(calibracoes["destaque"])
        self.assertContains(response, 'class="module-item--featured"', html=False)
        self.assertContains(response, "Central")

    def test_indices_operacionais_usam_cartoes_modernos_e_voltam_a_central(self):
        user = User.objects.create_superuser(
            "admin_indices_modernos",
            "indices-modernos@example.com",
            "senha-segura",
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("admin:app_list", kwargs={"app_label": "comercial"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="axion-area-hero"', html=False)
        self.assertContains(response, 'class="axion-app-grid is-app-index"', html=False)
        self.assertContains(response, "Módulos e registros")
        self.assertContains(response, "Abrir registros")
        self.assertContains(response, "Voltar para o início")
        self.assertContains(
            response,
            f'<a href="{reverse("inicio")}">Início</a>',
            html=True,
        )
        self.assertContains(response, reverse("admin:comercial_proposta_add"))
        self.assertContains(response, reverse("admin:comercial_proposta_changelist"))

    def test_todas_as_areas_usam_o_indice_visual_moderno(self):
        user = User.objects.create_superuser(
            "admin_todas_areas",
            "todas-areas@example.com",
            "senha-segura",
        )
        self.client.force_login(user)

        areas = [
            "auth",
            "certificados",
            "clientes",
            "comercial",
            "financeiro",
            "gestao",
            "documentos",
            "calibracao",
            "manutencao",
            "planejamento",
            "projetos",
            "qualidade",
        ]

        for app_label in areas:
            with self.subTest(app_label=app_label):
                response = self.client.get(
                    reverse("admin:app_list", kwargs={"app_label": app_label})
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="axion-area-hero', html=False)
                self.assertContains(
                    response,
                    'class="axion-app-grid is-app-index"',
                    html=False,
                )
                self.assertContains(response, "Voltar para o início")

        response = self.client.get(reverse("admin:calibracoes_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="axion-area-hero', html=False)
        self.assertContains(
            response,
            'class="axion-app-grid is-app-index"',
            html=False,
        )
        self.assertContains(response, "Voltar para o início")

    def test_usuario_restrito_visualiza_somente_modulos_permitidos(self):
        user = User.objects.create_user("cliente_teste", password="senha-segura", is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename="view_cliente"))
        self.client.force_login(user)

        response = self.client.get(reverse("inicio"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Comercial")
        self.assertContains(response, "Clientes")
        self.assertNotContains(response, "Contas a receber")
        self.assertNotContains(response, "Padrões")
        self.assertNotContains(response, "Manutenções")

    def test_dashboard_operacional_continua_em_rota_separada(self):
        user = User.objects.create_superuser("admin_dashboard", "dashboard@example.com", "senha-segura")
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Início")
        html = response.content.decode()
        top_actions = html.split('<nav class="top-actions"', 1)[1].split("</nav>", 1)[0]
        self.assertNotIn("Desenvolvimento", top_actions)
        self.assertNotIn("Qualidade", top_actions)
        self.assertNotIn("Proposta", top_actions)
        self.assertContains(response, 'class="dashboard-page"', html=False)
        self.assertContains(response, 'class="sidebar"', html=False)
        self.assertContains(response, 'class="nav-link active"', html=False)
        self.assertContains(response, "css/home.css")
        self.assertContains(response, "css/dashboard_shell.css")

    def test_agenda_integrada_reune_eventos_e_respeita_permissoes(self):
        ContaPagar.objects.create(
            descricao="Calibração do padrão de pressão",
            fornecedor="Laboratório parceiro",
            valor=Decimal("1250.00"),
            vencimento=date(2026, 8, 18),
        )
        user = User.objects.create_user(
            "financeiro_calendario",
            password="senha-segura",
            is_staff=True,
        )
        user.user_permissions.add(Permission.objects.get(codename="view_contapagar"))
        self.client.force_login(user)

        response = self.client.get(
            reverse("calendario_integrado"),
            {"ano": 2026, "mes": 8},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agenda Integrada AXION")
        self.assertContains(response, "Calibração do padrão de pressão")
        self.assertContains(response, "Conta a pagar")
        self.assertContains(response, 'class="nav-link active"', html=False)
        self.assertEqual(
            [modulo["valor"] for modulo in response.context["modulos"]],
            ["financeiro"],
        )
        modulo_financeiro = response.context["modulos"][0]
        self.assertFalse(modulo_financeiro["ativo"])
        self.assertEqual(
            modulo_financeiro["url_filtro"],
            f'{reverse("calendario_integrado")}?ano=2026&mes=8&modulo=financeiro',
        )
        self.assertContains(response, "Filtrar por Financeiro")
        self.assertEqual(response.context["total_eventos"], 1)

        response_filtrada = self.client.get(
            reverse("calendario_integrado"),
            {"ano": 2026, "mes": 8, "modulo": "financeiro"},
        )
        modulo_financeiro = response_filtrada.context["modulos"][0]
        self.assertTrue(modulo_financeiro["ativo"])
        self.assertEqual(
            modulo_financeiro["url_filtro"],
            f'{reverse("calendario_integrado")}?ano=2026&mes=8',
        )
        self.assertContains(response_filtrada, "Remover filtro Financeiro")
        self.assertContains(response_filtrada, 'aria-current="true"', html=False)

    def test_calendario_aparece_abaixo_do_dashboard_na_barra_lateral(self):
        user = User.objects.create_superuser(
            "admin_link_calendario",
            "link-calendario@example.com",
            "senha-segura",
        )
        self.client.force_login(user)

        for rota in ("inicio", "dashboard"):
            with self.subTest(rota=rota):
                response = self.client.get(reverse(rota))
                html = response.content.decode()
                self.assertContains(response, reverse("calendario_integrado"))
                self.assertLess(
                    html.index(f'href="{reverse("dashboard")}"'),
                    html.index(f'href="{reverse("calendario_integrado")}"'),
                )

    def test_filtros_das_listagens_usam_menus_suspensos_no_topo(self):
        user = User.objects.create_superuser(
            "admin_filtros_topo",
            "filtros-topo@example.com",
            "senha-segura",
        )
        self.client.force_login(user)

        listagens = [
            reverse("admin:projetos_projeto_changelist"),
            reverse("admin:comercial_proposta_changelist"),
            reverse("admin:calibracao_instrumento_changelist"),
        ]

        for url in listagens:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="changelist-filter"', html=False)
                self.assertContains(
                    response,
                    'class="axion-filter-dropdown"',
                    html=False,
                )
                self.assertContains(
                    response,
                    'class="axion-filter-dropdown__value"',
                    html=False,
                )
                self.assertTemplateUsed(response, "admin/filter.html")

    def test_engrenagem_de_desenvolvimento_aparece_somente_para_superusuario(self):
        superuser = User.objects.create_superuser(
            "admin_engrenagem",
            "engrenagem@example.com",
            "senha-segura",
        )
        self.client.force_login(superuser)

        response = self.client.get(reverse("inicio"))

        self.assertContains(response, 'class="development-link"', html=False)
        self.assertContains(response, "Área de Desenvolvimento")

        usuario_operacional = User.objects.create_user(
            "operacional_sem_engrenagem",
            password="senha-segura",
            is_staff=True,
        )
        usuario_operacional.user_permissions.add(Permission.objects.get(codename="view_cliente"))
        self.client.force_login(usuario_operacional)

        response = self.client.get(reverse("inicio"))

        self.assertNotContains(response, 'class="development-link"', html=False)
        self.assertNotContains(response, "Área de Desenvolvimento")

    def test_indice_admin_e_bastidor_restrito_mas_telas_operacionais_continuam_acessiveis(self):
        usuario = User.objects.create_user(
            "operacional_admin_restrito",
            password="senha-segura",
            is_staff=True,
        )
        usuario.user_permissions.add(Permission.objects.get(codename="view_cliente"))
        self.client.force_login(usuario)

        response = self.client.get(reverse("admin:index"))
        self.assertRedirects(response, reverse("inicio"))

        clientes_response = self.client.get(reverse("admin:clientes_cliente_changelist"))
        self.assertEqual(clientes_response.status_code, 200)

        superuser = User.objects.create_superuser(
            "desenvolvedor_admin",
            "desenvolvedor@example.com",
            "senha-segura",
        )
        self.client.force_login(superuser)

        development_response = self.client.get(reverse("admin:index"))
        self.assertEqual(development_response.status_code, 200)
        self.assertContains(development_response, "Área de Desenvolvimento")
        self.assertContains(development_response, "Bastidores do sistema")
        self.assertContains(development_response, "Voltar para o início")
        self.assertContains(development_response, "development-dashboard", html=False)

    def test_rota_inicio_explicitamente_acessivel(self):
        user = User.objects.create_superuser("admin_inicio", "inicio@example.com", "senha-segura")
        self.client.force_login(user)

        response = self.client.get("/inicio/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bem-vindo, admin_inicio!")

        admin_response = self.client.get(reverse("admin:index"))
        self.assertContains(
            admin_response,
            f'<a href="{reverse("inicio")}">Início</a>',
            html=True,
        )
        self.assertContains(admin_response, "Área de Desenvolvimento")
        self.assertContains(admin_response, "Modo desenvolvimento")
        self.assertContains(admin_response, reverse("inicio"))
        self.assertNotContains(admin_response, 'id="nav-sidebar"')

        clientes_response = self.client.get(reverse("admin:clientes_cliente_changelist"))
        self.assertEqual(clientes_response.status_code, 200)
        self.assertContains(
            clientes_response,
            f'<a href="{reverse("inicio")}">Início</a>',
            html=True,
        )
        self.assertContains(clientes_response, "js/admin_navigation.js")
        self.assertContains(clientes_response, f'data-central-url="{reverse("inicio")}"', html=False)
        self.assertNotContains(clientes_response, 'id="nav-sidebar"')

        padrao_add_response = self.client.get(reverse("admin:calibracao_padrao_add"))
        self.assertEqual(padrao_add_response.status_code, 200)
        self.assertContains(
            padrao_add_response,
            f'<a href="{reverse("inicio")}">Início</a>',
            html=True,
        )
        self.assertNotContains(padrao_add_response, 'id="nav-sidebar"')

        calendario_response = self.client.get(
            reverse("admin:planejamento_planejamentoservico_calendario")
        )
        self.assertEqual(calendario_response.status_code, 200)
        self.assertNotContains(calendario_response, 'id="nav-sidebar"')


class AlertasMetrologicosTests(TestCase):
    def test_alerta_lista_apenas_padroes_vencidos_e_link_do_sino(self):
        from datetime import timedelta
        from django.utils import timezone
        from calibracao.dilution_models import PreparacaoPadrao, PreparacaoPadraoResultado
        from calibracao.models import Padrao
        from .home_views import _montar_alertas
        hoje = timezone.localdate()
        usuario = User.objects.create_superuser("alertas", "alertas@example.com", "senha")
        vencido = Padrao.objects.create(codigo="TEST-01", descricao="Padrão atrasado", vencimento=hoje-timedelta(days=3))
        padrao_mae = Padrao.objects.create(codigo="TEST-02", descricao="Padrão em dia", vencimento=hoje)
        padrao_diluido = Padrao.objects.create(
            codigo="TEST-DIL",
            descricao="Padrão de diluição já utilizado",
            vencimento=hoje-timedelta(days=2),
        )
        preparacao = PreparacaoPadrao.objects.create(
            aplicacao="turbidez",
            data_preparacao=hoje-timedelta(days=4),
            validade=hoje-timedelta(days=2),
            padrao_origem=padrao_mae,
            unidade="NTU",
        )
        resultado = PreparacaoPadraoResultado.objects.create(
            preparacao=preparacao,
            ordem=1,
            valor_alvo=100,
            volume_final=100,
        )
        PreparacaoPadraoResultado.objects.filter(pk=resultado.pk).update(
            padrao_gerado=padrao_diluido
        )
        self.client.force_login(usuario)
        url = reverse("alerta_metrologico", args=["padroes"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Padrão atrasado")
        self.assertNotContains(response, "Padrão em dia")
        self.assertNotContains(response, "Padrão de diluição já utilizado")
        self.assertContains(response, "3 dias")
        self.assertContains(response, reverse("admin:calibracao_padrao_change", args=[vencido.pk]))
        alerta = next(a for a in _montar_alertas(usuario) if a["rotulo"] == "Padrões vencidos")
        self.assertEqual(alerta["total"], 1)
        self.assertEqual(alerta["url"], url)
        self.assertEqual(alerta["total"], response.context["pagina"].paginator.count)

    def test_permissao_e_estado_vazio(self):
        usuario = User.objects.create_user("restrito_alertas", password="senha", is_staff=True)
        self.client.force_login(usuario)
        for tipo in ("padroes", "calibracoes"):
            self.assertEqual(self.client.get(reverse("alerta_metrologico", args=[tipo])).status_code, 403)
        usuario.user_permissions.add(Permission.objects.get(codename="view_padrao", content_type__app_label="calibracao"))
        response = self.client.get(reverse("alerta_metrologico", args=["padroes"]))
        self.assertContains(response, "Nenhuma pendência nesta categoria")
        self.assertEqual(self.client.get(reverse("alerta_metrologico", args=["calibracoes"])).status_code, 403)


    def test_calibracoes_excluem_inativos_sem_data_e_vencimento_hoje(self):
        from datetime import timedelta
        from django.utils import timezone
        from calibracao.models import Instrumento
        from clientes.models import Cliente
        hoje = timezone.localdate()
        cliente = Cliente.objects.create(codigo="CLI-ALERTA", razao_social="Cliente alerta", nome_empresa="Cliente alerta", cnpj="12345678000100")
        for codigo, ativo, data in (("VENCIDO", True, hoje-timedelta(days=2)), ("INATIVO", False, hoje-timedelta(days=2)), ("HOJE", True, hoje), ("SEM-DATA", True, None)):
            Instrumento.objects.create(codigo=codigo, descricao=codigo, cliente=cliente, ativo=ativo, proxima_calibracao=data)
        usuario = User.objects.create_superuser("instrumentos_alertas", "i@example.com", "senha")
        self.client.force_login(usuario)
        response = self.client.get(reverse("alerta_metrologico", args=["calibracoes"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pagina"].paginator.count, 1)
        self.assertContains(response, "VENCIDO")
        self.assertContains(response, "2 dias")
        for codigo in ("INATIVO", "HOJE", "SEM-DATA"):
            self.assertNotContains(response, codigo)
