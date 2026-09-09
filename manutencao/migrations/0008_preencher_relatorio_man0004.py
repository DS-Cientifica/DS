from datetime import date

from django.db import migrations


NOVOS_DADOS = {
    "tipo_manutencao": "diagnostico",
    "data_saida": None,
    "condicao_recebida": (
        "Sistema de medição de vazão por pressão diferencial, composto por transmissor "
        "Aplisens APR-2000ALW, série 07261168, Device ID HART 7261168, manifold, linhas "
        "de impulso, saída 4-20 mA + HART para CLP e indicação na IHM. Sensor diferencial "
        "com faixa nominal indicada de -0,5 a +0,5 bar, alimentação de 11,5-30 Vcc, "
        "grau de proteção IP66 e partes molhadas em 316L. Elemento primário: placa de "
        "orifício existente. Dados identificados na plaqueta: Q.M. aproximadamente "
        "400 m³/h; D.T. aproximadamente 305 mm; D.F. aproximadamente 176,60 mm; "
        "ΔP de 2500 mmH₂O. Na leitura inicial via HART foi encontrado URV próximo de "
        "5111,65 mmH₂O, diferente do ΔP indicado na placa de orifício. A operação informou "
        "vazão normalmente observada de aproximadamente 180-190 m³/h."
    ),
    "condicao_saida": (
        "Transmissor comunicado e parametrizado com LRV = 0 mmH₂O, URV = 2500 mmH₂O, "
        "damping = 2,0 s, função Square Root, Start Point Rad observado de 0,8% e saída "
        "4-20 mA. Display configurado para escala de usuário de 0 a 400 m³/h, com LCD 2 "
        "em User Range. Com ΔP próximo de 1250 mmH₂O, a indicação ficou em aproximadamente "
        "280-284 m³/h. A configuração e o diagnóstico foram executados, porém a validação "
        "metrológica e funcional final permanece pendente."
    ),
    "diagnostico": (
        "A parametrização anterior apresentava valores de faixa diferentes dos dados da "
        "placa de orifício. Após configurar 0-2500 mmH₂O com extração de raiz quadrada, "
        "a indicação de aproximadamente 280-284 m³/h para ΔP próximo de 1250 mmH₂O é "
        "matematicamente coerente. Pela relação Q = 400 × √(ΔP/2500), o resultado esperado "
        "é aproximadamente 283 m³/h. Entretanto, esse valor diverge da referência operacional "
        "de 180-190 m³/h. Para 180 m³/h, o diferencial esperado seria aproximadamente "
        "506 mmH₂O. Deve ser investigada a razão de o transmissor indicar ΔP próximo de "
        "1250 mmH₂O. No trecho de lógica analisado no TIA Portal foi observado escalonamento "
        "linear de 0-400 m³/h, sem bloco de raiz quadrada no trecho apresentado; a lógica "
        "completa do CLP ainda precisa ser confirmada. A extração de raiz quadrada deve ocorrer "
        "uma única vez, no transmissor ou no sistema de controle."
    ),
    "parecer_tecnico": (
        "Conclusão provisória: a comunicação HART, a parametrização da faixa e o diagnóstico "
        "foram realizados conforme os dados disponíveis da placa de orifício. A indicação "
        "obtida é coerente com a função Square Root ativa, mas diverge da referência operacional. "
        "O serviço não deve ser encerrado como medição normalizada até a confirmação do memorial "
        "de cálculo da placa, da leitura física do diferencial, das linhas de impulso/manifold "
        "e da lógica completa do CLP. Status: validação metrológica e funcional final pendente."
    ),
    "criterio_aceitacao": (
        "Não foi informada tolerância quantitativa de aceitação. Antes do fechamento, confirmar "
        "a correspondência entre Q.M. = 400 m³/h e ΔP = 2500 mmH₂O nas condições reais do "
        "processo, garantir que a extração de raiz quadrada ocorra somente uma vez e verificar "
        "a resposta nos pontos recomendados. A aprovação final depende dessas confirmações."
    ),
    "status": "pendente_validacao",
    "observacoes": (
        "Pendências: confirmar a lógica completa do CLP; obter e analisar o memorial de cálculo/"
        "datasheet da placa de orifício; comparar simultaneamente equipamento de referência, "
        "transmissor, corrente de saída e CLP; verificar o zero com câmaras H e L equalizadas "
        "conforme procedimento seguro; inspecionar linhas de impulso quanto a obstruções, "
        "condensado e bolsas de gás ou líquido; confirmar posição do manifold e conexão das "
        "tomadas de alta e baixa pressão; aplicar ΔP conhecido, se necessário."
    ),
    "proxima_manutencao": None,
    "intervencoes": (
        "Realizada comunicação HART com Commubox Endress+Hauser FXA195, utilizando FieldCare "
        "e Aplisens Raport 2. Conferidos identificação, proteção de escrita, limites do sensor, "
        "saída analógica, variável de processo, parâmetros de faixa e display. Parametrizados: "
        "unidade mmH₂O; LRV 0 mmH₂O; URV 2500 mmH₂O; damping 2,0 s; função Square Root; "
        "Start Point Rad observado 0,8%; saída 4-20 mA. Configurado display local: User Lower "
        "Range 0; User Upper Range 400; unidade m³/h em formato compatível; LCD 2 = User Range."
    ),
    "materiais": (
        "Interface de comunicação Commubox Endress+Hauser FXA195 e softwares FieldCare e "
        "Aplisens Raport 2. Não foram informadas peças substituídas ou consumíveis utilizados."
    ),
    "verificacoes": (
        "Executadas verificações de identificação, comunicação HART, proteção de escrita, "
        "limites do sensor, saída analógica, variável de processo, faixa e display. Após a "
        "configuração, foi observada indicação de aproximadamente 280-284 m³/h para ΔP próximo "
        "de 1250 mmH₂O. Teste recomendado ainda pendente para 0-2500 mmH₂O / 0-400 m³/h: "
        "0 mmH₂O → 0 m³/h → 4 mA; 156,25 mmH₂O → 100 m³/h → 8 mA; 625 mmH₂O → "
        "200 m³/h → 12 mA; 1406,25 mmH₂O → 300 m³/h → 16 mA; 2500 mmH₂O → "
        "400 m³/h → 20 mA."
    ),
    "rastreabilidade": (
        "Não foram informados padrão de pressão diferencial, certificado de calibração ou "
        "cadeia de rastreabilidade metrológica para os valores observados. O Commubox FXA195 "
        "foi utilizado como interface de comunicação, não como padrão de medição. O memorial "
        "de cálculo/datasheet da placa de orifício também permanece pendente. Portanto, os "
        "resultados registrados têm caráter de diagnóstico e configuração, não de calibração."
    ),
    "resultados": (
        "Configuração aplicada: 0-2500 mmH₂O, Square Root, saída 4-20 mA e indicação local "
        "0-400 m³/h. Para ΔP ≈ 1250 mmH₂O: Q = 400 × √(1250/2500) ≈ 283 m³/h, "
        "compatível com os 280-284 m³/h observados. Em escala linear, a indicação equivalente "
        "seria aproximadamente 200 m³/h. Uma segunda extração de raiz no CLP elevaria a indicação "
        "para ordem de 336 m³/h nessa condição. Para vazão real de 180 m³/h, o diferencial "
        "estimado seria ΔP = (180/400)² × 2500 ≈ 506 mmH₂O. A divergência permanece em análise."
    ),
}


DADOS_ANTERIORES = {
    "tipo_manutencao": "ajuste",
    "data_saida": date(2026, 7, 30),
    "condicao_recebida": "Equipamento novo.",
    "condicao_saida": "Equipamento novo.",
    "diagnostico": "Equipamento instalado, teste realizado equipamebti liberado para o processo.",
    "parecer_tecnico": "Equipamento funcionsanod perfeitamente, aguardando novo teste para finalizar configuração do equipamento.",
    "criterio_aceitacao": "não se aplica.",
    "status": "conforme",
    "observacoes": "",
    "proxima_manutencao": date(2026, 8, 12),
    "intervencoes": "Instalação do eqipamento novo, na planta ete.",
    "materiais": "Equipamento.",
    "verificacoes": "Teste 4 a 20ma, teste de vazão e teste de estanqueidae",
    "rastreabilidade": "Padrão de Pressão e Calibrado de porcesso.",
    "resultados": "Resultados satisfatorio.",
}


def _atualizar_man0004(apps, dados):
    Manutencao = apps.get_model("manutencao", "Manutencao")
    manutencao = Manutencao.objects.filter(numero_relatorio="MAN-0004").first()
    if manutencao is None:
        return
    instrumento = manutencao.instrumento
    if instrumento.modelo != "APR-2000ALW" or instrumento.numero_serie != "07261168":
        raise RuntimeError("MAN-0004 não corresponde ao Aplisens APR-2000ALW série 07261168.")
    Manutencao.objects.filter(pk=manutencao.pk).update(**dados)


def preencher_man0004(apps, schema_editor):
    _atualizar_man0004(apps, NOVOS_DADOS)


def restaurar_man0004(apps, schema_editor):
    _atualizar_man0004(apps, DADOS_ANTERIORES)


class Migration(migrations.Migration):
    dependencies = [
        ("manutencao", "0007_alter_manutencao_status"),
    ]

    operations = [
        migrations.RunPython(preencher_man0004, restaurar_man0004),
    ]
