# Clientes, Comercial e Financeiro

## Clientes

### RN-CLI-001 - Cadastro de cliente por CNPJ

**Status:** Ativa

Ao informar um CNPJ válido, o sistema deve buscar automaticamente os dados disponíveis da empresa e preencher o cadastro do cliente.

Campos desejados:

- Razão social
- Nome fantasia
- CNPJ
- Inscrição estadual, quando disponível
- Endereço
- Cidade
- Estado
- Telefone, quando disponível
- E-mail, quando disponível

Quando algum dado não estiver disponível na consulta externa, o campo deve permanecer editável para preenchimento manual.

### RN-CLI-002 - Contatos do cliente

**Status:** Ativa

O cliente pode possuir contatos vinculados. Quando um contato for selecionado em uma tela operacional, os dados do contato devem ser usados automaticamente quando fizer sentido, evitando digitação duplicada.

## Comercial

### RN-COM-001 - Proposta comercial

**Status:** Ativa

A proposta comercial deve permitir cadastrar cliente, responsável, itens, valores, condições comerciais, observações e anexos.

O PDF da proposta deve ter aparência profissional, com cabeçalho, dados do cliente, tabela de itens, totais, condições comerciais e rodapé organizado.

### RN-COM-002 - Código da proposta

**Status:** Ativa

A proposta deve possuir código automático e identificável, evitando duplicidade e facilitando rastreabilidade.

## Financeiro

### RN-FIN-001 - Contas a receber vinculada à proposta

**Status:** Ativa

Quando uma proposta aprovada gerar cobrança, o sistema deve permitir criar conta a receber vinculada à proposta e puxar automaticamente os valores aplicáveis.

### RN-FIN-002 - Pedido de compra

**Status:** Ativa

O pedido de compra deve permitir cadastrar fornecedor, comprador, itens, valores, frete, descontos, outros custos e observações.

O pedido deve gerar PDF profissional usando identidade visual semelhante à proposta comercial.

### RN-FIN-003 - Categorias financeiras

**Status:** Ativa

Categorias financeiras devem possuir código automático para manter padronização e evitar cadastro duplicado com identificadores inconsistentes.
