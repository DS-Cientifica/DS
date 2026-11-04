import calendar
from collections import defaultdict
from datetime import date, datetime
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from calibracao.models import OrdemServico, Padrao
from comercial.models import CRMRegistro, Proposta
from financeiro.models import ContaPagar, ContaReceber, Imposto, NotaFiscal
from manutencao.models import Manutencao
from planejamento.models import PlanejamentoServico
from projetos.models import Projeto, ProjetoTarefa


MESES = (
    "",
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)

MODULOS = (
    {"valor": "financeiro", "rotulo": "Financeiro", "tom": "financeiro", "permissao": ("financeiro.view_contapagar", "financeiro.view_contareceber", "financeiro.view_imposto", "financeiro.view_notafiscal")},
    {"valor": "comercial", "rotulo": "Comercial", "tom": "comercial", "permissao": ("comercial.view_proposta", "comercial.view_crmregistro")},
    {"valor": "planejamento", "rotulo": "Agenda técnica", "tom": "planejamento", "permissao": "planejamento.view_planejamentoservico"},
    {"valor": "manutencao", "rotulo": "Manutenção", "tom": "manutencao", "permissao": "manutencao.view_manutencao"},
    {"valor": "projetos", "rotulo": "Projetos", "tom": "projetos", "permissao": "projetos.view_projeto"},
    {"valor": "metrologia", "rotulo": "Metrologia", "tom": "metrologia", "permissao": ("calibracao.view_ordemservico", "calibracao.view_padrao")},
)


def _pode(user, permissao):
    if user.is_superuser:
        return True
    if isinstance(permissao, (tuple, list)):
        return any(user.has_perm(item) for item in permissao)
    return user.has_perm(permissao)


def _data_datetime(valor):
    if isinstance(valor, datetime):
        return timezone.localtime(valor).date() if timezone.is_aware(valor) else valor.date()
    return valor


def _adicionar(eventos, data_evento, *, titulo, detalhe, url, modulo, tom, hora=""):
    data_evento = _data_datetime(data_evento)
    if not data_evento:
        return
    eventos[data_evento].append(
        {
            "titulo": titulo,
            "detalhe": detalhe,
            "url": url,
            "modulo": modulo,
            "tom": tom,
            "hora": hora,
        }
    )


def _link_mes(ano, mes, modulo):
    if mes < 1:
        ano, mes = ano - 1, 12
    elif mes > 12:
        ano, mes = ano + 1, 1
    parametros = {"ano": ano, "mes": mes}
    if modulo:
        parametros["modulo"] = modulo
    return f"{reverse('calendario_integrado')}?{urlencode(parametros)}"


@login_required
def calendario_integrado(request):
    hoje = timezone.localdate()
    try:
        ano = int(request.GET.get("ano", hoje.year))
        mes = int(request.GET.get("mes", hoje.month))
        primeiro_dia = date(ano, mes, 1)
    except (TypeError, ValueError):
        ano, mes = hoje.year, hoje.month
        primeiro_dia = date(ano, mes, 1)

    calendario = calendar.Calendar(firstweekday=6)
    semanas_base = calendario.monthdatescalendar(ano, mes)
    inicio_grade = semanas_base[0][0]
    fim_grade = semanas_base[-1][-1]

    modulos_disponiveis = [modulo for modulo in MODULOS if _pode(request.user, modulo["permissao"])]
    valores_disponiveis = {modulo["valor"] for modulo in modulos_disponiveis}
    filtro_modulo = request.GET.get("modulo", "").strip()
    if filtro_modulo not in valores_disponiveis:
        filtro_modulo = ""

    def exibir(modulo):
        return modulo in valores_disponiveis and (not filtro_modulo or filtro_modulo == modulo)

    eventos = defaultdict(list)

    if exibir("financeiro"):
        if _pode(request.user, "financeiro.view_contapagar"):
            for conta in ContaPagar.objects.filter(vencimento__range=(inicio_grade, fim_grade)):
                _adicionar(eventos, conta.vencimento, titulo="Conta a pagar", detalhe=f"{conta.fornecedor} · {conta.descricao}", url=reverse("admin:financeiro_contapagar_change", args=[conta.pk]), modulo="Financeiro", tom="financeiro")
            for conta in ContaPagar.objects.filter(data_pagamento__range=(inicio_grade, fim_grade)):
                _adicionar(eventos, conta.data_pagamento, titulo="Pagamento realizado", detalhe=f"{conta.fornecedor} · {conta.descricao}", url=reverse("admin:financeiro_contapagar_change", args=[conta.pk]), modulo="Financeiro", tom="financeiro")
        if _pode(request.user, "financeiro.view_contareceber"):
            for conta in ContaReceber.objects.filter(vencimento__range=(inicio_grade, fim_grade)).select_related("cliente"):
                _adicionar(eventos, conta.vencimento, titulo="Conta a receber", detalhe=f"{conta.cliente} · {conta.descricao}", url=reverse("admin:financeiro_contareceber_change", args=[conta.pk]), modulo="Financeiro", tom="financeiro")
            for conta in ContaReceber.objects.filter(data_recebimento__range=(inicio_grade, fim_grade)).select_related("cliente"):
                _adicionar(eventos, conta.data_recebimento, titulo="Recebimento realizado", detalhe=f"{conta.cliente} · {conta.descricao}", url=reverse("admin:financeiro_contareceber_change", args=[conta.pk]), modulo="Financeiro", tom="financeiro")
        if _pode(request.user, "financeiro.view_imposto"):
            for imposto in Imposto.objects.filter(vencimento__range=(inicio_grade, fim_grade)):
                _adicionar(eventos, imposto.vencimento, titulo="Vencimento de imposto", detalhe=f"{imposto.nome} · {imposto.competencia}", url=reverse("admin:financeiro_imposto_change", args=[imposto.pk]), modulo="Financeiro", tom="financeiro")
        if _pode(request.user, "financeiro.view_notafiscal"):
            notas = NotaFiscal.objects.filter(Q(data_emissao__range=(inicio_grade, fim_grade)) | Q(data_entrada_saida__range=(inicio_grade, fim_grade)) | Q(data_vencimento__range=(inicio_grade, fim_grade))).select_related("cliente")
            for nota in notas:
                referencia = str(nota.cliente) if nota.cliente_id else (nota.fornecedor_nome or "Sem vínculo")
                url = reverse("admin:financeiro_notafiscal_change", args=[nota.pk])
                _adicionar(eventos, nota.data_emissao, titulo="Emissão de nota fiscal", detalhe=f"NF {nota.numero or 'S/N'} · {referencia}", url=url, modulo="Financeiro", tom="financeiro")
                _adicionar(eventos, nota.data_entrada_saida, titulo="Entrada/saída de nota", detalhe=f"NF {nota.numero or 'S/N'} · {referencia}", url=url, modulo="Financeiro", tom="financeiro")
                _adicionar(eventos, nota.data_vencimento, titulo="Vencimento de nota fiscal", detalhe=f"NF {nota.numero or 'S/N'} · {referencia}", url=url, modulo="Financeiro", tom="financeiro")

    if exibir("comercial"):
        if _pode(request.user, "comercial.view_proposta"):
            propostas = Proposta.objects.filter(Q(data_emissao__range=(inicio_grade, fim_grade)) | Q(validade__range=(inicio_grade, fim_grade))).select_related("cliente")
            for proposta in propostas:
                url = reverse("admin:comercial_proposta_change", args=[proposta.pk])
                _adicionar(eventos, proposta.data_emissao, titulo="Proposta emitida", detalhe=f"{proposta.codigo} · {proposta.cliente}", url=url, modulo="Comercial", tom="comercial")
                _adicionar(eventos, proposta.validade, titulo="Validade da proposta", detalhe=f"{proposta.codigo} · {proposta.cliente}", url=url, modulo="Comercial", tom="comercial")
        if _pode(request.user, "comercial.view_crmregistro"):
            registros = CRMRegistro.objects.filter(Q(data_registro__date__range=(inicio_grade, fim_grade)) | Q(proxima_acao__range=(inicio_grade, fim_grade))).select_related("cliente")
            for registro in registros:
                url = reverse("admin:comercial_crmregistro_change", args=[registro.pk])
                _adicionar(eventos, registro.data_registro, titulo="Registro de CRM", detalhe=f"{registro.titulo} · {registro.cliente}", url=url, modulo="Comercial", tom="comercial")
                _adicionar(eventos, registro.proxima_acao, titulo="Próxima ação comercial", detalhe=f"{registro.titulo} · {registro.cliente}", url=url, modulo="Comercial", tom="comercial")

    if exibir("planejamento") and _pode(request.user, "planejamento.view_planejamentoservico"):
        planejamentos = PlanejamentoServico.objects.filter(data_inicio__lte=fim_grade).filter(Q(data_fim__gte=inicio_grade) | Q(data_fim__isnull=True, data_inicio__gte=inicio_grade)).select_related("cliente")
        for item in planejamentos:
            inicio = max(item.data_inicio, inicio_grade)
            fim = min(item.data_fim or item.data_inicio, fim_grade)
            dia = inicio
            while dia <= fim:
                hora = item.hora_inicio.strftime("%H:%M") if item.hora_inicio and dia == item.data_inicio else ""
                _adicionar(eventos, dia, titulo=item.titulo or item.get_tipo_agendamento_display(), detalhe=f"{item.codigo} · {item.cliente}", url=reverse("admin:planejamento_planejamentoservico_change", args=[item.pk]), modulo="Agenda técnica", tom="planejamento", hora=hora)
                dia = dia.fromordinal(dia.toordinal() + 1)

    if exibir("manutencao") and _pode(request.user, "manutencao.view_manutencao"):
        manutencoes = Manutencao.objects.filter(Q(data_servico__range=(inicio_grade, fim_grade)) | Q(proxima_manutencao__range=(inicio_grade, fim_grade))).select_related("cliente", "instrumento")
        for item in manutencoes:
            url = reverse("admin:manutencao_manutencao_change", args=[item.pk])
            detalhe = f"{item.numero_relatorio} · {item.cliente}"
            _adicionar(eventos, item.data_servico, titulo="Serviço de manutenção", detalhe=detalhe, url=url, modulo="Manutenção", tom="manutencao")
            _adicionar(eventos, item.proxima_manutencao, titulo="Próxima manutenção", detalhe=detalhe, url=url, modulo="Manutenção", tom="manutencao")

    if exibir("projetos"):
        if _pode(request.user, "projetos.view_projeto"):
            projetos = Projeto.objects.filter(Q(data_inicio__range=(inicio_grade, fim_grade)) | Q(previsao_conclusao__range=(inicio_grade, fim_grade)))
            for projeto in projetos:
                url = reverse("admin:projetos_projeto_change", args=[projeto.pk])
                _adicionar(eventos, projeto.data_inicio, titulo="Início de projeto", detalhe=f"{projeto.codigo} · {projeto.nome}", url=url, modulo="Projetos", tom="projetos")
                _adicionar(eventos, projeto.previsao_conclusao, titulo="Previsão de conclusão", detalhe=f"{projeto.codigo} · {projeto.nome}", url=url, modulo="Projetos", tom="projetos")
        if _pode(request.user, "projetos.view_projetotarefa"):
            for tarefa in ProjetoTarefa.objects.filter(prazo__range=(inicio_grade, fim_grade)).select_related("projeto"):
                _adicionar(eventos, tarefa.prazo, titulo="Prazo de tarefa", detalhe=f"{tarefa.projeto.codigo} · {tarefa.titulo}", url=reverse("admin:projetos_projetotarefa_change", args=[tarefa.pk]), modulo="Projetos", tom="projetos")

    if exibir("metrologia"):
        if _pode(request.user, "calibracao.view_ordemservico"):
            ordens = OrdemServico.objects.filter(Q(data_abertura__range=(inicio_grade, fim_grade)) | Q(data_conclusao__range=(inicio_grade, fim_grade))).select_related("cliente")
            for ordem in ordens:
                url = reverse("admin:calibracao_ordemservico_change", args=[ordem.pk])
                _adicionar(eventos, ordem.data_abertura, titulo="Abertura de ordem de serviço", detalhe=f"OS {ordem.numero} · {ordem.cliente}", url=url, modulo="Metrologia", tom="metrologia")
                _adicionar(eventos, ordem.data_conclusao, titulo="Conclusão de ordem de serviço", detalhe=f"OS {ordem.numero} · {ordem.cliente}", url=url, modulo="Metrologia", tom="metrologia")
        if _pode(request.user, "calibracao.view_padrao"):
            for padrao in Padrao.para_monitoramento().filter(
                vencimento__range=(inicio_grade, fim_grade)
            ):
                _adicionar(eventos, padrao.vencimento, titulo="Vencimento de padrão", detalhe=str(padrao), url=reverse("admin:calibracao_padrao_change", args=[padrao.pk]), modulo="Metrologia", tom="metrologia")

    semanas = []
    for semana in semanas_base:
        dias = []
        for dia in semana:
            eventos_dia = sorted(eventos.get(dia, []), key=lambda evento: (evento["hora"] or "99:99", evento["titulo"]))
            dias.append({"data": dia, "fora_mes": dia.month != mes, "hoje": dia == hoje, "eventos": eventos_dia})
        semanas.append(dias)

    modulos_com_filtro = [
        {
            **modulo,
            "ativo": filtro_modulo == modulo["valor"],
            "url_filtro": _link_mes(
                ano,
                mes,
                "" if filtro_modulo == modulo["valor"] else modulo["valor"],
            ),
        }
        for modulo in modulos_disponiveis
    ]

    context = {
        "ano": ano,
        "mes": mes,
        "mes_nome": MESES[mes],
        "semanas": semanas,
        "modulos": modulos_com_filtro,
        "filtro_modulo": filtro_modulo,
        "link_todos": _link_mes(ano, mes, ""),
        "link_anterior": _link_mes(ano, mes - 1, filtro_modulo),
        "link_proximo": _link_mes(ano, mes + 1, filtro_modulo),
        "link_hoje": _link_mes(hoje.year, hoje.month, filtro_modulo),
        "total_eventos": sum(len(itens) for dia, itens in eventos.items() if dia.month == mes and dia.year == ano),
    }
    return render(request, "calendario_integrado.html", context)
