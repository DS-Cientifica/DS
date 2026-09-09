from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from projetos.models import Projeto, ProjetoCusto, ProjetoTarefa, ProjetoTeste


DATA_REFERENCIA = date(2026, 8, 15)


PROJETOS = [
    {
        "codigo": "DEV-0003",
        "nome": "Laboratorio movel de calibracao e exposicao",
        "tipo": "servico",
        "area": "calibracao",
        "prioridade": "alta",
        "objetivo": (
            "Implantar uma unidade movel DS Cientifica em van de teto alto para apoio a calibracoes em campo, "
            "demonstracao de equipamentos, diagnostico de instrumentacao, treinamentos curtos e atendimento comercial. "
            "A operacao deve separar formalmente o modo calibracao do modo exposicao, controlar transporte de padroes, "
            "condicoes ambientais, energia, seguranca, carga por eixo e rastreabilidade dos registros no AXION."
        ),
        "justificativa": (
            "A unidade aproxima a empresa dos clientes industriais, reduz deslocamentos de instrumentos e cria um canal "
            "tecnico-comercial. O limite de R$ 150.000 exige van usada, adaptacao modular e reaproveitamento de padroes. "
            "A designacao laboratorio movel nao autoriza alegacao de acreditacao: qualquer atividade acreditada dependera "
            "de inclusao formal das instalacoes moveis, metodos, faixas e CMC no escopo concedido pela Cgcre."
        ),
        "resultado": (
            "Unidade movel funcional e regularizada, com projeto eletrico e mecanico, ART/CSV quando aplicavel, bancadas "
            "seguras, alimentacao externa, climatizacao, armazenamento protegido, procedimentos operacionais, estudo de "
            "carga, caracterizacao ambiental e operacao piloto. Aprovacao tecnica, metrologica e comercial permanecera "
            "pendente ate conclusao dos testes e analise critica."
        ),
        "tarefas": [
            "Definir demanda, regioes atendidas e indicadores de utilizacao",
            "Definir escopo inicial de pressao e sinais de processo",
            "Especificar van, carga util, altura e volume interno",
            "Inspecionar veiculo, historico, estrutura e manutencao",
            "Elaborar layout, distribuicao de massa e pontos de fixacao",
            "Projetar instalacao eletrica, protecoes, UPS e alimentacao externa",
            "Projetar isolamento, climatizacao, bancadas e armarios",
            "Regularizar modificacoes, ART, CSV e CRLV-e quando aplicavel",
            "Instalar mobiliario, seguranca, rastreamento e identidade visual",
            "Criar procedimentos de transporte, acesso e estabilizacao",
            "Caracterizar temperatura e recuperacao apos abertura de portas",
            "Validar metodos e incertezas nas condicoes moveis",
            "Executar pesagem final e verificar carga por eixo",
            "Realizar operacao piloto sem alegacao de acreditacao",
            "Analisar resultados, riscos, custos e decisao de continuidade",
        ],
        "custos": [
            ("Van usada teto alto", "82000.00"),
            ("Inspecao e manutencao inicial", "8000.00"),
            ("Projeto, ART, CSV e documentacao", "4000.00"),
            ("Isolamento, revestimento e piso", "12000.00"),
            ("Bancadas, armarios e fixacoes", "9000.00"),
            ("Instalacao eletrica e alimentacao externa", "9000.00"),
            ("Climatizacao e ventilacao", "6000.00"),
            ("Informatica e conectividade", "4000.00"),
            ("Seguranca e rastreamento", "3000.00"),
            ("Kit inicial de demonstracao", "7000.00"),
            ("Identidade visual", "2000.00"),
            ("Contingencia", "4000.00"),
        ],
        "riscos": [
            "Veiculo usado com falhas mecanicas ou estruturais",
            "Excesso de peso total ou por eixo",
            "Instabilidade ambiental durante calibracoes",
            "Dano ou deriva de padroes durante transporte",
            "Mistura simultanea de calibracao e exposicao",
            "Modificacao veicular sem regularizacao adequada",
            "Falha eletrica, incendio ou uso incorreto de gerador",
            "Alegacao indevida de servico acreditado",
            "Demanda insuficiente para recuperar o investimento",
        ],
        "criterios": [
            "Veiculo aprovado em inspecao independente",
            "Peso e distribuicao por eixo dentro dos limites",
            "Instalacao eletrica documentada e aprovada",
            "Padroes fixados e protegidos contra impacto",
            "Caracterizacao ambiental concluida",
            "Metodos e planilhas tecnicas validados",
            "Procedimentos de calibracao e exposicao separados",
            "Operacao piloto sem ocorrencia critica",
            "Viabilidade comercial aprovada pela direcao",
        ],
    },
    {
        "codigo": "DEV-0004",
        "nome": "Laboratorio fixo de calibracao e exposicao",
        "tipo": "servico",
        "area": "calibracao",
        "prioridade": "alta",
        "objetivo": (
            "Implantar laboratorio fixo DS Cientifica, em imovel existente ou alugado de aproximadamente 90 a 120 m2, "
            "para calibracoes de pressao, temperatura e sinais eletricos de processo, com recepcao, triagem, areas "
            "tecnicas segregadas, sala de padroes, escritorio de certificados e showroom separado das calibracoes."
        ),
        "justificativa": (
            "A instalacao fixa oferece maior estabilidade ambiental, menor vibracao, melhor segregacao, produtividade e "
            "condicoes mais favoraveis a futura acreditacao. O investimento de R$ 150.000 permite uma primeira fase "
            "controlada, mas nao um laboratorio multigrandezas completo. Fisico-quimica deve iniciar como demonstracao "
            "ate que metodos, materiais de referencia e incertezas sejam avaliados."
        ),
        "resultado": (
            "Laboratorio implantado com fluxo de recebimento ate expedicao, areas segregadas, climatizacao, monitoramento, "
            "circuitos eletricos dedicados, bancadas seguras, padroes rastreados, metodos controlados e integracao com o "
            "AXION. A liberacao para uso dependera de caracterizacao ambiental, validacao dos metodos, competencia do "
            "pessoal e analise critica da direcao."
        ),
        "tarefas": [
            "Validar carteira de clientes e demanda mensal minima",
            "Definir escopo, faixas, tolerancias e CMC pretendida",
            "Selecionar imovel e verificar requisitos legais locais",
            "Elaborar planta com fluxo e segregacao das areas",
            "Projetar climatizacao e monitoramento ambiental",
            "Projetar circuitos eletricos, aterramento, DPS, DR e UPS",
            "Executar adequacoes civis, piso, pintura e divisorias",
            "Instalar bancadas, armarios, anteparos e sinalizacao",
            "Especificar e adquirir padroes apos estudo de incerteza",
            "Calibrar e cadastrar padroes e equipamentos auxiliares",
            "Criar procedimentos de recebimento e descontaminacao",
            "Caracterizar ambientes e meios geradores",
            "Validar metodos, planilhas e sistema AXION",
            "Qualificar e autorizar tecnicos",
            "Realizar operacao piloto e analise de viabilidade",
        ],
        "custos": [
            ("Projeto, layout, ART e regularizacao", "4000.00"),
            ("Divisorias, pintura, piso e adequacoes", "14000.00"),
            ("Instalacao eletrica e aterramento", "8000.00"),
            ("Climatizacao e controle ambiental", "10000.00"),
            ("Bancadas e armarios tecnicos", "12000.00"),
            ("Seguranca, incendio e acesso", "4000.00"),
            ("Sistema de pressao", "30000.00"),
            ("Sinais eletricos de processo", "12000.00"),
            ("Sistema de temperatura", "20000.00"),
            ("Monitoramento ambiental e acessorios", "5000.00"),
            ("Informatica e rede", "7000.00"),
            ("Calibracoes, EP e preparacao do sistema", "10000.00"),
            ("Contingencia", "14000.00"),
        ],
        "riscos": [
            "Imovel inadequado ao fluxo ou a potencia eletrica",
            "Condicoes ambientais sem estabilidade suficiente",
            "Compra de padrao sem capacidade para a CMC pretendida",
            "Contaminacao cruzada entre recebimento e calibracao",
            "Interferencia do showroom nas areas tecnicas",
            "Falta de demanda para atingir o ponto de equilibrio",
            "Custos recorrentes superiores ao previsto",
            "Ausencia de evidencia de competencia dos tecnicos",
            "Uso indevido de alegacao ou simbolo de acreditacao",
        ],
        "criterios": [
            "Layout e fluxo aprovados pela direcao tecnica",
            "Instalacoes eletricas e seguranca aprovadas",
            "Caracterizacao ambiental concluida",
            "Padroes com rastreabilidade e adequacao demonstradas",
            "Metodos e orcamentos de incerteza validados",
            "Tecnicos avaliados e formalmente autorizados",
            "AXION validado para registros e certificados",
            "Operacao piloto concluida sem falha critica",
            "Demanda minima e ponto de equilibrio demonstrados",
        ],
    },
    {
        "codigo": "DEV-0005",
        "nome": "Acreditacao ISO IEC 17025 - Pressao e temperatura",
        "tipo": "metodo",
        "area": "qualidade",
        "prioridade": "alta",
        "objetivo": (
            "Implantar o sistema de gestao e demonstrar competencia tecnica para solicitar a acreditacao Cgcre segundo a "
            "ABNT NBR ISO/IEC 17025:2017, inicialmente em instalacoes permanentes, para pressao relativa e termometria de "
            "contato. O escopo deve ser compativel com a NIT-Dicla-012, com metodos, faixas e CMC sustentados por evidencias."
        ),
        "justificativa": (
            "A acreditacao aumenta a confianca nos resultados e a competitividade em contratos industriais. O escopo "
            "inicial deve permanecer controlado: manometros analogicos e digitais, transmissores quando a medicao eletrica "
            "estiver coberta, termometros mecanicos e sistemas com termopar ou termorresistencia. Pressao absoluta, baixa "
            "pressao diferencial, infravermelho, umidade, campo e instalacoes moveis ficam fora da primeira solicitacao."
        ),
        "resultado": (
            "Sistema ISO/IEC 17025 implementado e operando, pessoal competente, padroes rastreados, metodos verificados, "
            "orcamentos de incerteza validados, participacao em EP ou comparacoes, auditoria interna e analise critica "
            "concluidas, documentacao submetida no Orquestra e nao conformidades tratadas. O resultado final permanece "
            "como validacao pendente ate decisao formal da Cgcre."
        ),
        "tarefas": [
            "Definir escopo conforme NIT-Dicla-012 e demanda",
            "Definir mensurandos, faixas, metodos e CMC-alvo",
            "Elaborar orcamentos preliminares de incerteza",
            "Especificar e adquirir padroes adequados",
            "Calibrar padroes conforme politica de rastreabilidade",
            "Adequar infraestrutura e caracterizar ambientes",
            "Caracterizar sistemas de pressao e blocos secos",
            "Elaborar procedimentos gerenciais e tecnicos",
            "Validar planilhas e controles do AXION",
            "Treinar, avaliar e autorizar os tecnicos",
            "Executar calibracoes piloto e controles intermediarios",
            "Participar de EP ou comparacao em pressao",
            "Participar de EP ou comparacao em temperatura",
            "Realizar auditoria interna completa",
            "Realizar analise critica pela direcao",
            "Cadastrar solicitacao e documentos no Orquestra",
            "Receber avaliacao e tratar eventuais nao conformidades",
            "Aguardar decisao formal antes de alegar acreditacao",
        ],
        "custos": [
            ("Climatizacao e monitoramento", "7000.00"),
            ("Instalacao eletrica e circuitos tecnicos", "4000.00"),
            ("Bancadas, armarios e anteparo", "8000.00"),
            ("Segregacao e sinalizacao", "3000.00"),
            ("Sistema de pressao pneumatica", "14000.00"),
            ("Sistema de pressao hidraulica", "16000.00"),
            ("Adaptadores, mangueiras e seguranca", "6000.00"),
            ("Bloco de baixa e media temperatura", "14000.00"),
            ("Bloco de alta temperatura", "14000.00"),
            ("Termometro, leitor e sensor de referencia", "8000.00"),
            ("Insertos, cabos e suportes", "2000.00"),
            ("Multimetro e calibrador de processo", "6000.00"),
            ("Instrumentos ambientais e barometro", "4000.00"),
            ("Calibracoes iniciais dos padroes", "9000.00"),
            ("Sistema de gestao, treinamento e avaliacao", "18000.00"),
            ("Ensaios de proficiencia e comparacoes", "6000.00"),
            ("Contingencia", "11000.00"),
        ],
        "riscos": [
            "Padroes incapazes de sustentar a CMC solicitada",
            "Escopo excessivo para recursos e equipe disponiveis",
            "Blocos secos sem caracterizacao suficiente",
            "Rastreabilidade inadequada dos padroes",
            "Ausencia ou resultado insatisfatorio em EP",
            "Tecnicos sem evidencia objetiva de competencia",
            "Planilhas ou AXION com calculos nao validados",
            "Regras de decisao e contratos incompletos",
            "Custos de avaliacao e correcoes acima da provisao",
            "Alegacao de acreditacao antes da decisao da Cgcre",
        ],
        "criterios": [
            "Escopo e CMC sustentados por evidencias",
            "Padroes rastreados e adequados a cada faixa",
            "Ambientes e meios geradores caracterizados",
            "Metodos, planilhas e software validados",
            "Pessoal competente e autorizado por atividade",
            "Resultados satisfatorios em EP ou comparacoes",
            "Auditoria interna completa e tratada",
            "Analise critica pela direcao concluida",
            "Documentacao aceita para avaliacao pela Cgcre",
            "Acreditacao somente declarada apos concessao formal",
        ],
    },
]


class Command(BaseCommand):
    help = "Preenche, com previa e de forma idempotente, os projetos DEV-0003 a DEV-0005."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Grava as alteracoes. Sem esta opcao, somente apresenta a previa.",
        )

    def handle(self, *args, **options):
        aplicar = options["apply"]
        responsavel = User.objects.filter(is_superuser=True).order_by("id").first()
        self.stdout.write("PROJETOS DE LABORATORIO - PREVIA CONTROLADA")
        self.stdout.write(f"Modo: {'GRAVACAO' if aplicar else 'PRE-VISUALIZACAO'}")

        for dados in PROJETOS:
            total = sum(Decimal(valor) for _, valor in dados["custos"])
            self.stdout.write(
                f"{dados['codigo']} | {dados['nome']} | tarefas={len(dados['tarefas'])} | "
                f"custos={len(dados['custos'])} | riscos={len(dados['riscos'])} | "
                f"criterios={len(dados['criterios'])} | total=R$ {total:.2f}"
            )
            if total != Decimal("150000.00"):
                raise ValueError(f"Orcamento de {dados['codigo']} nao totaliza R$ 150.000,00.")

        if not aplicar:
            self.stdout.write(self.style.WARNING("Nenhum dado foi gravado. Use --apply apos revisar a previa."))
            return

        with transaction.atomic():
            for dados in PROJETOS:
                projeto, criado = Projeto.objects.update_or_create(
                    codigo=dados["codigo"],
                    defaults={
                        "nome": dados["nome"],
                        "tipo": dados["tipo"],
                        "area": dados["area"],
                        "status": "em_analise",
                        "prioridade": dados["prioridade"],
                        "responsavel": responsavel,
                        "cliente": None,
                        "objetivo": dados["objetivo"],
                        "justificativa": dados["justificativa"],
                        "data_inicio": None,
                        "previsao_conclusao": None,
                        "orcamento_previsto": Decimal("150000.00"),
                        "custo_real": Decimal("0.00"),
                        "resultado_esperado": dados["resultado"],
                    },
                )
                self._gravar_relacionados(projeto, dados, responsavel)
                acao = "criado" if criado else "atualizado"
                self.stdout.write(self.style.SUCCESS(f"{projeto.codigo} {acao}."))

        self.stdout.write(self.style.SUCCESS("Projetos cadastrados com sucesso."))

    def _gravar_relacionados(self, projeto, dados, responsavel):
        for ordem, titulo in enumerate(dados["tarefas"], start=1):
            chave = f"[{dados['codigo']}] ETAPA {ordem:02d} - {titulo}"
            self._upsert(
                ProjetoTarefa,
                {"projeto": projeto, "titulo": chave},
                {
                    "descricao": titulo,
                    "responsavel": responsavel,
                    "prazo": None,
                    "status": "a_fazer",
                    "observacao": "Etapa planejada; execucao e aprovacao ainda pendentes.",
                    "ordem": ordem,
                },
            )

        for descricao, valor in dados["custos"]:
            chave = f"[{dados['codigo']}] {descricao}"
            self._upsert(
                ProjetoCusto,
                {"projeto": projeto, "descricao": chave},
                {
                    "custo_componentes": Decimal(valor),
                    "horas_tecnicas": Decimal("0"),
                    "valor_hora_tecnica": Decimal("0"),
                    "custo_outros": Decimal("0"),
                    "preco_estimado_venda": None,
                    "payback_esperado": "A definir apos validacao da demanda e dos custos recorrentes.",
                    "viabilidade": "em_analise",
                    "observacoes": "Estimativa conceitual; exige especificacao tecnica e cotacoes formais.",
                },
            )

        for indice, risco in enumerate(dados["riscos"], start=1):
            tipo = f"[{dados['codigo']}] Risco {indice:02d}"
            self._upsert(
                ProjetoTeste,
                {"projeto": projeto, "tipo_teste": tipo},
                {
                    "data_teste": DATA_REFERENCIA,
                    "resultado": "em_analise",
                    "observacao_tecnica": risco,
                    "conclusao_tecnica": "Tratamento, responsavel e evidencia ainda pendentes.",
                },
            )

        for indice, criterio in enumerate(dados["criterios"], start=1):
            tipo = f"[{dados['codigo']}] Criterio de aceitacao {indice:02d}"
            self._upsert(
                ProjetoTeste,
                {"projeto": projeto, "tipo_teste": tipo},
                {
                    "data_teste": DATA_REFERENCIA,
                    "resultado": "em_analise",
                    "observacao_tecnica": criterio,
                    "conclusao_tecnica": "Validacao pendente; nao constitui aprovacao.",
                },
            )

    @staticmethod
    def _upsert(model, lookup, defaults):
        registro = model.objects.filter(**lookup).order_by("created_at").first()
        if registro is None:
            return model.objects.create(**lookup, **defaults)
        for campo, valor in defaults.items():
            setattr(registro, campo, valor)
        registro.save(update_fields=list(defaults.keys()))
        return registro
