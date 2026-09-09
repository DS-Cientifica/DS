# Calibração de esfigmomanômetros

## Escopo

O módulo registra calibrações de esfigmomanômetros analógicos aneroides, digitais automáticos e digitais não automáticos. O fluxo é independente da calibração genérica de pressão, preservando os registros históricos existentes.

O certificado emitido é de **calibração** e não substitui aprovação de modelo, marca de verificação ou certificado de verificação legal do Inmetro/RBMLQ-I. Em especial, selecionar “calibração após manutenção/reparo” não autoriza o retorno legal do instrumento ao uso.

## Referências regulatórias e técnicas

- Portaria Inmetro nº 341/2021 e seu Regulamento Técnico Metrológico consolidado.
- NIT-Sefiq-025 e NIT-Sefiq-026 vigentes, conforme aplicabilidade à tecnologia.
- OIML R 148:2020 (não automáticos) e OIML R 149:2020 (automáticos), quando adotadas pelo método validado.
- ABNT NBR ISO/IEC 17025:2017, VIM e GUM para método, rastreabilidade, resultado e incerteza.

Os valores regulatórios são referências configuráveis, não uma declaração automática de verificação legal:

- erro máximo permitido inicial/após reparo: ±3 mmHg ou ±0,4 kPa;
- erro máximo permitido em verificação periódica: ±4 mmHg ou ±0,5 kPa;
- escapamento de ar não automático: 4 mmHg/min ou 0,5 kPa/min;
- escapamento de ar automático: 6 mmHg/min ou 0,8 kPa/min;
- condições de referência: 15 °C a 25 °C e 20 % a 85 % UR.

## Cálculos

- Média: `Ī = ΣIᵢ / n`.
- Erro de indicação: `E = Ī - R`.
- Correção: `C = -E`.
- Histerese: `H = |Ī crescente - Ī decrescente|`.
- Desvio-padrão experimental: `s = sqrt[Σ(Iᵢ-Ī)²/(n-1)]`.
- Incerteza da média por repetitividade: `u_rep = s/sqrt(n)`.
- Resolução com distribuição retangular: `u_res = resolução/sqrt(12)`.
- Certificado do padrão: `u_pad = U_pad/k_pad`.
- Deriva com distribuição retangular: `u_der = limite/sqrt(3)`.
- Incerteza padrão combinada: `u_c = sqrt(Σuᵢ²)`.
- Incerteza expandida: `U = k·u_c`.
- Taxa de escapamento: `q = |P_inicial-P_final|/tempo`.

### Componentes efetivamente aplicáveis

O orçamento básico utiliza apenas componentes demonstradas pelo próprio ensaio: repetitividade das leituras, resolução do esfigmomanômetro e incerteza declarada no certificado do padrão. A resolução adicional do padrão fica desativada por padrão para evitar dupla contagem e somente deve ser incluída quando a quantização da leitura usada no ensaio não estiver adequadamente representada em outra componente. A deriva também fica desativada e exige limite sustentado por histórico, especificação ou verificação intermediária. Qualquer outra componente requer valor e identificação técnica.

Histerese não é somada automaticamente ao orçamento quando os erros crescente e decrescente são declarados separadamente. Condições ambientais controladas não viram uma parcela arbitrária de incerteza; um efeito ambiental só deve ser incluído quando houver coeficiente de sensibilidade e variação relevantes e sustentados pelo método. Componentes correlacionadas não devem ser repetidas como se fossem independentes.

### Resolução e algarismos apresentados

Os valores são mantidos internamente com casas adicionais para impedir erros de arredondamento em médias, incerteza e regra de decisão. Na interface de resultados e no certificado, referência, médias, erros, correções, histerese, tolerância, vazamento e incerteza expandida são apresentados com as casas decimais determinadas pela resolução cadastrada do esfigmomanômetro. Exemplos: resolução `1 mmHg` apresenta `101 mmHg`; resolução `0,1 mmHg` apresenta `101,3 mmHg`; resolução `0,01 mmHg` apresenta `101,33 mmHg`.

O arredondamento de apresentação não altera o valor usado na avaliação de conformidade. Dados ambientais, duração, fator de abrangência e dados do padrão conservam a resolução própria de suas respectivas grandezas e fontes.

Na aceitação simples, aprova-se quando `máx(|E|) ≤ tolerância`. Com banda de guarda, aprova-se quando `máx(|E|) + U ≤ tolerância`. A regra e a origem do critério precisam constar no registro; sem regra, o resultado é “não declarado”.

## Fluxo operacional e controles

1. Cadastrar o instrumento e selecionar a aba “Esfigmomanômetros”.
2. Escolher tecnologia, aplicação, unidade e método validado.
3. Registrar identificação e integridade da braçadeira/manguito.
4. Para digitais, registrar o modo manômetro, isolamento pneumático, conexão e alimentação.
5. Vincular padrões calibrados, válidos e na mesma unidade do ensaio.
6. Executar três indicações crescentes e três decrescentes por ponto.
7. Registrar orçamento de incerteza por ponto e ensaio de escapamento aplicável.
8. Registrar exame geral, zero para aneroide e interrupção imediata para automático.
9. Selecionar critério/regra somente após análise crítica do contrato e do risco de falsa aceitação.
10. Sanar as pendências antes de mudar o status para emitida e revisar o certificado em duas páginas.

O bloqueio de emissão verifica método, condições ambientais ou justificativa, rastreabilidade e unidade dos padrões, ciclos de pressão, ensaios funcionais, critério e assinaturas. A periodicidade de calibração deve ser definida pelo usuário com base no risco, histórico e intensidade de uso; ela não deve ser confundida com a periodicidade da verificação legal.
