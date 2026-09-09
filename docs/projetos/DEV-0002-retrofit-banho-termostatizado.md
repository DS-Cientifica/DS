# DEV-0002 - Retrofit de banho termostatizado

## Identificacao

- Codigo: DEV-0002
- Nome: Retrofit de banho termostatizado
- Titulo tecnico: Retrofit e modernizacao do sistema de controle de banho termostatizado UH4
- Tipo: Retrofit de equipamento
- Area: projeto interno / desenvolvimento tecnico
- Prioridade: alta
- Status previsto: em desenvolvimento
- Fase atual informada: montagem eletrica e validacao funcional
- Inicio: 16/07/2026
- Previsao inicial de conclusao: 15/08/2026

## Equipamento

- Equipamento: banho termostatizado UH4
- Fabricante original: VEB MLW Prufgerate-Werk Medingen Sitz Freital
- Origem: Republica Democratica Alema - GDR
- Modelo: UH4
- Numero de fabricacao identificado: 4606
- Numero de serie identificado: ELN 13892520
- Tensao nominal: 220 Vca
- Potencia nominal informada: aproximadamente 1,72 kW

## Objetivo

Modernizar o banho termostatizado UH4 por meio da substituicao do sistema eletronico analogico original por um sistema digital de controle de temperatura, preservando sempre que tecnicamente viavel a estrutura mecanica, a cuba de aco inoxidavel, a resistencia de aquecimento, o conjunto hidraulico e o motor de circulacao originais.

O novo sistema devera utilizar controlador PID REX-C100, termopar tipo K, rele de estado solido SSR-40DA, dissipador termico, entrada IEC com chave liga/desliga e fusivel integrado, novo cabeamento, terminais e aterramento da estrutura.

## Escopo incluido

- Inspecao visual e diagnostico inicial.
- Desmontagem do controlador eletronico original.
- Registro fotografico dos componentes e ligacoes.
- Identificacao do equipamento e dos principais componentes.
- Limpeza da estrutura e do motor.
- Avaliacao preliminar da resistencia.
- Medicao da resistencia eletrica do aquecedor.
- Avaliacao do motor de circulacao.
- Avaliacao e substituicao do capacitor do motor, se necessario.
- Instalacao do controlador PID REX-C100.
- Instalacao do SSR-40DA.
- Instalacao do dissipador e pasta termica.
- Instalacao do termopar tipo K.
- Instalacao de entrada IEC com chave e fusivel.
- Refazimento do cabeamento.
- Instalacao de terminais apropriados.
- Aterramento da estrutura.
- Testes eletricos antes da energizacao.
- Teste funcional inicial.
- Teste de circulacao.
- Teste de aquecimento.
- Ajuste inicial do controlador PID.
- Avaliacao de estabilidade da temperatura.
- Elaboracao de documentacao tecnica.

## Escopo excluido nesta versao

- Sistema de refrigeracao ativo por compressor.
- Disjuntor termomagnetico adicional.
- Indicador luminoso externo de aquecimento.
- Protecao eletronica por falta de agua.
- Termostato independente de seguranca, salvo se o componente original for validado.
- Supervisorio ou registro automatico de dados.
- Comunicacao RS-485.
- Certificacao formal do equipamento.
- Declaracao de conformidade para uso regulamentado.
- Calibracao acreditada.
- Substituicao completa da resistencia ou do motor, salvo falha durante os testes.

## Arquitetura eletrica

Circuito de alimentacao:

```text
Rede 220 Vca
-> entrada IEC
-> fusivel
-> chave liga/desliga
-> distribuicao para controlador, motor e circuito de potencia da resistencia
```

Circuito da resistencia:

```text
Condutor ativo apos chave/fusivel
-> borne 1 do SSR
-> borne 2 do SSR
-> terminal da resistencia
-> outro terminal da resistencia
-> segundo condutor da alimentacao
```

Comando do SSR:

```text
Borne 4 do REX-C100 -> borne 3 positivo do SSR
Borne 5 do REX-C100 -> borne 4 negativo do SSR
```

Sensor:

```text
Termopar K positivo -> borne 9 do controlador
Termopar K negativo -> borne 10 do controlador
```

Aterramento:

```text
Pino de terra da entrada IEC
-> estrutura metalica principal
-> carcaca da cuba
-> suportes metalicos acessiveis
-> carcaca do motor, quando aplicavel
```

Nota critica: nao definir a ligacao do motor somente pelas cores dos fios. Antes da ligacao, identificar comum, enrolamento principal e enrolamento auxiliar por medicoes de resistencia.

## Memoria de calculo eletrica

Resistencia medida aproximada: 30 ohms.

Corrente teorica:

```text
I = V / R
I = 220 / 30
I = 7,33 A
```

Potencia teorica:

```text
P = V^2 / R
P = 220^2 / 30
P = 1.613 W
```

Conclusao tecnica: o valor medido e coerente com a potencia aproximada informada na placa. A continuidade eletrica nao substitui o ensaio de isolamento.

## Lista de materiais

| Item | Material | Quantidade | Status |
| --- | --- | ---: | --- |
| 1 | Controlador PID REX-C100 | 1 | adquirido |
| 2 | Rele de estado solido SSR-40DA | 1 | adquirido |
| 3 | Dissipador de aluminio para SSR | 1 | adquirido |
| 4 | Pasta termica | 1 | confirmar |
| 5 | Termopar tipo K | 1 | adquirido |
| 6 | Entrada IEC C14 com chave e fusivel | 1 | adquirido |
| 7 | Fusivel retardado T10 A / 250 V | 2 | confirmar |
| 8 | Capacitor permanente 2 uF / 450 Vca | 1 | recomendado |
| 9 | Cabo de alimentacao 3 x 1,5 mm2 | 1 | pendente |
| 10 | Cabo de potencia 1,5 ou 2,5 mm2 | 2 m | parcial |
| 11 | Cabo de comando 0,5 a 0,75 mm2 | 2 m | parcial |
| 12 | Cabo/extensao para termopar K | conforme necessidade | adquirido |
| 13 | Terminais Faston | 10 | confirmar |
| 14 | Terminais tipo olhal | 10 | confirmar |
| 15 | Terminais ilhos | 20 | pendente |
| 16 | Espaguete termo-retratil | 2 m | confirmar |
| 17 | Abracadeiras de nylon | 20 | pendente |
| 18 | Borne de ligacao minimo 20 A | 1 | reaproveitado |
| 19 | Fio verde/amarelo de aterramento | conforme necessidade | parcial |
| 20 | Etiquetas ou anilhas | 1 conjunto | pendente |

## Etapas

1. Levantamento e identificacao - concluida - 100%.
2. Registro fotografico - concluida - 100%.
3. Desmontagem da eletronica original - concluida - 100%.
4. Avaliacao da estrutura mecanica - concluida - 100%.
5. Limpeza do motor e da estrutura - em andamento - 80%.
6. Avaliacao da resistencia - concluida parcialmente - 70%.
7. Avaliacao do motor - em andamento - 60%.
8. Definicao da arquitetura do retrofit - concluida - 100%.
9. Aquisicao dos componentes - concluida parcialmente - 80%.
10. Instalacao mecanica do controlador - concluida parcialmente - 80%.
11. Instalacao do SSR e dissipador - concluida parcialmente - 80%.
12. Refazimento da fiacao - em andamento - 65%.
13. Identificacao dos fios do motor - pendente - 20%.
14. Testes eletricos sem energizacao - pendente - 20%.
15. Energizacao controlada - pendente - 0%.
16. Teste de circulacao - pendente - 0%.
17. Teste de aquecimento - pendente - 0%.
18. Ajuste PID - pendente - 0%.
19. Estudo de estabilidade termica - pendente - 0%.
20. Organizacao final do chicote - pendente - 0%.
21. Fechamento e acabamento - pendente - 0%.
22. Relatorio tecnico - pendente - 0%.
23. Avaliacao metrologica - pendente - 0%.

## Riscos

1. Choque eletrico em 220 Vca proximo a agua.
2. Fuga eletrica da resistencia para a cuba.
3. Superaquecimento por falha do SSR fechado.
4. Funcionamento da resistencia sem agua.
5. Ligacao incorreta do motor ou capacitor.
6. Superaquecimento do SSR por dissipacao insuficiente.
7. Falha ou baixa qualidade do SSR de baixo custo.
8. Leitura incorreta por termopar incompativel ou polaridade invertida.
9. Contato acidental com terminais energizados.
10. Desempenho termico insuficiente ou instavel.

## Checklist de verificacao

- Confirmar tensao, fusivel, capacidade do modulo IEC e aperto dos terminais.
- Confirmar aterramento da estrutura, da cuba e continuidade do terra.
- Confirmar ausencia de curto entre condutores.
- Confirmar resistencia de aproximadamente 30 ohms.
- Executar teste de isolamento com megometro, preferencialmente a 500 Vcc.
- Confirmar posicao do SSR, pasta termica, dissipador e ventilacao.
- Confirmar polaridade do comando do SSR.
- Confirmar termopar nos bornes 9 e 10.
- Identificar fios do motor por resistencia.
- Confirmar ligacao correta do capacitor.
- Energizar inicialmente sem a resistencia conectada.
- Testar motor separadamente.
- Conectar a resistencia somente apos aprovacao dos testes anteriores.
- Monitorar corrente, temperatura do dissipador, temperatura do motor e tensao da rede.
- Confirmar circulacao de agua, ausencia de vazamentos e estabilidade termica.

## Cronograma

| Data | Marco |
| --- | --- |
| 16/07/2026 | Inicio do levantamento e desmontagem |
| 19/07/2026 | Definicao da arquitetura eletrica |
| 22/07/2026 | Montagem eletrica inicial |
| 25/07/2026 | Identificacao e teste do motor |
| 28/07/2026 | Testes eletricos sem energizacao |
| 30/07/2026 | Primeira energizacao controlada |
| 03/08/2026 | Testes de aquecimento e circulacao |
| 07/08/2026 | Ajuste PID |
| 10/08/2026 | Estudo de estabilidade |
| 13/08/2026 | Organizacao e acabamento |
| 15/08/2026 | Relatorio tecnico e encerramento preliminar |

Datas futuras devem ser tratadas como planejamento, nao como execucao concluida.

## Custos

- Orcamento previsto: R$ 500,00.
- Custo realizado: nao inventar.
- Valor confirmado somente se houver documento de compra: kit REX-C100, R$ 181,65.
- Entrada IEC e fusiveis: estimativa R$ 30,00 a R$ 60,00.
- Capacitor: estimativa R$ 20,00 a R$ 40,00.
- Cabos e terminais: estimativa R$ 60,00 a R$ 120,00.
- Pasta termica, termo-retratil e consumiveis: estimativa R$ 30,00 a R$ 60,00.
- Contingencia: R$ 80,00.

## Criterios de aceite

- Equipamento liga sem desarme do fusivel.
- Controlador inicializa normalmente.
- Termopar apresenta leitura coerente.
- Motor parte sem auxilio manual.
- Circulacao de agua e observada.
- Resistencia aquece somente quando comandada.
- SSR desliga a resistencia quando solicitado.
- Corrente da resistencia e coerente com aproximadamente 1,6 kW.
- Nao existe fuga eletrica detectavel para a carcaca.
- Terra apresenta continuidade adequada.
- Nao existem vazamentos.
- Dissipador permanece em temperatura operacional aceitavel.
- Motor nao apresenta superaquecimento anormal.
- Sistema atinge 30 C, 40 C e 50 C.
- Temperatura estabiliza dentro do limite definido.
- Overshoot inicial registrado e avaliado.
- Todos os fios ficam identificados.
- Terminais energizados ficam protegidos.
- Esquema eletrico final anexado.
- Relatorio tecnico emitido.

Aceitacao preliminar: variacao maxima de +/-1,0 C no ponto de medicao apos estabilizacao.

Aceitacao final: definir somente apos caracterizacao termica e avaliacao metrologica.

## Pendencias

- Confirmar ligacao eletrica do motor por medicao dos enrolamentos.
- Executar teste de isolamento da resistencia.
- Confirmar capacidade do modulo IEC e da chave.
- Confirmar fusivel T10 A / 250 V.
- Instalar protecoes contra contato acidental.
- Validar dissipacao termica do SSR.
- Registrar corrente total e corrente da resistencia.
- Registrar estabilidade, overshoot e uniformidade termica.
- Emitir relatorio tecnico.
- Nao declarar equipamento aprovado para uso metrologico antes dos testes funcionais, eletricos e termicos.
