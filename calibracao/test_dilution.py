from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from qualidade.models import Documento

from .dilution_models import (
    PreparacaoPadrao,
    PreparacaoPadraoEquipamento,
    PreparacaoPadraoEtapa,
    PreparacaoPadraoResultado,
)
from .models import (
    CalibracaoColorimetro,
    CalibracaoTurbidez,
    ColorimetroPadraoUtilizado,
    Instrumento,
    Padrao,
    TurbidezPadraoUtilizado,
)


class PreparacaoPadraoTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser(
            username="metrologista",
            email="metrologia@example.com",
            password="senha-teste",
        )
        self.procedimento = Documento.objects.create(
            codigo="MDS-DIL-001",
            titulo="Preparação de padrões por diluição volumétrica",
            tipo="metodo",
            revisao="REV.00",
            status="vigente",
            arquivo=SimpleUploadedFile("metodo.pdf", b"pdf"),
        )
        self.origem = Padrao.objects.create(
            descricao="Solução padrão de turbidez 4000 NTU",
            numero_certificado="167081.2026",
            laboratorio_emitente="Fornecedor",
            data_calibracao=date(2026, 6, 9),
            valor_nominal=Decimal("4000"),
            incerteza=Decimal("40"),
            fator_k=Decimal("2"),
            graus_liberdade=Decimal("999999"),
            unidade="NTU",
            vencimento=date(2028, 6, 9),
        )
        self.pipeta = Padrao.objects.create(
            descricao="Pipeta 2,5 mL",
            numero_certificado="PIP-001",
            valor_nominal=Decimal("2.5"),
            resolucao=Decimal("0.01"),
            incerteza=Decimal("0.01"),
            fator_k=Decimal("2"),
            unidade="mL",
            vencimento=date(2027, 1, 1),
        )
        self.balao = Padrao.objects.create(
            descricao="Balão volumétrico 100 mL",
            numero_certificado="BAL-001",
            valor_nominal=Decimal("100"),
            resolucao=Decimal("0.1"),
            incerteza=Decimal("0.08"),
            fator_k=Decimal("2"),
            unidade="mL",
            vencimento=date(2027, 1, 1),
        )

    def criar_preparacao(self, *, aplicacao="turbidez", data_preparacao=date(2026, 8, 22)):
        return PreparacaoPadrao.objects.create(
            aplicacao=aplicacao,
            tipo_preparacao="volumetrica",
            data_preparacao=data_preparacao,
            validade=date(2026, 9, 22),
            padrao_origem=self.origem,
            procedimento=self.procedimento,
            valor_alvo=Decimal("100"),
            unidade="NTU",
            matriz_diluente="Água isenta de turbidez",
            temperatura_preparacao=Decimal("20"),
            responsavel_preparo="Técnico executor",
            responsavel_revisao="Responsável técnico",
        )

    def test_duplica_planejamento_como_rascunho_sem_copiar_execucao(self):
        preparacao = self.criar_preparacao(data_preparacao=date(2026, 8, 22))
        preparacao.status = "aprovado"
        preparacao.lote = "LOTE-ORIGINAL"
        preparacao.save(update_fields=("status", "lote"))
        PreparacaoPadraoResultado.objects.create(
            preparacao=preparacao,
            ordem=1,
            valor_alvo=Decimal("100"),
            volume_final=Decimal("100"),
            volume_aliquota_utilizado=Decimal("2.498"),
            pipeta=self.pipeta,
            recipiente_final=self.balao,
        )
        PreparacaoPadraoEquipamento.objects.create(
            preparacao=preparacao,
            ordem=1,
            papel="balanca",
            padrao=self.pipeta,
            valor_utilizado=Decimal("10"),
        )

        copia = preparacao.duplicar_como_rascunho(data_preparacao=date(2026, 8, 27))

        self.assertEqual(copia.status, "rascunho")
        self.assertEqual(copia.data_preparacao, date(2026, 8, 27))
        self.assertEqual(copia.validade, date(2026, 9, 27))
        self.assertEqual(copia.padrao_origem, preparacao.padrao_origem)
        self.assertEqual(copia.procedimento, preparacao.procedimento)
        self.assertEqual(copia.lote, "")
        self.assertIsNone(copia.temperatura_preparacao)
        self.assertFalse(copia.registro_retroativo)
        self.assertNotEqual(copia.codigo, preparacao.codigo)
        self.assertIsNone(copia.resultados.get().volume_aliquota_utilizado)
        self.assertIsNone(copia.equipamentos.get().valor_utilizado)

    def test_codigo_sequencial_por_aplicacao_e_data(self):
        primeira = self.criar_preparacao()
        segunda = self.criar_preparacao()
        cor = self.criar_preparacao(aplicacao="cor")

        self.assertEqual(primeira.codigo, "DIL-TUR-220826-01/26")
        self.assertEqual(segunda.codigo, "DIL-TUR-220826-02/26")
        self.assertEqual(cor.codigo, "DIL-COR-220826-01/26")

    def test_calcula_diluicao_e_componentes_automaticas(self):
        preparacao = self.criar_preparacao()
        PreparacaoPadraoEtapa.objects.create(
            preparacao=preparacao,
            ordem=1,
            volume_aliquota=Decimal("2.5"),
            volume_final=Decimal("100"),
            unidade_volume="mL",
            pipeta=self.pipeta,
            recipiente_final=self.balao,
        )

        preparacao.recalcular()
        preparacao.refresh_from_db()

        self.assertEqual(preparacao.valor_atribuido, Decimal("100.000000000"))
        self.assertGreater(preparacao.incerteza_padrao_combinada, Decimal("0.5"))
        self.assertGreater(preparacao.incerteza_expandida, Decimal("1"))
        self.assertEqual(preparacao.componentes.filter(automatico=True).count(), 5)

    def test_aprovacao_cria_padrao_preparado_rastreavel(self):
        preparacao = self.criar_preparacao()
        PreparacaoPadraoEtapa.objects.create(
            preparacao=preparacao,
            ordem=1,
            volume_aliquota=Decimal("2.5"),
            volume_final=Decimal("100"),
            pipeta=self.pipeta,
            recipiente_final=self.balao,
        )

        preparacao.status = "em_revisao"
        preparacao.save(update_fields=("status",))
        preparacao.aprovar(self.usuario)
        preparacao.refresh_from_db()

        self.assertEqual(preparacao.status, "aprovado")
        self.assertIsNotNone(preparacao.padrao_gerado_id)
        self.assertEqual(preparacao.padrao_gerado.valor_nominal, preparacao.valor_atribuido)
        self.assertEqual(preparacao.padrao_gerado.incerteza, preparacao.incerteza_expandida)
        self.assertEqual(preparacao.padrao_gerado.numero_certificado, preparacao.codigo)

        self.client.force_login(self.usuario)
        resposta = self.client.get(
            reverse("admin:calibracao_preparacaopadrao_change", args=(preparacao.pk,))
        )
        self.assertEqual(resposta.status_code, 200)

    def test_aprovacao_exige_revisao_formal(self):
        preparacao = self.criar_preparacao()
        PreparacaoPadraoEtapa.objects.create(
            preparacao=preparacao,
            ordem=1,
            volume_aliquota=Decimal("2.5"),
            volume_final=Decimal("100"),
            pipeta=self.pipeta,
            recipiente_final=self.balao,
        )

        with self.assertRaises(ValidationError):
            preparacao.aprovar(self.usuario)

    def test_gabarito_gera_varios_padroes_com_resultado_e_incerteza_individuais(self):
        preparacao = self.criar_preparacao()
        pipeta_maior = Padrao.objects.create(
            descricao="Pipeta 25 mL",
            numero_certificado="PIP-025",
            valor_nominal=Decimal("25"),
            resolucao=Decimal("0.01"),
            incerteza=Decimal("0.02"),
            fator_k=Decimal("2"),
            unidade="mL",
            vencimento=date(2027, 1, 1),
        )
        linhas = (
            (1, Decimal("10"), Decimal("0.25"), self.pipeta),
            (2, Decimal("100"), Decimal("2.5"), self.pipeta),
            (3, Decimal("500"), Decimal("12.5"), pipeta_maior),
        )
        for ordem, alvo, aliquota, pipeta in linhas:
            PreparacaoPadraoResultado.objects.create(
                preparacao=preparacao,
                ordem=ordem,
                valor_alvo=alvo,
                volume_final=Decimal("100"),
                volume_aliquota_utilizado=aliquota,
                pipeta=pipeta,
                recipiente_final=self.balao,
            )

        preparacao.recalcular()
        resultados = list(preparacao.resultados.order_by("ordem"))
        self.assertEqual(
            [item.volume_aliquota_planejado for item in resultados],
            [Decimal("0.250000000"), Decimal("2.500000000"), Decimal("12.500000000")],
        )
        self.assertEqual(
            [item.valor_calculado for item in resultados],
            [Decimal("10.000000000"), Decimal("100.000000000"), Decimal("500.000000000")],
        )
        self.assertTrue(all(item.incerteza_expandida for item in resultados))

        preparacao.status = "em_revisao"
        preparacao.save(update_fields=("status",))
        preparacao.aprovar(self.usuario)
        resultados = list(preparacao.resultados.order_by("ordem"))

        self.assertEqual(preparacao.status, "aprovado")
        self.assertEqual(
            [item.padrao_gerado.numero_certificado for item in resultados],
            [
                "DIL-TUR-220826-01-P01/26",
                "DIL-TUR-220826-01-P02/26",
                "DIL-TUR-220826-01-P03/26",
            ],
        )

    def test_tela_admin_e_registro_estao_disponiveis(self):
        preparacao = self.criar_preparacao()
        preparacao.status = "em_revisao"
        preparacao.save(update_fields=("status",))
        self.client.force_login(self.usuario)

        lista = self.client.get(reverse("admin:calibracao_preparacaopadrao_changelist"))
        adicionar = self.client.get(reverse("admin:calibracao_preparacaopadrao_add"))
        alterar = self.client.get(
            reverse("admin:calibracao_preparacaopadrao_change", args=(preparacao.pk,))
        )
        registro = self.client.get(
            reverse("admin:calibracao_preparacaopadrao_registro", args=(preparacao.pk,))
        )
        dados_padrao = self.client.get(
            reverse("admin:calibracao_preparacaopadrao_padrao_dados"),
            {"id": self.origem.pk},
        )
        dados_certificado = self.client.get(
            reverse("admin:calibracao_padrao_dados_metrologicos", args=(self.origem.pk,))
        )
        tentativa_aprovacao = self.client.post(
            reverse("admin:calibracao_preparacaopadrao_aprovar", args=(preparacao.pk,)),
            follow=True,
        )
        adicionar_turbidez = self.client.get(reverse("admin:calibracao_calibracaoturbidez_add"))
        adicionar_colorimetro = self.client.get(reverse("admin:calibracao_calibracaocolorimetro_add"))

        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, "Diluições e preparações de padrões")
        self.assertEqual(adicionar.status_code, 200)
        self.assertContains(adicionar, "Gabarito de diluição")
        self.assertContains(adicionar, 'id="diluicao-matrizes"')
        self.assertContains(adicionar, "Selecione ou digite para incluir")
        self.assertContains(adicionar, "calibracao/js/dilution_live.js")
        self.assertContains(adicionar, "calibracao/css/dilution_live.css")
        self.assertEqual(alterar.status_code, 200)
        self.assertContains(alterar, 'name="status"')
        self.assertContains(
            alterar,
            '<option value="em_revisao" selected>Em revisão</option>',
            html=True,
        )
        self.assertNotContains(alterar, '<option value="aprovado">Aprovado</option>', html=True)
        self.assertContains(alterar, "Aprovar e gerar padrões")
        self.assertContains(alterar, "Registro retroativo e aprovação")
        self.assertEqual(tentativa_aprovacao.status_code, 200)
        preparacao.refresh_from_db()
        self.assertEqual(preparacao.status, "em_revisao")
        self.assertEqual(registro.status_code, 200)
        self.assertContains(registro, preparacao.codigo)
        self.assertContains(registro, "Registro de preparação")
        self.assertContains(registro, "DS Científica")
        self.assertContains(registro, "63.669.660/0001-80")
        self.assertContains(registro, "img/logo_ds.png")
        self.assertNotContains(registro, "AXION")
        self.assertEqual(dados_padrao.status_code, 200)
        self.assertEqual(dados_padrao.json()["valor_nominal"], "4000.000000000")
        self.assertEqual(dados_padrao.json()["unidade"], "NTU")
        self.assertEqual(dados_certificado.status_code, 200)
        self.assertEqual(dados_certificado.json()["numero_certificado"], "167081.2026")
        self.assertEqual(dados_certificado.json()["incerteza"], "40.000000000")
        for pagina in (adicionar_turbidez, adicionar_colorimetro):
            self.assertEqual(pagina.status_code, 200)
            self.assertContains(pagina, "js/padrao_autofill.js")
            self.assertContains(pagina, "css/padrao_autofill.css")

    def test_registro_retroativo_exige_justificativa_e_evidencia(self):
        preparacao = self.criar_preparacao()
        preparacao.status = "em_revisao"
        preparacao.registro_retroativo = True
        preparacao.save(update_fields=("status", "registro_retroativo"))

        pendencias = preparacao.pendencias_aprovacao()

        self.assertIn("justificativa do registro retroativo não informada", pendencias)
        self.assertIn("evidência documental do registro retroativo não anexada", pendencias)
        self.assertIn("responsável ou data do lançamento retroativo não registrados", pendencias)

    def test_registro_retroativo_preserva_codigo_anterior_e_reidentifica_data(self):
        preparacao = self.criar_preparacao(data_preparacao=date(2026, 8, 22))
        codigo_original = preparacao.codigo
        preparacao.data_preparacao = date(2026, 6, 12)
        preparacao.registro_retroativo = True

        preparacao.save()

        self.assertEqual(preparacao.codigo_anterior, codigo_original)
        self.assertIn("-120626-", preparacao.codigo)

    def test_admin_exibe_sem_pendencias_sem_erro_de_renderizacao(self):
        preparacao = self.criar_preparacao()
        PreparacaoPadraoEtapa.objects.create(
            preparacao=preparacao,
            ordem=1,
            volume_aliquota=Decimal("2.5"),
            volume_final=Decimal("100"),
            pipeta=self.pipeta,
            recipiente_final=self.balao,
        )
        preparacao.status = "em_revisao"
        preparacao.save(update_fields=("status",))
        preparacao.recalcular()
        self.assertEqual(preparacao.pendencias_aprovacao(), [])
        self.client.force_login(self.usuario)

        resposta = self.client.get(
            reverse("admin:calibracao_preparacaopadrao_change", args=(preparacao.pk,))
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Sem pendências.")

    def test_padrao_preparado_alimenta_turbidez_e_colorimetro(self):
        preparacao = self.criar_preparacao()
        PreparacaoPadraoEtapa.objects.create(
            preparacao=preparacao,
            ordem=1,
            volume_aliquota=Decimal("2.5"),
            volume_final=Decimal("100"),
            pipeta=self.pipeta,
            recipiente_final=self.balao,
        )
        preparacao.status = "em_revisao"
        preparacao.save(update_fields=("status",))
        preparacao.aprovar(self.usuario)
        preparacao.refresh_from_db()

        cliente = Cliente.objects.create(
            razao_social="Cliente integração Ltda",
            nome_empresa="Cliente integração",
            cnpj="74.222.333/0001-91",
        )
        instrumento = Instrumento.objects.create(
            codigo="TUR-COR-DIL-001",
            descricao="Instrumento óptico",
            cliente=cliente,
        )
        turbidez = CalibracaoTurbidez.objects.create(
            instrumento=instrumento,
            cliente=cliente,
            data_calibracao=date(2026, 8, 22),
        )
        colorimetro = CalibracaoColorimetro.objects.create(
            instrumento=instrumento,
            cliente=cliente,
            data_calibracao=date(2026, 8, 22),
            tipo_aplicacao="cor",
        )

        uso_turbidez = TurbidezPadraoUtilizado.objects.create(
            calibracao=turbidez,
            tipo="calibracao",
            ordem=1,
            padrao=preparacao.padrao_gerado,
        )
        uso_colorimetro = ColorimetroPadraoUtilizado.objects.create(
            calibracao=colorimetro,
            tipo="calibracao",
            ordem=1,
            padrao=preparacao.padrao_gerado,
        )

        for uso in (uso_turbidez, uso_colorimetro):
            self.assertEqual(uso.valor_nominal, preparacao.valor_atribuido)
            self.assertEqual(uso.incerteza, preparacao.incerteza_expandida)
            self.assertEqual(uso.fator_k, preparacao.fator_abrangencia)
            self.assertEqual(uso.numero_certificado, preparacao.codigo)

        colorimetro.tipo_aplicacao = "cloro"
        colorimetro.save(update_fields=("tipo_aplicacao",))
        uso_incompativel = ColorimetroPadraoUtilizado(
            calibracao=colorimetro,
            tipo="calibracao",
            ordem=2,
            padrao=preparacao.padrao_gerado,
        )
        with self.assertRaises(ValidationError):
            uso_incompativel.full_clean()

        turbidez.data_calibracao = date(2026, 9, 23)
        turbidez.save(update_fields=("data_calibracao",))
        uso_vencido = TurbidezPadraoUtilizado(
            calibracao=turbidez,
            tipo="calibracao",
            ordem=2,
            padrao=preparacao.padrao_gerado,
        )
        with self.assertRaisesMessage(ValidationError, "não pode ser utilizado"):
            uso_vencido.full_clean()
