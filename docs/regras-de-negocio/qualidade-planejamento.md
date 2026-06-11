# Qualidade e Planejamento

## Qualidade

### RN-QUA-001 - Documentos da qualidade

**Status:** Ativa

A aba Qualidade deve armazenar documentos controlados, procedimentos, métodos e anexos usados como referência nas calibrações e demais processos.

Quando um método de calibração estiver vinculado a um certificado, o sistema deve permitir rastrear o documento correspondente.

### RN-QUA-002 - Arquivos permanentes

**Status:** Ativa

Arquivos enviados ao sistema devem ser armazenados de forma permanente fora do disco efêmero do Render.

O armazenamento definido para produção é Cloudflare R2.

## Planejamento

### RN-PLAN-001 - Planejamento de serviço

**Status:** Ativa

O sistema deve permitir cadastrar planejamentos de serviço com informações de data, cliente, contato, local, proposta, ordem de serviço, técnicos, equipamentos, padrões, veículo e observações.

### RN-PLAN-002 - Calendário de planejamento

**Status:** Ativa

O planejamento deve possuir visualização em calendário para facilitar a organização de visitas, serviços agendados, retirada de equipamentos e entregas.

### RN-PLAN-003 - Impressão do planejamento

**Status:** Ativa

O planejamento deve possuir impressão limpa, com layout profissional e campo para assinatura do responsável pelo cliente, contendo data e hora quando aplicável.

### RN-PLAN-004 - Padrões obrigatórios por tipo de serviço

**Status:** Ativa

Os padrões devem ser obrigatórios somente quando o tipo de planejamento exigir serviço técnico/calibração.

Quando não forem aplicáveis, o sistema deve exibir `Não aplicável` ou `-----`.

### RN-PLAN-005 - Dados do contato

**Status:** Ativa

Ao selecionar um contato do cliente, o planejamento deve usar automaticamente os dados desse contato, como nome, cargo, telefone e e-mail, evitando campos duplicados.

### RN-PLAN-006 - Equipe técnica

**Status:** Ativa

O planejamento deve permitir selecionar um ou mais técnicos responsáveis pelo serviço.

Na impressão, cada técnico deve aparecer uma única vez.

## Permissões

### RN-PERM-001 - Perfis de acesso

**Status:** Ativa

O sistema deve permitir criar perfis de acesso com permissão limitada a áreas específicas, por exemplo:

- Comercial
- Financeiro
- Calibração
- Qualidade
- Planejamento
- Administração

Usuários com perfil restrito não devem visualizar ou acessar módulos fora de sua permissão.
