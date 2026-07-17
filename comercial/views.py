from decimal import Decimal
import re
import unicodedata
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.http import FileResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .models import Proposta
from .pdf import gerar_pdf_proposta


EMPRESA_PROPOSTA = {
    "nome": "DS Científica",
    "site": "www.dscientifica.com.br",
    "telefone": "(11) 98859-9577",
    "cnpj": "63.669.660/0001-80",
    "cidade": "Jundiaí-SP",
    "endereço": "Avenida Reynlado de Porcari, 2788 - Jardim Tereza Cristina",
    "email": "contato@dscientifica.com.br"
   
}

CONDICOES_GERAIS_PROPOSTA = """A aprovação desta proposta implica na aceitação integral das condições comerciais, técnicas e operacionais aqui descritas. Eventuais alterações de escopo, inclusão de serviços adicionais, alteração de pontos de calibração, faixas de trabalho ou requisitos específicos poderão ser objeto de nova análise técnica e comercial, mediante prévia concordância entre as partes.

Em caso de dúvidas quanto à interpretação deste documento, solicitamos que entrem em contato com a DS Científica antes da aprovação da proposta, para os devidos esclarecimentos.

1. PRAZO DE EXECUÇÃO
O prazo para execução dos serviços é de até 7 (sete) dias úteis, contados a partir do recebimento dos equipamentos nas dependências da DS Científica ou da realização dos serviços em campo, conforme aplicável.

Os certificados de calibração, relatórios técnicos ou relatórios de ensaio serão emitidos em até 7 (sete) dias úteis após a conclusão dos serviços, salvo em casos que demandem avaliações complementares, análise técnica adicional, necessidade de aprovação do cliente ou acordos específicos previamente estabelecidos.

A reprogramação de serviços em campo estará sujeita à disponibilidade da agenda técnica da DS Científica, não sendo garantido o reagendamento automático para o dia útil seguinte.

2. CONDIÇÕES COMERCIAIS E DESPESAS
Todos os valores apresentados nesta proposta estão expressos em Reais (R$).

Os preços informados não incluem frete, taxa de deslocamento técnico, hospedagem, alimentação, pedágios, estacionamento ou quaisquer outras despesas de viagem, salvo quando expressamente indicado na proposta comercial.

Quando aplicáveis, as despesas de viagem e deslocamento deverão ser previamente aprovadas pela CONTRATANTE e serão cobradas separadamente, conforme condições estabelecidas na proposta.

Para que a condição de pagamento seja considerada parcelada, o orçamento deverá ser faturado em sua totalidade.

Para empresas que exigem a inclusão de Nota Fiscal em portal ou sistema interno, os certificados de calibração, relatórios ou documentos técnicos somente serão liberados após o aceite da Nota Fiscal no respectivo sistema.

Caso o serviço não possa ser concluído no prazo contratado por motivos não imputáveis à DS Científica, poderão ser cobradas as despesas operacionais adicionais necessárias até a conclusão do serviço, incluindo, quando aplicável, diária técnica, deslocamento, hospedagem e alimentação.

3. TRANSPORTE, FRETE E RESPONSABILIDADES
O transporte dos equipamentos não é de responsabilidade da DS Científica, salvo quando expressamente acordado entre as partes.

A DS Científica não se responsabiliza por danos, avarias, furtos, roubos, extravios ou perdas ocorridas durante o transporte realizado por transportadoras, Correios, motoboys, aplicativos de entrega ou quaisquer outros agentes logísticos contratados.

Eventuais ressarcimentos referentes a furtos, roubos, perdas ou danos durante o transporte somente serão repassados ao cliente após o efetivo ressarcimento realizado pelo agente de transporte à DS Científica, quando aplicável.

O horário para recebimento e retirada de materiais é:
Segunda a sexta-feira: 08h30 às 12h00 / 13h00 às 16h30

4. DADOS PARA FATURAMENTO
Razão Social: DS Científica
CNPJ: 63.669.660/0001-80
Inscrição Estadual: 159.489.708.114
Endereço: Avenida Reynaldo de Porcari, nº 2788 - Jardim Tereza Cristina - Jundiaí/SP
CEP: 13212-439

5. REQUISITOS PARA CONTRATAÇÃO DOS SERVIÇOS
O pedido de compra deverá especificar claramente os pontos a serem calibrados, a faixa de utilização dos equipamentos, os critérios de aceitação, tolerâncias aplicáveis e demais requisitos técnicos necessários à execução dos serviços.

Caso não sejam informados os pontos de calibração ou a faixa de uso do equipamento, a DS Científica poderá definir os pontos conforme seu procedimento interno, capacidade técnica disponível e aplicação usual do instrumento.

Poderão ocorrer pequenas variações nos pontos de calibração solicitados, em função de limitações técnicas, disponibilidade de padrões, faixa operacional do equipamento ou método utilizado.

Qualquer divergência entre o material orçado e o material recebido será submetida à avaliação técnica, podendo resultar em revisão de escopo, prazo e valores.

Para que o serviço seja executado adequadamente, todos os componentes necessários ao funcionamento do equipamento deverão ser enviados juntamente com o instrumento, incluindo, quando aplicável: fonte de alimentação, cabos, sensores, ponteiras, display, software, carta gráfica, acessórios, manuais, adaptadores e demais itens necessários à operação.

A DS Científica não executa descontaminação de equipamentos enviados para calibração, manutenção ou avaliação técnica. A responsabilidade pela limpeza, descontaminação e envio seguro do equipamento é exclusivamente do cliente.

6. CERTIFICADOS, RELATÓRIOS E DADOS DO CLIENTE
Nos campos "Contratante" e "Interessado" dos certificados de calibração, relatórios de ensaio ou relatórios técnicos constará a razão social das empresas envolvidas.

Caso seja necessário incluir nome fantasia ou informação específica nos documentos emitidos, essa solicitação deverá ser formalizada no momento da contratação, preferencialmente no pedido de compra.

Caso haja divergência técnica nos serviços executados, não será aceita a devolução da Nota Fiscal referente ao serviço prestado. Nesses casos, a situação será avaliada pelo departamento técnico da DS Científica, podendo ser realizada renegociação, reanálise ou emissão de relatório complementar, conforme aplicável.

7. CALIBRAÇÕES NÃO ACREDITADAS
Os serviços de calibração executados diretamente pela DS Científica são não acreditados pela CGCRE/Inmetro.

Entretanto, as calibrações são realizadas com rastreabilidade metrológica a padrões nacionais e/ou internacionais, assegurando a confiabilidade dos resultados e a rastreabilidade das medições, conforme os métodos e procedimentos aplicáveis.

A calibração não compreende garantia de aprovação do instrumento, ajuste obrigatório, manutenção corretiva ou adequação do equipamento ao critério de aceitação do cliente, salvo quando expressamente contratado.

Quando forem aplicados critérios de aceitação, tolerâncias ou especificações de trabalho, o resultado será apresentado no certificado ou relatório técnico, conforme aplicável.

8. CALIBRAÇÕES ACREDITADAS
Quando houver necessidade de calibração acreditada pela CGCRE/Inmetro ou calibração em pontos específicos não contemplados no escopo padrão da DS Científica, os serviços poderão ser realizados por meio de laboratório parceiro acreditado.

Nesses casos, os requisitos técnicos deverão ser informados previamente à contratação e estarão sujeitos à análise técnica, disponibilidade do laboratório parceiro, prazo específico e revisão comercial.

9. REQUISITOS GERAIS PARA CALIBRAÇÃO
Conforme o VIM - Vocabulário Internacional de Metrologia, item 2.39, calibração é a operação que estabelece, sob condições especificadas, uma relação entre os valores e as incertezas de medição fornecidos por padrões e as indicações correspondentes do instrumento, utilizando esta informação para obtenção de resultados de medição a partir de uma indicação.

As calibrações realizadas pela DS Científica são executadas por método comparativo, utilizando padrões rastreáveis e procedimentos técnicos aplicáveis à grandeza avaliada.

A calibração não garante a aprovação do instrumento, pois o resultado depende das condições metrológicas do equipamento, do critério de aceitação definido pelo cliente e da aplicação pretendida.

Caso o equipamento seja submetido à calibração e apresente resultado fora do critério de aceitação, o serviço será considerado executado e cobrado conforme proposta aprovada.

Caso não seja possível realizar a calibração por motivos relacionados ao cliente, ao equipamento ou à indisponibilidade das condições mínimas necessárias, poderá ser cobrado o percentual de 35% do valor da calibração, conforme proposta, além das despesas de deslocamento e viagem, quando aplicáveis.

Exemplos de impossibilidade de execução por motivos não imputáveis à DS Científica incluem: equipamento indisponível, equipamento quebrado, equipamento em manutenção, ausência de acessórios necessários, falta de alimentação elétrica, impossibilidade de acesso ao local, ausência de responsável técnico do cliente ou condições inadequadas de instalação.

10. CALIBRAÇÃO EXTERNA - SERVIÇOS EM CAMPO
Para execução dos serviços de calibração em campo, a CONTRATANTE deverá garantir as seguintes condições:
- Disponibilidade de um técnico de manutenção ou responsável técnico durante o período de calibração;
- Disponibilidade dos equipamentos na data e horário previamente programados;
- Informação prévia dos locais onde os equipamentos estão instalados;
- Disponibilização de rede de alimentação elétrica 110/220 V, com tomada em padrão adequado, em um raio máximo de 5 metros do equipamento a ser calibrado;
- Condições adequadas de acesso, segurança e operação para execução dos serviços;
- Disponibilização dos manuais técnicos, procedimentos internos ou pessoa capacitada quando houver necessidade de ajuste, configuração ou acesso a parâmetros do equipamento;
- Informação prévia dos critérios de aceitação, tolerâncias ou limites operacionais aplicáveis;
- Possibilidade de remoção dos sensores, termopares, termorresistências, cabos de extensão ou compensação do local de instalação, quando necessário para a execução da calibração.

Os técnicos da DS Científica não estão autorizados a desmontar ou montar máquinas, painéis, sistemas produtivos ou instalações elétricas para execução da calibração, salvo quando essa atividade estiver expressamente prevista e contratada no escopo do serviço.

Caso seja exigida integração, liberação de acesso, envio de documentos, treinamentos ou cadastros prévios para entrada nas instalações da CONTRATANTE, tais requisitos deverão ser informados e solicitados com antecedência mínima de 48 horas.

11. IMPOSSIBILIDADE DE EXECUÇÃO EM CAMPO
Caso não seja possível realizar a calibração em campo por motivos não imputáveis à DS Científica, serão cobrados:
- Despesas de viagem, quando aplicáveis;
- Taxa de deslocamento, conforme proposta.

12. OBSERVAÇÕES FINAIS
A DS Científica se reserva o direito de revisar prazos, valores e condições técnicas caso sejam identificadas divergências entre as informações fornecidas na solicitação de orçamento e as condições reais encontradas no equipamento, processo ou local de execução.

Qualquer dúvida na compreensão deste documento deverá ser esclarecida antes da aprovação da proposta."""


def _formatar_moeda(valor):
    valor = Decimal(valor or 0)
    texto = f"{valor:,.2f}"
    return f"R$ {texto}".replace(",", "X").replace(".", ",").replace("X", ".")


def _endereco_cliente(cliente):
    partes = [
        cliente.endereco,
        cliente.numero,
        cliente.bairro,
        cliente.cidade,
        cliente.uf,
        cliente.cep,
    ]
    return " - ".join(str(parte).strip() for parte in partes if parte)


def _contato_principal(proposta):
    if proposta.responsavel_id:
        return proposta.responsavel

    return (
        proposta.cliente.contatos.filter(principal=True).first()
        or proposta.cliente.contatos.first()
    )


def _is_image_file(nome_arquivo):
    extensoes = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg")
    return str(nome_arquivo or "").lower().endswith(extensoes)


def _sanitizar_nome_arquivo(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r'[\\/:*?"<>|]+', " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _nome_arquivo_proposta(proposta):
    nome_cliente = (
        getattr(proposta.cliente, "nome_empresa", "")
        or getattr(proposta.cliente, "razao_social", "")
        or "CLIENTE"
    )
    nome_cliente = _sanitizar_nome_arquivo(nome_cliente).upper()
    codigo = _sanitizar_nome_arquivo(str(proposta.codigo or "").replace("/", "_"))
    return f"{nome_cliente} - {codigo}.pdf"


def _queryset_proposta_pdf():
    return Proposta.objects.select_related("cliente", "responsavel").prefetch_related(
        "itens__produto",
        "cliente__contatos",
        "anexos",
        "movimentacoes__usuario",
    )


def _destinatario_email_proposta(proposta):
    contato = _contato_principal(proposta)
    if contato and getattr(contato, "email", ""):
        return contato.email
    return getattr(proposta.cliente, "email", "") or ""


def _contexto_proposta_pdf(request, proposta):
    itens = []
    resumo = proposta.resumo_financeiro()

    for numero, item in enumerate(proposta.itens.all(), start=1):
        itens.append(
            {
                "numero": numero,
                "obj": item,
                "valor_unitario": _formatar_moeda(item.valor_unitario_com_margem()),
                "valor_total": _formatar_moeda(item.valor_total_com_margem()),
            }
        )

    imagens_pdf = []
    for anexo in proposta.anexos.all():
        if not anexo.exibir_no_pdf:
            continue
        if anexo.tipo != "imagem" and not _is_image_file(getattr(anexo.arquivo, "name", "")):
            continue
        if not getattr(anexo, "arquivo", None):
            continue
        imagens_pdf.append(
            {
                "nome": anexo.nome,
                "legenda": anexo.legenda,
                "url": anexo.arquivo.url,
            }
        )

    historico_itens = list(
        proposta.movimentacoes.filter(
            tipo="alteracao",
            descricao__startswith="Item ",
        ).select_related("usuario").order_by("data")
    )

    secao_historico_numero = None
    secao_despesas_numero = 5
    if historico_itens:
        secao_historico_numero = 5
        secao_despesas_numero = 6

    secao_observacoes_numero = secao_despesas_numero + 1
    proxima_secao = secao_observacoes_numero + 1
    secao_imagens_numero = None
    if imagens_pdf:
        secao_imagens_numero = proxima_secao
        proxima_secao += 1

    secao_tecnica_numero = None
    if proposta.metodo or proposta.padroes_utilizados:
        secao_tecnica_numero = proxima_secao

    contato = _contato_principal(proposta)
    url_pdf = request.build_absolute_uri()
    assunto_email = f"Proposta comercial {proposta.codigo} - DS Cientifica"
    mensagem_compartilhamento = (
        f"Segue a proposta comercial {proposta.codigo} da DS Cientifica.\n\n"
        f"Acesse o PDF pelo link: {url_pdf}"
    )
    email_destinatario = _destinatario_email_proposta(proposta)
    mailto_url = (
        f"mailto:{email_destinatario}"
        f"?subject={quote(assunto_email)}"
        f"&body={quote(mensagem_compartilhamento)}"
    )
    whatsapp_url = f"https://wa.me/?text={quote(mensagem_compartilhamento)}"
    pdf_filename = _nome_arquivo_proposta(proposta)

    return {
        "empresa": EMPRESA_PROPOSTA,
        "proposta": proposta,
        "pdf_filename": pdf_filename,
        "cliente": proposta.cliente,
        "contato": contato,
        "endereco_cliente": _endereco_cliente(proposta.cliente),
        "itens": itens,
        "historico_itens": historico_itens,
        "secao_historico_numero": secao_historico_numero,
        "secao_despesas_numero": secao_despesas_numero,
        "secao_observacoes_numero": secao_observacoes_numero,
        "subtotal": _formatar_moeda(resumo["subtotal"]),
        "desconto_itens": _formatar_moeda(resumo["desconto_itens"]),
        "desconto_geral": _formatar_moeda(resumo["desconto_geral"]),
        "frete_valor": _formatar_moeda(resumo["frete_valor"]),
        "outras_despesas": _formatar_moeda(resumo["outras_despesas"]),
        "seguro_valor": _formatar_moeda(resumo["seguro_valor"]),
        "total": _formatar_moeda(proposta.total),
        "local_execucao": proposta.get_local_execucao_display(),
        "frete": proposta.get_frete_display(),
        "status": proposta.get_status_display(),
        "imagens_pdf": imagens_pdf,
        "secao_imagens_numero": secao_imagens_numero,
        "secao_tecnica_numero": secao_tecnica_numero,
        "condicoes_gerais_proposta": CONDICOES_GERAIS_PROPOSTA,
        "mailto_url": mailto_url,
        "whatsapp_url": whatsapp_url,
        "email_destinatario": email_destinatario,
        "download_pdf_url": reverse("download_pdf_proposta", args=[proposta.pk]),
        "send_email_url": reverse("enviar_proposta_email", args=[proposta.pk]),
    }

@login_required
def pdf_proposta(request, pk):
    proposta = get_object_or_404(_queryset_proposta_pdf(), pk=pk)
    contexto = _contexto_proposta_pdf(request, proposta)
    return render(
        request,
        "comercial/proposta_pdf.html",
        contexto,
    )


@login_required
def download_pdf_proposta(request, pk):
    proposta = get_object_or_404(_queryset_proposta_pdf(), pk=pk)
    contexto = _contexto_proposta_pdf(request, proposta)
    buffer = gerar_pdf_proposta(proposta, EMPRESA_PROPOSTA, contexto)
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=contexto["pdf_filename"],
    )


@login_required
def enviar_proposta_email(request, pk):
    proposta = get_object_or_404(_queryset_proposta_pdf(), pk=pk)
    if request.method != "POST":
        return HttpResponseRedirect(reverse("pdf_proposta", args=[proposta.pk]))

    destinatario = _destinatario_email_proposta(proposta)
    if not destinatario:
        messages.error(request, "A proposta não possui e-mail de destinatário configurado no contato ou no cliente.")
        return HttpResponseRedirect(reverse("pdf_proposta", args=[proposta.pk]))

    if not settings.EMAIL_HOST or not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        messages.error(request, "As configurações de e-mail do sistema não estão completas.")
        return HttpResponseRedirect(reverse("pdf_proposta", args=[proposta.pk]))

    contexto = _contexto_proposta_pdf(request, proposta)
    buffer = gerar_pdf_proposta(proposta, EMPRESA_PROPOSTA, contexto)
    pdf_bytes = buffer.getvalue()

    assunto = f"Proposta comercial {proposta.codigo} - DS Cientifica"
    corpo = (
        f"Prezados,\n\n"
        f"Segue em anexo a proposta comercial {proposta.codigo}.\n\n"
        f"Atenciosamente,\n"
        f"{EMPRESA_PROPOSTA['nome']}\n"
        f"{EMPRESA_PROPOSTA['telefone']} | {EMPRESA_PROPOSTA['email']}"
    )
    email = EmailMessage(
        subject=assunto,
        body=corpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destinatario],
    )
    email.attach(contexto["pdf_filename"], pdf_bytes, "application/pdf")

    try:
        email.send(fail_silently=False)
    except Exception as exc:
        messages.error(request, f"Falha ao enviar a proposta por e-mail: {exc}")
    else:
        messages.success(request, f"Proposta enviada com sucesso para {destinatario}.")

    return HttpResponseRedirect(reverse("pdf_proposta", args=[proposta.pk]))
