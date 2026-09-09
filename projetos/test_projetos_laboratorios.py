from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from projetos.models import Projeto, ProjetoTarefa


class PreencherProjetosLaboratoriosTests(TestCase):
    def test_previa_nao_grava(self):
        saida = StringIO()
        call_command("preencher_projetos_laboratorios", stdout=saida)
        self.assertEqual(Projeto.objects.count(), 0)
        self.assertIn("Nenhum dado foi gravado", saida.getvalue())

    def test_apply_cria_tres_projetos_com_orcamento(self):
        call_command("preencher_projetos_laboratorios", apply=True, stdout=StringIO())
        self.assertEqual(Projeto.objects.filter(codigo__in=["DEV-0003", "DEV-0004", "DEV-0005"]).count(), 3)
        for projeto in Projeto.objects.filter(codigo__in=["DEV-0003", "DEV-0004", "DEV-0005"]):
            self.assertEqual(projeto.status, "em_analise")
            self.assertEqual(projeto.orcamento_previsto, 150000)
            self.assertEqual(sum(c.custo_total for c in projeto.custos.all()), 150000)

    def test_apply_e_idempotente_e_preserva_tarefa_manual(self):
        call_command("preencher_projetos_laboratorios", apply=True, stdout=StringIO())
        projeto = Projeto.objects.get(codigo="DEV-0003")
        ProjetoTarefa.objects.create(projeto=projeto, titulo="Tarefa manual", ordem=99)
        contagem = ProjetoTarefa.objects.count()

        call_command("preencher_projetos_laboratorios", apply=True, stdout=StringIO())

        self.assertEqual(ProjetoTarefa.objects.count(), contagem)
        self.assertTrue(ProjetoTarefa.objects.filter(projeto=projeto, titulo="Tarefa manual").exists())
