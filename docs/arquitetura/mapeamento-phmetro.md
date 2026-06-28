# Mapeamento tecnico da planilha ODS de pH

Fonte analisada:
- `FM - 7.2.1-xxxRV00 Calibração de Medidor de pH- Eletrica e Quimica.ods`

Objetivo do mapeamento:
- servir como base para implementar no Axion uma nova calibração de medidor de pH
- preservar a logica da planilha original antes de codificar qualquer rotina
- identificar dependencias cruzadas entre abas

## 1. Estrutura da planilha

Abas identificadas:
- `PLANILHA`
- `PADROES`
- `GERADOR DETENSAO`
- `CERTIFICADO 2P`
- `CERTIFICADO MP`
- `INCERTEZA ELETRICA`
- `INCERTEZA MRC`
- `CALCULOS`
- `HISTORICO`
- `CERTIFICADO`

## 2. Aba PLANILHA

Aba principal de entrada e consolidacao.

### 2.1 Blocos funcionais

- Informacoes gerais da calibracao
- Informacoes do contratante
- Informacoes do cliente
- Informacoes do equipamento calibrado
- Procedimento utilizado
- Dados dos padroes utilizados
- Condicoes ambientais
- Calibracao eletrica em mV
- Calibracao eletrica em pH
- Calibracao quimica
- Leituras de verificacao
- Observacoes para o certificado
- Identificacao do tecnico, conferente e signatario

### 2.2 Campos de entrada visiveis

- Ordem de servico
- Numero do certificado
- Data de calibracao
- Data de emissao
- Revisa o
- Local de calibracao
- Contratante
- Endereco do contratante
- Cliente
- Endereco do cliente
- Equipamento calibrado
- Marca
- Modelo
- Numero de serie
- Numero de identificacao
- Tipo de indicacao
- Capacidade
- Resolucao em pH
- Resolucao em mV
- Identificacao do eletrodo
- Resolucao do termometro
- Temperatura de referencia
- Tipo de calibracao
- Identificacao do sensor de temperatura
- Unidade de leitura
- Compensacao de temperatura
- Tipo do sensor de temperatura
- Procedimento utilizado
- Revisao do procedimento
- Padroes utilizados
- MRC faixa acida
- MRC neutro
- MRC faixa basica
- MRC de verificacao acida
- MRC de verificacao basica
- Temperatura ambiente inicial/final
- Umidade ambiente inicial/final
- Leituras em mV
- Leituras em pH
- Leituras quimicas/MRC
- Observacoes do certificado
- Tecnico responsavel
- Responsavel pela conferencia
- Signatario autorizado
- Funcao do signatario

### 2.3 Formula e comportamento das secoes principais

#### Parte eletrica em mV

- Valor padrao vem da aba `GERADOR DETENSAO`
- Leituras do instrumento sao lancadas em 3 pontos
- Media:
  - `AVERAGE(leitura1; leitura2; leitura3)`
- Desvio:
  - `STDEV(leitura1; leitura2; leitura3)`
- Erro:
  - `media - valor_padrao`

#### Parte eletrica em pH

- Valor teorico em pH e calculado a partir do valor em mV
- Formula base usada na planilha:
  - `7 - (E(mV) * 96485.3399 / (LN(10) * 8.314472 * (273.15 + 25) * 1000))`
- Leituras de instrumento:
  - avanc o, retorno, avanc o
- Media:
  - `AVERAGE(...)`
- Desvio:
  - `STDEV(...)`
- Erro:
  - `media - pH_teorico`

#### Calibracao quimica

- Usa MRC faixa acida e MRC faixa basica
- Calcula:
  - inclinacao real `k'`
  - `pH0`
  - leitura do padrao de verificacao acida
  - leitura do padrao de verificacao basica

## 3. Aba PADROES

Cadastro consolidado dos padroes de temperatura, gerador de tensao, termohigrometro e MRCs de pH.

### 3.1 Colunas principais observadas

- Codigo
- Tipo
- Data de calibracao/abertura
- Numero do certificado
- Laboratorio/emitente
- Validade
- Resolucao
- Rastreabilidade
- Incerteza do padrao
- k
- Veff
- Variacao residual
- Erro maximo
- Equacao
- Unidade de medida
- Capacidade
- Deriva
- Valor nominal
- Data de atualizacao
- Responsavel

### 3.2 Status calculado

- `OK` quando ainda esta valido
- `VENCIDO` quando a data de validade acabou

### 3.3 Dependencia com PLANILHA

- a planilha principal seleciona o padrao por codigo
- os campos da selecao puxam automaticamente os dados do cadastro
- o estado de validade alimenta o alerta visual

## 4. Aba GERADOR DETENSAO

Bloco auxiliar usado na parte eletrica em mV.

Funcoes percebidas:
- fornecer os valores de referencia para o gerador/multimetro padrao
- alimentar as referencias de cada ponto da parte eletrica

## 5. Aba INCERTEZA ELETRICA

Orcamento de incerteza da parte eletrica.

### 5.1 Estrutura

- blocos separados por ponto de leitura
- blocos em mV e em pH
- calculo de incerteza padrao, incerteza expandida, k e Veff

### 5.2 Componentes observados

- repetitividade do medidor de pH
- resolucao do medidor
- incerteza do PLJ
- incerteza do MRC
- incerteza da temperatura
- constante de Faraday
- constante dos gases
- incerteza do pH(X)

### 5.3 Formula padrao recorrente

- componente padrao:
  - `u(xi) = valor / divisor`
- componente em saida:
  - `ui(y) = u(xi) * Ci`
- incerteza combinada:
  - `uc = sqrt(soma dos quadrados)`
- incerteza expandida:
  - `U = uc * k`
- fator de abrangencia:
  - `k = TINV(0.0455; Veff)` quando aplicavel
- graus efetivos:
  - `Veff` por Welch-Satterthwaite

### 5.4 Observacoes tecnicas

- A planilha original usa muitos retornos `#DIV/0!`, `#VALOR!` e `#REF!` quando dados estao ausentes.
- No sistema, isso deve virar tratamento controlado, nao erro bruto exibido ao usuario.

## 6. Aba INCERTEZA MRC

Orcamento de incerteza da parte quimica/MRC.

### 6.1 Estrutura

- secao para 2 pontos, faixa acida
- secao para 2 pontos, faixa basica
- secao multiponto

### 6.2 Componentes observados

- repetitividade
- resolucao do instrumento
- incerteza do padrao
- resolucao do padrao
- incerteza de curva
- incerteza do turbidimetro/pHmetro quando aplicavel

### 6.3 Formula principal

- combinacao quadratica dos componentes:
  - `uc = sqrt(repetibilidade^2 + resolucao_instrumento^2 + incerteza_padrao^2 + resolucao_padrao^2 + incerteza_curva^2 + ...)`
- incerteza expandida:
  - `U = uc * k`
- EMA do ponto:
  - `EMA = abs(erro) + U`

## 7. Aba CALCULOS

Aba de calculos auxiliares e consolidacao tecnica.

### 7.1 Parte eletrica

Blocos observados:
- incerteza de medicao do instrumento mostrador de pH em mV
- incerteza de medicao do instrumento mostrador de pH em pH
- incerteza expandida da inclinacao teorica
- incerteza expandida da inclinacao real
- incerteza expandida da inclinacao relativa

### 7.2 Formulas principais observadas

- `k' = (E(S1) - E(S2)) / (pH(S2) - pH(S1))`
- `pH0 = pH(S1) + E(S1) / k'`
- intercepcao:
  - `E(S1) + pH(S1) * k'`
- eficiencia eletromotriz:
  - `k' / 59.16`
- slope relativo:
  - `eficiencia eletromotriz * 100`
- `pH(X)`:
  - `pH(S1) - (leitura_mV - E(S1)) / k'`
- regressao:
  - usa equivalentes de `SLOPE`, `INTERCEPT`, `RSQ`, `AVERAGE`, `STDEV`, `COUNT`, `SUM`, `SUMSQ`

### 7.3 Pontos criticos observados

- a planilha usa referencias diretas a `PLANILHA`, `PADROES` e blocos de incerteza
- valores nulos provocam varias cascatas de erro na origem
- o sistema precisa recalcular com seguranca e salvar o resultado final ja sanitizado

## 8. Abas CERTIFICADO 2P, CERTIFICADO MP e CERTIFICADO

Saidas formatadas para impressao.

Campos que aparecem ou sao esperados:
- numero do certificado
- revisao
- data de calibracao
- data de emissao
- contratante
- cliente
- equipamento
- procedimento
- condicoes ambientais
- rastreabilidade metrologica
- resultados eletricos
- resultados quimicos
- slope real
- pH0
- eficiencia eletromotriz
- slope relativo
- erro
- incerteza expandida
- fator k
- Veff
- observacoes
- responsaveis e assinatura

## 9. Aba HISTORICO

Registro de revisao e rastreabilidade da planilha.

Comportamento esperado:
- criacao
- alteracao
- revisao
- responsavel
- data e hora

## 10. Dependencias cruzadas mais importantes

- `PLANILHA` usa dados de `PADROES`
- `PLANILHA` usa dados de `GERADOR DETENSAO`
- `CALCULOS` usa dados de `PLANILHA`
- `INCERTEZA MRC` usa `PADROES`, `PLANILHA` e `CALCULOS`
- `CERTIFICADO` consome os resultados consolidados de `PLANILHA` e `CALCULOS`

## 11. Campos com alerta, vencido ou vazio controlado

### Status esperados na planilha original

- `OK`
- `VENCIDO`
- `ALERTA`
- `NÃO CONSTA`
- `--------`

### Regra de interpretacao para o sistema

- campo obrigatorio vazio:
  - bloquear ou mostrar `ALERTA`
- campo opcional vazio:
  - mostrar `--------`
- padrao vencido:
  - mostrar `VENCIDO` ou `ALERTA`
- dado inexistente de equipamento:
  - mostrar `NÃO CONSTA`

## 12. Conclusao tecnica

A planilha de pH nao e um simples formulario:
- ela mistura entrada operacional, selecao de padroes, calculos eletricos, calculos quimicos e emissao de certificado
- ha forte dependencia entre abas
- existe logica de validacao por status, validade e rastreabilidade
- a implementacao no Axion deve ser feita com servico de calculo dedicado, para nao espalhar regra em template ou admin

Proxima etapa recomendada:
- mapear os modelos e telas atuais do modulo `calibracao`
- desenhar a modelagem do novo tipo de calibracao de pH
- implementar primeiro a estrutura de dados e o servico de calculo
