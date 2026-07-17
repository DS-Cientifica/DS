# Glossario de abreviacoes do sistema

Este documento consolida as abreviacoes, siglas e prefixos internos encontrados no sistema.

Objetivo:
- reduzir dupla interpretacao;
- melhorar padronizacao de telas, PDFs e planilhas;
- apoiar rastreabilidade operacional e metrologica.

Observacao importante:
- esta lista foi montada a partir de uma varredura no codigo atual;
- quando a sigla aparece no sistema mas nao tem definicao formal no proprio codigo, ela foi marcada como `pendente de padronizacao`.

## 1. Comerciais, fiscais e cadastro

| Sigla | Significado | Uso no sistema | Status |
| --- | --- | --- | --- |
| CNPJ | Cadastro Nacional da Pessoa Juridica | cadastro de clientes, propostas, PDFs, autofill | validado |
| IE | Inscricao Estadual | cadastro de clientes, propostas, pedido de compra | validado |
| CEP | Codigo de Enderecamento Postal | autofill de endereco do cliente | validado |
| UF | Unidade Federativa | endereco do cliente | validado |
| CRM | Customer Relationship Management / gestao de relacionamento comercial | registros de CRM, tickets, propostas vinculadas | validado |
| PDF | Portable Document Format | exportacoes e impressao de propostas, certificados, pedidos e relatorios | validado |
| CIF | Cost, Insurance and Freight | condicao comercial de frete na proposta | validado |
| FOB | Free On Board | condicao comercial de frete na proposta | validado |
| DDL | sigla usada em prazo de pagamento, ex.: `28 DDL` | propostas e testes | pendente de padronizacao |

## 2. Metrologia, calibracao e manutencao

| Sigla | Significado | Uso no sistema | Status |
| --- | --- | --- | --- |
| OS | Ordem de Servico | planejamento, calibracao, PDFs | validado |
| MRC | Material de Referencia Certificado | calibracao de pH e rastreabilidade | validado |
| RBC | Rede Brasileira de Calibracao | textos de rastreabilidade em certificados | validado |
| CGCRE | Coordenacao Geral de Acreditacao | textos comerciais e referencias reguladoras | validado |
| NTU | Nephelometric Turbidity Unit | calibracao de turbidez | validado |
| pH | potencial hidrogenionico | calibracao de pH | validado |
| mV | milivolt | calibracao eletrica de pH | validado |
| Veff | graus de liberdade efetivos | tabelas e certificados de incerteza | validado |
| EMA | Erro Maximo Admissivel | tabelas de calibracao em pH e pressao | inferido pelo contexto; recomenda-se explicitar |
| ORP | Oxidation Reduction Potential / potencial de oxidacao e reducao | grandeza prevista no sistema e no dominio metrologico | validado no dominio; revisar exibicao se for para cliente |
| HART | Highway Addressable Remote Transducer | manutencao de transmissores e relatorios tecnicos | validado no contexto tecnico |
| LRV | Lower Range Value | manutencao/configuracao de transmissores | validado no contexto tecnico |
| URV | Upper Range Value | manutencao/configuracao de transmissores | validado no contexto tecnico |
| IN LOCO | execucao no campo / nas instalacoes do cliente | propostas, calibracoes e planejamento | validado |

## 3. RH, gestao e operacao

| Sigla | Significado | Uso no sistema | Status |
| --- | --- | --- | --- |
| RH | Recursos Humanos | area de colaboradores, cargos e treinamentos | validado |
| CLT | Consolidacao das Leis do Trabalho | tipo de colaborador | validado |
| PJ | Pessoa Juridica | tipo de colaborador | validado |
| ASO | Atestado de Saude Ocupacional | anexo de colaborador | validado |
| EPI | Equipamento de Protecao Individual | recursos necessarios no planejamento | validado |

## 4. Prefixos internos de codigos

Esses prefixos sao usados pelo proprio sistema para gerar identificadores internos.

| Prefixo | Significado | Exemplo | Origem |
| --- | --- | --- | --- |
| CL- | cliente | `CL-0001` | cadastro de clientes |
| PROP- | proposta comercial | `PROP-0001/26` | propostas |
| CRM- | registro de CRM | `CRM-0001/26` | registros de CRM |
| TKT- | ticket de CRM | `TKT-0001/26` | tickets de CRM |
| CAR- | cargo/funcao | `CAR-0001` | RH |
| COL- | colaborador | `COL-0001` | RH |
| TRE- | treinamento | `TRE-0001` | RH |
| PLAN- | planejamento de servico | `PLAN-0001/26` | planejamento |
| DEV- | projeto de desenvolvimento tecnico | `DEV-0001` | projetos |
| MKT- | campanha de marketing | `MKT-0001` | marketing |
| EQ- | codigo interno de instrumento importado por planilha | `EQ-0001` | importacao de instrumentos |
| PT- | tag operacional do equipamento | `PT-101` | importacao de instrumentos |
| SN- | numero de serie em exemplos de importacao | `SN-12345` | importacao de instrumentos |
| CL- | produto/servico do tipo calibracao | `CL-0001` | produtos/servicos |
| PRD- | produto | `PRD-0001` | produtos/servicos |
| MAN- | manutencao | `MAN-0001` | produtos/servicos / relatorios |
| QUA- | qualificacao | `QUA-0001` | produtos/servicos |

## 5. Prefixos de certificados e documentos tecnicos

| Prefixo | Significado observado | Observacao |
| --- | --- | --- |
| PRE | certificado de pressao | aparece no mapa de prefixo de certificados de pressao |
| CLOR | certificado/ensaio ligado a cloro | aparece no mapa de prefixo do colorimetro |
| FLUOR | certificado/ensaio ligado a fluoreto | aparece no mapa de prefixo do colorimetro |
| COR | certificado/ensaio ligado a cor | aparece no mapa de prefixo do colorimetro |
| FOTO | certificado/ensaio ligado a fotometria/colorimetria | aparece no mapa de prefixo do colorimetro |
| REV | revisao documental | usado em documentos e revisoes, ex.: `REV.01` |
| DOC-CGCRE-014 | documento de referencia da CGCRE/Inmetro | citado no certificado de pressao |
| CCDS-xxxx | codigo interno de procedimento/metodo da DS Cientifica | aparece em mapeamentos e certificados |

## 6. Termos que hoje geram risco de dupla interpretacao

### DDL
- aparece como prazo de pagamento, por exemplo `28 DDL`;
- o sistema usa a sigla, mas nao traz o significado por extenso;
- risco: cliente, financeiro e comercial podem interpretar de formas diferentes.

Recomendacao:
- substituir na interface por texto completo;
- exemplo: `28 dias da data da liberacao`, `28 dias data laudo` ou o criterio real adotado pela empresa.

### EMA
- aparece nas tabelas tecnicas;
- pelo contexto metrologico, a interpretacao mais provavel e `Erro Maximo Admissivel`;
- risco: se o certificado for entregue a cliente externo sem legenda, pode haver questionamento.

Recomendacao:
- mostrar no cabecalho ou rodape: `EMA = Erro Maximo Admissivel`.

### Veff
- aparece em certificados de incerteza;
- o template de turbidez e colorimetro ja ajuda ao escrever `graus de liberdade efetivos`;
- risco menor, mas ainda vale padronizar em todos os certificados.

Recomendacao:
- padronizar sempre como `Veff (graus de liberdade efetivos)`.

### TAG
- no sistema esta sendo usada como identificacao operacional/fisica do equipamento na planta;
- faz sentido tecnico;
- risco: alguns clientes nao usam TAG e podem confundir com codigo interno do sistema.

Recomendacao:
- manter a diferenciacao explicita:
  - `codigo`: identificador interno do sistema;
  - `tag`: identificacao operacional do cliente ou da planta.

## 7. Leitura critica

O que esta correto:
- o sistema ja diferencia bem varias siglas de negocio e prefixos internos;
- a importacao de instrumentos ja traz legenda util para `codigo`, `tag` e identificacao do cliente;
- os prefixos internos estao relativamente consistentes.

O que esta incorreto ou incompleto:
- ha siglas expostas ao usuario final sem legenda padrao, principalmente `DDL`, `EMA` e `Veff`;
- ha mistura entre prefixo interno, sigla normativa e termo comercial em alguns pontos da interface;
- existe colisao de prefixo `CL-`, hoje usado tanto para cliente quanto para produto/servico de calibracao;
- parte das siglas so fica clara para quem conhece o processo interno.

O que falta:
- uma padronizacao oficial de siglas aceitas pela empresa;
- legenda obrigatoria em PDFs externos;
- regra documental para novas siglas antes de entrarem no sistema.

Impacto tecnico:
- reduz erro de interpretacao em cadastro, proposta, certificado e manutencao.

Impacto financeiro:
- reduz divergencia comercial e questionamento de prazo/frete/faturamento.

Impacto regulatorio:
- melhora clareza documental e reduz risco de observacao em auditoria, especialmente em documentos tecnicos e certificados.

## 8. Recomendacao pratica

Padronizar no sistema, no minimo, estes itens:
1. `DDL` por extenso.
2. `EMA` com legenda.
3. `Veff` com legenda.
4. `TAG` sempre separado de `codigo interno`.
5. `CGCRE`, `RBC` e `MRC` com descricao no primeiro uso em certificados e propostas tecnicas.
6. revisar o prefixo `CL-` em produtos/servicos de calibracao para evitar conflito com `CL-` de cliente.
