from django.contrib.admin.models import DELETION, LogEntry
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from calibracao.models import Instrumento, Padrao
from financeiro.models import ContaPagar, ContaReceber
from qualidade.models import Documento


def _pode_acessar(user, permissao):
    return user.is_superuser or user.has_perm(permissao)


def _item(rotulo, url_name, permissao, *, query="", destaque=False):
    url = reverse(url_name)
    if query:
        url = f"{url}?{query}"
    return {
        "rotulo": rotulo,
        "url": url,
        "permissao": permissao,
        "destaque": destaque,
    }


def _montar_modulos(user):
    permissoes_calibracao = (
        "calibracao.view_calibracao",
        "calibracao.view_calibracaoph",
        "calibracao.view_calibracaoturbidez",
        "calibracao.view_calibracaocolorimetro",
        "calibracao.view_calibracaocondutividade",
        "calibracao.view_calibracaopressao",
        "calibracao.view_calibracaobalanca",
        "calibracao.view_calibracaodispositivosegurancapressao",
        "calibracao.view_calibracaoesfigmomanometro",
    )
    modulos = [
        {
            "titulo": "Comercial",
            "app_label": "comercial",
            "descricao": "Clientes, propostas, produtos e relacionamento comercial.",
            "icone": "commercial",
            "tom": "green",
            "itens": [
                _item("Clientes", "admin:clientes_cliente_changelist", "clientes.view_cliente"),
                _item("Contatos de clientes", "admin:clientes_contatocliente_changelist", "clientes.view_contatocliente"),
                _item("Produtos e serviços", "admin:comercial_produtoservico_changelist", "comercial.view_produtoservico"),
                _item("Propostas", "admin:comercial_proposta_changelist", "comercial.view_proposta"),
                _item("Prospecções comerciais", "admin:comercial_prospeccaocomercial_changelist", "comercial.view_prospeccaocomercial"),
                _item("Registros de CRM", "admin:comercial_crmregistro_changelist", "comercial.view_crmregistro"),
                _item("Tickets de CRM", "admin:comercial_crmticket_changelist", "comercial.view_crmticket"),
            ],
        },
        {
            "titulo": "Financeiro",
            "app_label": "financeiro",
            "descricao": "Contas, tributos, documentos fiscais e compras.",
            "icone": "finance",
            "tom": "red",
            "itens": [
                _item("Categorias financeiras", "admin:financeiro_categoriafinanceira_changelist", "financeiro.view_categoriafinanceira"),
                _item("Contas a pagar", "admin:financeiro_contapagar_changelist", "financeiro.view_contapagar"),
                _item("Contas a receber", "admin:financeiro_contareceber_changelist", "financeiro.view_contareceber"),
                _item("Impostos", "admin:financeiro_imposto_changelist", "financeiro.view_imposto"),
                _item("Notas fiscais", "admin:financeiro_notafiscal_changelist", "financeiro.view_notafiscal"),
                _item("Pedidos de compra", "admin:financeiro_pedidocompra_changelist", "financeiro.view_pedidocompra"),
            ],
        },
        {
            "titulo": "Gestão",
            "app_label": "gestao",
            "descricao": "Documentos corporativos, pessoas e competências.",
            "icone": "chart",
            "tom": "amber",
            "itens": [
                _item("Gestão — Documentos da empresa", "admin:gestao_documentoempresa_changelist", "gestao.view_documentoempresa"),
                _item("RH — Colaboradores", "admin:gestao_colaborador_changelist", "gestao.view_colaborador"),
                _item("RH — Treinamentos", "admin:gestao_treinamento_changelist", "gestao.view_treinamento"),
            ],
        },
        {
            "titulo": "Gestão Metrológica",
            "app_label": "calibracao",
            "descricao": "Instrumentos, rastreabilidade, calibrações e manutenção.",
            "icone": "quality",
            "tom": "teal",
            "itens": [
                _item("Instrumentos", "admin:calibracao_instrumento_changelist", "calibracao.view_instrumento"),
                _item("Ordens de serviço", "admin:calibracao_ordemservico_changelist", "calibracao.view_ordemservico"),
                _item("Padrões", "admin:calibracao_padrao_changelist", "calibracao.view_padrao"),
                _item(
                    "Diluição e preparação de padrões",
                    "admin:calibracao_preparacaopadrao_changelist",
                    "calibracao.view_preparacaopadrao",
                ),
                _item("Calibrações", "admin:calibracoes_index", permissoes_calibracao, destaque=True),
                _item("Documentos", "admin:qualidade_documento_changelist", "qualidade.view_documento"),
                _item("Manutenções", "admin:manutencao_manutencao_changelist", "manutencao.view_manutencao"),
            ],
        },
        {
            "titulo": "Planejamento e Logística",
            "app_label": "planejamento",
            "descricao": "Programação técnica e movimentação logística.",
            "icone": "calendar",
            "tom": "blue",
            "itens": [
                _item("Agendas técnicas", "admin:planejamento_planejamentoservico_changelist", "planejamento.view_planejamentoservico"),
                _item("Formulários logísticos sem NF", "admin:planejamento_envioequipamentosemnota_changelist", "planejamento.view_envioequipamentosemnota"),
            ],
        },
        {
            "titulo": "Projetos e Desenvolvimento",
            "app_label": "projetos",
            "descricao": "Desenvolvimento técnico e ações de marketing.",
            "icone": "folder",
            "tom": "purple",
            "itens": [
                _item("Desenvolvimento Técnico — Projetos", "admin:projetos_projeto_changelist", "projetos.view_projeto"),
                _item("Marketing — Campanhas", "admin:projetos_campanhamarketing_changelist", "projetos.view_campanhamarketing"),
            ],
        },
    ]

    for modulo in modulos:
        itens_visiveis = []
        for item in modulo["itens"]:
            permissoes = item["permissao"]
            if isinstance(permissoes, str):
                permissoes = (permissoes,)
            if any(_pode_acessar(user, permissao) for permissao in permissoes):
                itens_visiveis.append(item)
        modulo["itens"] = itens_visiveis
        if itens_visiveis:
            modulo["url"] = reverse(
                "admin:app_list",
                kwargs={"app_label": modulo["app_label"]},
            )

    modulos = [modulo for modulo in modulos if modulo["itens"]]
    return [{"titulo": "", "subtitulo": "", "tom": "", "modulos": modulos}] if modulos else []


def _montar_alertas(user):
    hoje = timezone.localdate()
    alertas = []

    if _pode_acessar(user, "calibracao.view_instrumento"):
        total = Instrumento.objects.filter(ativo=True, proxima_calibracao__lt=hoje).count()
        if total:
            alertas.append({"rotulo": "Calibrações vencidas", "total": total, "url": reverse("admin:calibracao_instrumento_changelist")})

    if _pode_acessar(user, "calibracao.view_padrao"):
        total = Padrao.objects.filter(vencimento__lt=hoje).count()
        if total:
            alertas.append({"rotulo": "Padrões vencidos", "total": total, "url": reverse("admin:calibracao_padrao_changelist")})

    if _pode_acessar(user, "qualidade.view_documento"):
        total = sum(1 for documento in Documento.objects.filter(status="vigente") if documento.data_proxima_revisao < hoje)
        if total:
            alertas.append({"rotulo": "Documentos vencidos", "total": total, "url": reverse("admin:qualidade_documento_changelist")})

    if _pode_acessar(user, "financeiro.view_contareceber"):
        total = ContaReceber.objects.filter(status__in=("pendente", "atrasado"), vencimento__lt=hoje).count()
        if total:
            alertas.append({"rotulo": "Recebimentos atrasados", "total": total, "url": reverse("admin:financeiro_contareceber_changelist")})

    if _pode_acessar(user, "financeiro.view_contapagar"):
        total = ContaPagar.objects.filter(status__in=("pendente", "atrasado"), vencimento__lt=hoje).count()
        if total:
            alertas.append({"rotulo": "Pagamentos atrasados", "total": total, "url": reverse("admin:financeiro_contapagar_changelist")})

    return alertas


def _atividades_recentes(user, limite=5):
    atividades = []
    entradas = (
        LogEntry.objects.filter(user=user)
        .exclude(action_flag=DELETION)
        .select_related("content_type")
        .order_by("-action_time")[:30]
    )

    for entrada in entradas:
        model_class = entrada.content_type.model_class()
        if model_class is None:
            continue
        permissao = f"{entrada.content_type.app_label}.view_{entrada.content_type.model}"
        if not _pode_acessar(user, permissao):
            continue
        try:
            url = entrada.get_admin_url()
        except Exception:
            continue
        atividades.append(
            {
                "rotulo": entrada.object_repr,
                "tipo": str(entrada.content_type.name).capitalize(),
                "url": url,
                "quando": entrada.action_time,
            }
        )
        if len(atividades) == limite:
            break

    return atividades


@login_required(login_url="/admin/login/")
def inicio(request):
    grupos = _montar_modulos(request.user)
    alertas = _montar_alertas(request.user)
    nome = request.user.get_short_name() or request.user.get_username()

    return render(
        request,
        "home.html",
        {
            "nome_usuario": nome,
            "inicial_usuario": nome[:1].upper(),
            "grupos": grupos,
            "alertas": alertas,
            "total_alertas": sum(alerta["total"] for alerta in alertas),
            "atividades_recentes": _atividades_recentes(request.user),
        },
    )
