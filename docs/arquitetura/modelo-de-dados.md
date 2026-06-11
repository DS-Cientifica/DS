# Modelo de Dados

Este documento descreve os principais blocos de dados do sistema. Ele não substitui as migrations nem os models, mas serve como mapa de navegação.

## Clientes e Usuários

```mermaid
erDiagram
    Cliente ||--o{ ContatoCliente : possui
    Cliente ||--o{ ClienteAnexo : possui
    User ||--o| PerfilUsuario : possui
```

Entidades:

- `Cliente`: dados cadastrais, CNPJ, endereço e identificação comercial.
- `ContatoCliente`: contatos ligados a um cliente.
- `ClienteAnexo`: arquivos relacionados ao cliente.
- `PerfilUsuario`: define escopo de acesso por usuário.

## Comercial

```mermaid
erDiagram
    Cliente ||--o{ Proposta : recebe
    Proposta ||--o{ ItemProposta : contem
    ProdutoServico ||--o{ ItemProposta : compoe
    ProdutoServico ||--o{ ProdutoAnexo : possui
    CRMRegistro ||--o{ CRMInteracao : possui
```

Entidades:

- `ProdutoServico`: catálogo de serviços/produtos.
- `Proposta`: proposta comercial para cliente.
- `ItemProposta`: itens e valores da proposta.
- `CRMRegistro`: oportunidade ou registro comercial.
- `CRMTicket`: demandas de CRM.

## Financeiro

```mermaid
erDiagram
    CategoriaFinanceira ||--o{ ContaPagar : categoriza
    CategoriaFinanceira ||--o{ ContaReceber : categoriza
    PedidoCompra ||--o{ PedidoCompraItem : contem
```

Entidades:

- `CategoriaFinanceira`: classificação financeira.
- `ContaPagar`: obrigações financeiras.
- `ContaReceber`: valores a receber.
- `Imposto`: impostos e competências.
- `PedidoCompra`: compra de fornecedor.
- `PedidoCompraItem`: itens do pedido.

## Metrologia Base

```mermaid
erDiagram
    Cliente ||--o{ Instrumento : possui
    Instrumento ||--o| InstrumentoTecnico : possui
    Instrumento ||--o{ Calibracao : possui
    Instrumento ||--o{ Periodicidade : possui
    Padrao ||--o{ Instrumento : usado_em
    OrdemServico }o--|| Cliente : pertence
```

Entidades:

- `Instrumento`: equipamento do cliente.
- `InstrumentoTecnico`: dados técnicos do equipamento.
- `Padrao`: padrão metrológico com certificado, validade e incerteza.
- `OrdemServico`: OS ligada a cliente/proposta/equipamentos.
- `Calibracao`: calibração geral anterior às especializadas.

## Calibrações Especializadas

### Turbidez

```mermaid
erDiagram
    CalibracaoTurbidez ||--o{ TurbidezPadraoUtilizado : usa
    CalibracaoTurbidez ||--o{ TurbidezVerificacaoPonto : verifica
    CalibracaoTurbidez ||--o{ TurbidezCalibracaoPonto : calibra
    CalibracaoTurbidez ||--o{ TurbidezIncertezaPonto : calcula
```

### Colorímetro

```mermaid
erDiagram
    CalibracaoColorimetro ||--o{ ColorimetroPadraoUtilizado : usa
    CalibracaoColorimetro ||--o{ ColorimetroVerificacaoPonto : verifica
    CalibracaoColorimetro ||--o{ ColorimetroCalibracaoPonto : calibra
    CalibracaoColorimetro ||--o{ ColorimetroIncertezaPonto : calcula
```

### Pressão

```mermaid
erDiagram
    CalibracaoPressao ||--o{ PressaoPadraoUtilizado : usa
    CalibracaoPressao ||--o{ PressaoCalibracaoPonto : calibra
    CalibracaoPressao ||--o{ PressaoIncertezaPonto : calcula
```

Padrão comum:

- modelo principal guarda dados do certificado, cliente, instrumento e ambiente
- modelo de padrões guarda rastreabilidade
- modelo de pontos guarda leituras e resultado
- modelo de incerteza guarda cálculo metrológico

## Qualidade

```mermaid
erDiagram
    Documento ||--o{ DocumentoRevisao : possui
```

Entidades:

- `Documento`: procedimento, método ou instrução controlada.
- `DocumentoRevisao`: histórico de revisões.

## Planejamento

```mermaid
erDiagram
    Cliente ||--o{ PlanejamentoServico : agenda
    ContatoCliente ||--o{ PlanejamentoServico : acompanha
```

Entidade:

- `PlanejamentoServico`: agenda serviço, visita, retirada, técnico, veículo, padrões e observações.

## Cuidados com Dados

- Usar `Decimal` para valores financeiros e metrológicos.
- Campos opcionais em inlines devem aceitar vazio sem quebrar o save.
- Evitar apagar dados vinculados a certificados já emitidos.
- Não alterar prefixos/códigos de certificados sem avaliar rastreabilidade.
- Migrations devem ser incrementais e preservadas.
