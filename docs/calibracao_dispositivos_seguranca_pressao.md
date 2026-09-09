# Calibração de dispositivos de segurança - pressão

## Objetivo e escopo

O fluxo atende, nesta primeira etapa, somente dispositivos cujo mensurando principal é pressão:

- válvula de segurança;
- válvula de alívio;
- válvula de segurança e alívio;
- pressostato;
- vacuostato.

O cadastro separa `calibração`, `ensaio funcional` e `ensaio e ajuste`. A classificação deve refletir o serviço efetivamente executado; ajuste e manutenção não são sinônimos de calibração.

## Mapeamento do certificado de referência

| Modelo atual | Campo no AXION |
| --- | --- |
| Empresa e endereço | Cliente, contratante e endereço (snapshot) |
| Tipo de válvula | Tipo de dispositivo |
| TAG e equipamento | TAG e equipamento protegido |
| Fluido de serviço | Fluido de serviço |
| Fabricante, modelo e série | Identificação do dispositivo (snapshot do instrumento) |
| Tamanho e conexão | Tamanho nominal e tipo de conexão |
| Pressão de ajuste / PMTA | Pressão de ajuste declarada e PMTA |
| Fluido de teste | Fluido de teste |
| Ensaio, ajuste, quente e manutenção | Tipo documental e marcadores de intervenção |
| Exame visual e constatações | Condição inicial, defeitos e condição final |
| Pressão requerida | Pressão de referência do ponto |
| Pressão antes da abertura / final | Pontos “como encontrado” e “como deixado” |
| Padrão utilizado | Vínculo ao cadastro `Padrao` com snapshot rastreável |
| Laudo inicial | Resultado agregado dos pontos “como encontrado” |

O valor de referência identificado no arquivo foi `4,08 kgf/cm²`; o valor final mostrado foi `4,20 kgf/cm²`, com erro informado de `0,12 kgf/cm²`. No AXION, a correção correspondente é armazenada como `-0,12 kgf/cm²`, conforme a relação entre erro e correção.

## Memória de cálculo

Para as leituras de atuação `x_i` e pressão de referência `x_ref`:

```text
Média de atuação:       x_bar = Σx_i / n
Erro de medição:        E = x_bar - x_ref
Correção:               C = -E
Repetitividade (faixa): R = max(x_i) - min(x_i)
Desvio-padrão amostral: s = sqrt[Σ(x_i - x_bar)² / (n - 1)]
Histerese:              H = |x_bar_atuacao - x_bar_rearme|
```

Componentes-padrão da incerteza:

```text
Repetitividade:         u_rep = s / sqrt(n)
Resolução:              u_res = resolução / sqrt(12)
Certificado do padrão:  u_cert = U_cert / k_cert
Deriva (limite):        u_deriva = limite / sqrt(3)
Combinada:              u_c = sqrt(Σu_i²)
Expandida:              U = k * u_c
```

O fator `k = 2` é valor inicial editável. A emissão deve usar o fator definido no procedimento e coerente com os graus de liberdade efetivos. O sistema registra `Veff`, mas não presume que todo resultado possua `Veff = infinito`.

## Critério e regra de decisão

O critério pode ser absoluto ou percentual da pressão de referência:

```text
Tolerância absoluta:    T = valor informado
Tolerância percentual:  T = |x_ref| * percentual / 100
```

Regras disponíveis:

- sem declaração de conformidade: o certificado apresenta resultados, mas não conclui aprovado/reprovado;
- aceitação simples: aprovado quando `|E| ≤ T`;
- banda de guarda: aprovado quando `|E| + U ≤ T`.

A origem do critério e a referência documental devem ser registradas. PMTA, pressão de ajuste de placa e tolerância não devem ser tratados automaticamente como equivalentes.

## Controles de conformidade e risco

A emissão é bloqueada quando faltarem dados críticos, método, condições ambientais, padrão, ponto/ciclo, responsáveis ou critério quando houver declaração de conformidade. Padrão suspenso, vencido na data do serviço, calibrado somente após o serviço, com unidade divergente ou com rastreabilidade incompleta também bloqueia a emissão. Conversões de unidade não são presumidas silenciosamente no orçamento de incerteza.

O certificado de referência não evidencia, no mesmo quadro de resultados, todos os elementos necessários para sustentar a afirmação de incerteza e conformidade. O novo fluxo exige:

- resultado numérico por condição, preservando “como encontrado” e “como deixado”;
- identificação e validade do padrão na data;
- incerteza expandida por ponto, fator de abrangência e graus de liberdade quando aplicável;
- critério, origem, referência e regra de decisão;
- método e revisão vigentes;
- responsável técnico e executor.

As referências ASME, NR-13, ISO/IEC 17025 ou outras não são preenchidas automaticamente. A aplicabilidade, edição e escopo devem ser confirmados tecnicamente antes da emissão.

## Fluxo operacional

1. Cadastrar ou selecionar o instrumento do cliente.
2. Criar a calibração em **Gestão Metrológica > Dispositivos de segurança - pressão**.
3. Selecionar o tipo de documento correspondente ao serviço contratado.
4. Registrar condições, método, exame visual e intervenção.
5. Vincular padrões existentes; os dados são copiados para um snapshot auditável.
6. Registrar ciclos “como encontrado” e, se houver ajuste, “como deixado”.
7. Preencher o orçamento de incerteza de cada condição/ponto.
8. Registrar critério e regra de decisão quando houver declaração de conformidade.
9. Corrigir todas as pendências e somente então mudar o status para **Emitida**.
10. Visualizar e imprimir/salvar o certificado em PDF.
