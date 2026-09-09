from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from clientes.models import Cliente
from projetos.models import Projeto, ProjetoCusto, ProjetoTarefa, ProjetoTeste


PROJECT_CODE = "DEV-0002"
PROJECT_NAME = "Retrofit de banho termostatizado"


OBJECTIVE = """Modernizar o banho termostatizado UH4 por meio da substituicao do sistema eletronico analogico original por um sistema digital de controle de temperatura, preservando sempre que tecnicamente viavel a estrutura mecanica, a cuba de aco inoxidavel, a resistencia de aquecimento, o conjunto hidraulico e o motor de circulacao originais.

O novo sistema devera utilizar controlador PID REX-C100, termopar tipo K, rele de estado solido SSR-40DA, dissipador termico, entrada IEC com chave liga/desliga e fusivel integrado, novo cabeamento, terminais e aterramento da estrutura.

O projeto devera resultar em um prototipo funcional, organizado, documentado, de facil manutencao e adequado para posterior avaliacao metrologica e validacao operacional."""


JUSTIFICATION = """O equipamento possui construcao mecanica robusta e componentes termicos e hidraulicos potencialmente reutilizaveis, porem utiliza eletronica analogica antiga, com grande quantidade de placas, componentes discretos, transformadores, potenciometros e conexoes de dificil manutencao.

A modernizacao permite reaproveitar a estrutura original e reduzir o custo de aquisicao de um novo banho termostatizado. Tambem facilita a manutencao, a substituicao de componentes e o ajuste digital da temperatura.

O retrofit sera inicialmente executado como prototipo de baixo custo. Apos a comprovacao do funcionamento, estabilidade, seguranca e desempenho termico, poderao ser implementadas melhorias adicionais, como protecao independente contra sobretemperatura, sensor de nivel, alarme, indicadores luminosos, disjuntor bipolar, registro de dados e controlador de maior qualidade.

Dados tecnicos identificados:
- Equipamento: banho termostatizado UH4.
- Fabricante original: VEB MLW Prufgerate-Werk Medingen Sitz Freital.
- Origem: Republica Democratica Alema - GDR.
- Numero de fabricacao identificado: 4606.
- Numero de serie identificado na etiqueta: ELN 13892520.
- Tensao nominal: 220 Vca.
- Potencia nominal informada: aproximadamente 1,72 kW.
- Resistencia tubular de imersao: aproximadamente 30 ohms.
- Corrente teorica em 220 V: I = V / R = 220 / 30 = 7,33 A.
- Potencia teorica em 220 V: P = V^2 / R = 220^2 / 30 = 1.613 W.
- Motor: VEB Elmo Barleben DDR, modelo 1055.4, 220 Vca, 25 W, capacitor permanente 2 uF / 380 Vca.
- Controlador: REX-C100FK02-V*DA, alimentacao 220 Vca, entrada termopar K, saida SSR.
- SSR: SSR-40DA, entrada 3 a 32 Vcc, saida 24 a 380 Vca.

Arquitetura eletrica prevista:
Rede 220 Vca -> entrada IEC -> fusivel -> chave liga/desliga -> distribuicao para controlador, motor e potencia da resistencia.
Comando SSR: borne 4 do REX-C100 no borne 3 positivo do SSR e borne 5 do REX-C100 no borne 4 negativo do SSR.
Sensor: termopar K nos bornes 9 e 10 do controlador.
Aterramento: pino de terra da entrada IEC ligado a estrutura metalica, cuba, suportes acessiveis e carcaca do motor, quando aplicavel.

Restricao tecnica: nao definir a ligacao do motor somente pelas cores dos fios. Identificar comum, enrolamento principal e auxiliar por medicao de resistencia antes da energizacao."""


RESULTS = """1. Controle digital da temperatura por controlador PID.
2. Acionamento da resistencia por rele de estado solido.
3. Circulacao continua da agua pelo motor original.
4. Leitura de temperatura por termopar tipo K.
5. Substituicao da eletronica analogica antiga por circuito simplificado.
6. Manutencao da cuba, estrutura, resistencia, motor e conjunto hidraulico originais, se aprovados nos ensaios.
7. Instalacao de alimentacao por entrada IEC com chave e fusivel.
8. Aterramento adequado de todas as partes metalicas acessiveis.
9. Organizacao e identificacao do chicote eletrico.
10. Elaboracao de esquema eletrico atualizado.
11. Execucao de testes de continuidade, isolamento, aquecimento, circulacao e estabilidade.
12. Emissao de relatorio tecnico do retrofit.
13. Possibilidade de calibracao ou caracterizacao termica apos conclusao da montagem.
14. Equipamento funcional sem declarar aprovacao para uso critico antes da conclusao dos testes de seguranca e desempenho."""


STAGES = [
    (1, "ETAPA 01 - Levantamento e identificacao", "concluido", 100, "Identificacao do fabricante, modelo, tensao, potencia, motor, resistencia, placas eletronicas, controles e conexoes originais."),
    (2, "ETAPA 02 - Registro fotografico", "concluido", 100, "Registro externo, interno, etiquetas, motor, capacitor, resistencia, controlador original, placas e fiacao."),
    (3, "ETAPA 03 - Desmontagem da eletronica original", "concluido", 100, "Remocao das placas analogicas, transformadores e circuitos de controle que nao serao reutilizados."),
    (4, "ETAPA 04 - Avaliacao da estrutura mecanica", "concluido", 100, "Verificacao preliminar da cuba, estrutura, suportes, conjunto hidraulico e mecanismo de circulacao."),
    (5, "ETAPA 05 - Limpeza do motor e da estrutura", "em_andamento", 80, "Limpeza com pincel, ar controlado, pano e produto apropriado, evitando danos ao verniz dos enrolamentos."),
    (6, "ETAPA 06 - Avaliacao da resistencia", "em_teste", 70, "Medicao de aproximadamente 30 ohms. Ainda e necessario ensaio de isolamento entre terminais e carcaca."),
    (7, "ETAPA 07 - Avaliacao do motor", "em_andamento", 60, "Motor identificado como 220 V, 25 W, com capacitor permanente de 2 uF. Falta confirmar a ligacao dos enrolamentos e executar teste funcional."),
    (8, "ETAPA 08 - Definicao da arquitetura do retrofit", "concluido", 100, "Definida arquitetura com REX-C100, termopar K, SSR-40DA, dissipador, entrada IEC, fusivel e reaproveitamento do motor e da resistencia."),
    (9, "ETAPA 09 - Aquisicao dos componentes", "aguardando_compra", 80, "Controlador, termopar, SSR e dissipador adquiridos. Confirmar compra do capacitor, fusivel, cabos, terminais e modulo IEC."),
    (10, "ETAPA 10 - Instalacao mecanica do controlador", "em_andamento", 80, "Controlador posicionado no painel, com aproximadamente 2 cm de distancia do SSR."),
    (11, "ETAPA 11 - Instalacao do SSR e dissipador", "em_andamento", 80, "SSR instalado em dissipador. Confirmar pasta termica, aperto, ventilacao e protecao dos terminais."),
    (12, "ETAPA 12 - Refazimento da fiacao", "em_andamento", 65, "Ligacao do controlador, SSR, resistencia e entrada IEC em execucao. Motor ainda nao ligado definitivamente."),
    (13, "ETAPA 13 - Identificacao dos fios do motor", "a_fazer", 20, "Medir resistencia entre os fios do motor e identificar comum, enrolamento principal e auxiliar antes de energizar."),
    (14, "ETAPA 14 - Testes eletricos sem energizacao", "a_fazer", 20, "Executar continuidade, ausencia de curto, aterramento, isolamento e conferencia completa do circuito."),
    (15, "ETAPA 15 - Energizacao controlada", "a_fazer", 0, "Primeiro teste com limitacao de corrente e resistencia inicialmente desconectada, seguido de teste do controlador, SSR e motor."),
    (16, "ETAPA 16 - Teste de circulacao", "a_fazer", 0, "Confirmar circulacao da agua e ausencia de vazamentos."),
    (17, "ETAPA 17 - Teste de aquecimento", "a_fazer", 0, "Confirmar aquecimento controlado e corrente compativel com aproximadamente 1,6 kW."),
    (18, "ETAPA 18 - Ajuste PID", "a_fazer", 0, "Ajustar parametros PID e registrar overshoot e oscilacao."),
    (19, "ETAPA 19 - Estudo de estabilidade termica", "a_fazer", 0, "Avaliar estabilidade nos pontos de 30 C, 40 C e 50 C."),
    (20, "ETAPA 20 - Organizacao final do chicote", "a_fazer", 0, "Organizar cabos, terminais, protecoes e identificacoes."),
    (21, "ETAPA 21 - Fechamento e acabamento", "a_fazer", 0, "Fechamento mecanico, acabamento e revisao visual final."),
    (22, "ETAPA 22 - Relatorio tecnico", "a_fazer", 0, "Emitir relatorio tecnico do retrofit."),
    (23, "ETAPA 23 - Avaliacao metrologica", "a_fazer", 0, "Avaliar necessidade de calibracao ou caracterizacao termica apos testes funcionais."),
]


MATERIALS = [
    ("Material - Controlador PID REX-C100", "Qtd. 1. 220 V, saida SSR, entrada termopar K. Valor confirmado somente se o kit completo corresponder ao valor real comprado.", Decimal("181.65")),
    ("Material - Rele de estado solido SSR-40DA", "Qtd. 1. Entrada 3-32 Vcc, saida 24-380 Vca.", Decimal("0")),
    ("Material - Dissipador de aluminio para SSR", "Qtd. 1. Status: adquirido.", Decimal("0")),
    ("Material - Pasta termica", "Qtd. 1. Confirmar status adquirido ou pendente.", Decimal("0")),
    ("Material - Termopar tipo K", "Qtd. 1. Faixa do kit ate 400 C.", Decimal("0")),
    ("Material - Entrada IEC C14", "Qtd. 1. Chave iluminada e porta-fusivel.", Decimal("0")),
    ("Material - Fusivel retardado T10 A / 250 V", "Qtd. 2. Um em uso e um reserva.", Decimal("0")),
    ("Material - Capacitor permanente para motor", "Qtd. 1. 2 uF / 450 Vca recomendado.", Decimal("0")),
    ("Material - Cabo de alimentacao", "Qtd. 1. 3 x 1,5 mm2 com terra.", Decimal("0")),
    ("Material - Cabo de potencia", "Qtd. 2 m. 1,5 ou 2,5 mm2.", Decimal("0")),
    ("Material - Cabo de comando", "Qtd. 2 m. 0,5 a 0,75 mm2.", Decimal("0")),
    ("Material - Cabo/extensao para termopar K", "Qtd. conforme necessidade. Usar cabo compativel com termopar K.", Decimal("0")),
    ("Material - Terminais Faston", "Qtd. 10. Confirmar disponibilidade.", Decimal("0")),
    ("Material - Terminais tipo olhal", "Qtd. 10. Confirmar disponibilidade.", Decimal("0")),
    ("Material - Terminais ilhos", "Qtd. 20. Status pendente.", Decimal("0")),
    ("Material - Espaguete termo-retratil", "Qtd. 2 m. Confirmar disponibilidade.", Decimal("0")),
    ("Material - Abracadeiras de nylon", "Qtd. 20. Status pendente.", Decimal("0")),
    ("Material - Borne de ligacao", "Qtd. 1. Reaproveitado, minimo 20 A.", Decimal("0")),
    ("Material - Fio verde/amarelo de aterramento", "Qtd. conforme necessidade. Parcialmente instalado.", Decimal("0")),
    ("Material - Etiquetas ou anilhas de identificacao", "Qtd. 1 conjunto. Status pendente.", Decimal("0")),
]


COSTS = [
    ("Custo estimado - Entrada IEC e fusiveis", Decimal("45.00"), "Estimativa entre R$ 30,00 e R$ 60,00."),
    ("Custo estimado - Capacitor", Decimal("30.00"), "Estimativa entre R$ 20,00 e R$ 40,00."),
    ("Custo estimado - Cabos e terminais", Decimal("90.00"), "Estimativa entre R$ 60,00 e R$ 120,00."),
    ("Custo estimado - Consumiveis", Decimal("45.00"), "Pasta termica, termo-retratil e consumiveis. Estimativa entre R$ 30,00 e R$ 60,00."),
    ("Custo estimado - Contingencia", Decimal("80.00"), "Reserva tecnica estimada."),
]


RISKS = [
    ("Risco 01 - Choque eletrico", "Operacao em 220 Vca proxima a agua. Probabilidade media, impacto critico. Mitigar com aterramento, isolamento, terminais protegidos, ensaio eletrico, revisao tecnica e uso de DR na instalacao."),
    ("Risco 02 - Fuga eletrica da resistencia", "Fuga eletrica da resistencia para a cuba. Probabilidade media, impacto critico. Mitigar com teste de isolamento com megometro antes da energizacao."),
    ("Risco 03 - Superaquecimento por falha do SSR", "SSR fechado pode manter aquecimento. Probabilidade baixa a media, impacto alto. Mitigar com monitoramento e futura protecao independente contra sobretemperatura."),
    ("Risco 04 - Resistencia sem agua", "Funcionamento da resistencia sem agua. Probabilidade media, impacto alto. Mitigar com procedimento operacional, nivel minimo e futura protecao por nivel."),
    ("Risco 05 - Ligacao incorreta do motor", "Ligacao incorreta do motor ou capacitor. Probabilidade media, impacto alto. Mitigar identificando enrolamentos por medicao."),
    ("Risco 06 - Superaquecimento do SSR", "Dissipacao insuficiente. Probabilidade media, impacto medio/alto. Mitigar com dissipador, pasta termica, ventilacao e medicao de temperatura."),
    ("Risco 07 - Falha do SSR de baixo custo", "Baixa qualidade do SSR. Probabilidade media, impacto alto. Mitigar com testes progressivos e substituicao futura por componente industrial."),
    ("Risco 08 - Leitura incorreta do termopar", "Termopar incompatvel ou polaridade invertida. Probabilidade media, impacto alto. Mitigar usando termopar K e validando com padrao externo."),
    ("Risco 09 - Terminais energizados acessiveis", "Contato acidental com terminais energizados. Probabilidade media, impacto critico. Mitigar com protecoes, tampa, isolamento e organizacao do chicote."),
    ("Risco 10 - Desempenho termico insuficiente", "Controle instavel ou baixa uniformidade. Probabilidade media, impacto medio. Mitigar com ajuste PID, circulacao adequada e estudo de uniformidade."),
]


CHECKS = [
    "Confirmar tensao de alimentacao do equipamento.",
    "Confirmar fusivel T10 A / 250 V.",
    "Confirmar capacidade do modulo IEC.",
    "Confirmar aperto dos terminais.",
    "Confirmar ausencia de fios desencapados.",
    "Confirmar uso de terminais adequados.",
    "Confirmar aterramento da estrutura e da cuba.",
    "Confirmar continuidade do terra.",
    "Confirmar ausencia de curto entre condutores de alimentacao.",
    "Confirmar resistencia de aproximadamente 30 ohms.",
    "Executar teste de isolamento com megometro, preferencialmente a 500 Vcc.",
    "Confirmar posicao do SSR, pasta termica e ventilacao do dissipador.",
    "Confirmar polaridade do comando do SSR.",
    "Confirmar termopar nos bornes 9 e 10 e sua polaridade.",
    "Identificar fios do motor por resistencia.",
    "Confirmar ligacao correta do capacitor.",
    "Confirmar que a resistencia esta totalmente submersa.",
    "Energizar inicialmente sem a resistencia conectada.",
    "Confirmar inicializacao do REX-C100 e leitura coerente do termopar.",
    "Testar motor separadamente, sentido de rotacao, ruido, vibracao e aquecimento.",
    "Conectar a resistencia somente apos aprovacao dos testes anteriores.",
    "Monitorar corrente com alicate amperimetro, temperatura do dissipador e temperatura do motor.",
    "Confirmar circulacao da agua e ausencia de vazamentos.",
    "Registrar tempo de aquecimento, overshoot, oscilacao, corrente total e tensao da rede.",
]


ACCEPTANCE = [
    "Equipamento liga sem desarme do fusivel.",
    "Controlador inicializa normalmente.",
    "Termopar apresenta leitura coerente.",
    "Motor parte sem auxilio manual.",
    "Circulacao de agua e observada.",
    "Resistencia aquece somente quando comandada.",
    "SSR desliga a resistencia quando solicitado.",
    "Corrente da resistencia e coerente com aproximadamente 1,6 kW.",
    "Nao existe fuga eletrica detectavel para a carcaca.",
    "Terra apresenta continuidade adequada.",
    "Nao existem vazamentos.",
    "Dissipador permanece em temperatura operacional aceitavel.",
    "Motor nao apresenta superaquecimento anormal.",
    "Sistema atinge 30 C, 40 C e 50 C.",
    "Temperatura estabiliza dentro do limite definido.",
    "Overshoot inicial registrado e avaliado.",
    "Todos os fios ficam identificados.",
    "Terminais energizados ficam protegidos.",
    "Esquema eletrico final anexado.",
    "Relatorio tecnico emitido.",
]


class Command(BaseCommand):
    help = "Preenche de forma idempotente o projeto DEV-0002 - Retrofit de banho termostatizado."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Grava as alteracoes no banco. Sem esta opcao, apenas mostra o resumo previsto.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        responsavel = self._find_responsavel()
        cliente = self._find_cliente_ds()
        campos_nao_preenchidos = [
            "categoria",
            "subarea",
            "fase_atual",
            "visibilidade",
            "projeto_relacionado",
            "produto_equipamento_relacionado",
            "fabricante_original",
            "origem",
            "modelo",
            "numero_fabricacao",
            "numero_serie_identificado",
            "tensao_nominal",
            "frequencia",
            "potencia_nominal",
            "escopo_incluido",
            "escopo_excluido",
            "risco_model_dedicado",
            "checklist_model_dedicado",
            "material_model_dedicado",
            "historico_model_dedicado",
            "arquivo_placeholder_sem_arquivo",
        ]

        resumo = {
            "projeto": PROJECT_CODE,
            "modo": "gravacao" if apply_changes else "pre-visualizacao",
            "etapas": len(STAGES),
            "materiais": len(MATERIALS),
            "riscos": len(RISKS),
            "verificacoes": len(CHECKS) + len(ACCEPTANCE),
            "custos": len(COSTS) + len(MATERIALS),
            "campos_nao_preenchidos": campos_nao_preenchidos,
        }
        self._print_summary(resumo)

        if not apply_changes:
            self.stdout.write(self.style.WARNING("Nenhum dado foi gravado. Revise o resumo e execute com --apply para gravar."))
            return

        with transaction.atomic():
            projeto, created = Projeto.objects.update_or_create(
                codigo=PROJECT_CODE,
                defaults={
                    "nome": PROJECT_NAME,
                    "tipo": "retrofit",
                    "area": "interno",
                    "status": "em_desenvolvimento",
                    "prioridade": "alta",
                    "responsavel": responsavel,
                    "cliente": cliente,
                    "objetivo": OBJECTIVE,
                    "justificativa": JUSTIFICATION,
                    "resultado_esperado": RESULTS,
                    "data_inicio": date(2026, 7, 16),
                    "previsao_conclusao": date(2026, 8, 15),
                    "orcamento_previsto": Decimal("500.00"),
                    "custo_real": None,
                },
            )
            self._upsert_stages(projeto, responsavel)
            self._upsert_materials_and_costs(projeto)
            self._upsert_risks(projeto)
            self._upsert_checks(projeto)
            self._upsert_acceptance(projeto)

        self.stdout.write(self.style.SUCCESS(f"Projeto {'criado' if created else 'atualizado'}: {projeto}"))
        self._print_summary(resumo)

    def _find_responsavel(self):
        diego = User.objects.filter(username__icontains="diego").first()
        if diego:
            return diego
        return User.objects.filter(is_superuser=True).order_by("id").first()

    def _find_cliente_ds(self):
        return (
            Cliente.objects.filter(razao_social__icontains="DS Cient").first()
            or Cliente.objects.filter(nome_empresa__icontains="DS Cient").first()
        )

    def _upsert_stages(self, projeto, responsavel):
        for ordem, titulo, status, percentual, descricao in STAGES:
            self._upsert(
                ProjetoTarefa,
                {"projeto": projeto, "titulo": titulo},
                {
                    "ordem": ordem,
                    "status": status,
                    "responsavel": responsavel,
                    "descricao": descricao,
                    "observacao": f"Percentual planejado/estimado: {percentual}%.",
                },
            )

    def _upsert_materials_and_costs(self, projeto):
        for descricao, observacoes, custo in MATERIALS:
            self._upsert(
                ProjetoCusto,
                {"projeto": projeto, "descricao": descricao},
                {
                    "custo_componentes": custo,
                    "horas_tecnicas": Decimal("0"),
                    "valor_hora_tecnica": Decimal("0"),
                    "custo_outros": Decimal("0"),
                    "preco_estimado_venda": None,
                    "payback_esperado": "",
                    "viabilidade": "em_analise",
                    "observacoes": observacoes,
                },
            )
        for descricao, custo, observacoes in COSTS:
            self._upsert(
                ProjetoCusto,
                {"projeto": projeto, "descricao": descricao},
                {
                    "custo_componentes": custo,
                    "horas_tecnicas": Decimal("0"),
                    "valor_hora_tecnica": Decimal("0"),
                    "custo_outros": Decimal("0"),
                    "preco_estimado_venda": None,
                    "payback_esperado": "",
                    "viabilidade": "em_analise",
                    "observacoes": observacoes,
                },
            )

    def _upsert_risks(self, projeto):
        for titulo, descricao in RISKS:
            self._upsert(
                ProjetoTeste,
                {"projeto": projeto, "tipo_teste": titulo},
                {
                    "data_teste": date(2026, 7, 22),
                    "resultado": "em_analise",
                    "condicao_ambiental": "Registro de risco do projeto",
                    "observacao_tecnica": descricao,
                    "conclusao_tecnica": "Risco registrado para mitigacao antes da liberacao operacional.",
                },
            )

    def _upsert_checks(self, projeto):
        for ordem, descricao in enumerate(CHECKS, start=1):
            self._upsert(
                ProjetoTeste,
                {"projeto": projeto, "tipo_teste": f"Verificacao {ordem:02d}"},
                {
                    "data_teste": date(2026, 7, 28),
                    "resultado": "em_analise",
                    "condicao_ambiental": "Checklist antes/durante energizacao",
                    "observacao_tecnica": descricao,
                    "conclusao_tecnica": "Pendente de execucao e registro de evidencia.",
                },
            )

    def _upsert_acceptance(self, projeto):
        for ordem, descricao in enumerate(ACCEPTANCE, start=1):
            self._upsert(
                ProjetoTeste,
                {"projeto": projeto, "tipo_teste": f"Criterio de aceite {ordem:02d}"},
                {
                    "data_teste": date(2026, 8, 15),
                    "resultado": "em_analise",
                    "condicao_ambiental": "Aceitacao preliminar",
                    "observacao_tecnica": descricao,
                    "conclusao_tecnica": "Aceitacao preliminar: variacao maxima de +/-1,0 C no ponto de medicao apos estabilizacao. Aceitacao final depende de caracterizacao termica e avaliacao metrologica.",
                },
            )

    def _upsert(self, model, lookup, defaults):
        obj = model.objects.filter(**lookup).order_by("created_at").first()
        if obj:
            for field, value in defaults.items():
                setattr(obj, field, value)
            obj.save()
            return obj, False
        data = {**lookup, **defaults}
        return model.objects.create(**data), True

    def _print_summary(self, resumo):
        self.stdout.write("")
        self.stdout.write("Resumo do preenchimento previsto")
        self.stdout.write(f"- Projeto: {resumo['projeto']}")
        self.stdout.write(f"- Modo: {resumo['modo']}")
        self.stdout.write(f"- Etapas: {resumo['etapas']}")
        self.stdout.write(f"- Materiais: {resumo['materiais']}")
        self.stdout.write(f"- Riscos: {resumo['riscos']}")
        self.stdout.write(f"- Verificacoes: {resumo['verificacoes']}")
        self.stdout.write(f"- Custos/registros financeiros: {resumo['custos']}")
        self.stdout.write("- Campos sem preenchimento direto no model:")
        for campo in resumo["campos_nao_preenchidos"]:
            self.stdout.write(f"  - {campo}")
