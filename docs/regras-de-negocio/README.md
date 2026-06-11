# Regras de Negócio

Esta pasta concentra as regras de negócio do sistema DS Científica/AXION.

O objetivo é deixar claro o comportamento esperado do sistema antes da implementação técnica, facilitando manutenção, validação com usuários e evolução das telas.

## Organização

- [Clientes, Comercial e Financeiro](./clientes-comercial-financeiro.md)
- [Calibrações e Certificados](./calibracoes-certificados.md)
- [Qualidade e Planejamento](./qualidade-planejamento.md)
- [Normas e Referências Metrológicas](./normas-e-referencias.md)

## Convenções

- Cada regra deve ter um identificador curto, por exemplo `RN-CAL-001`.
- Regras obrigatórias devem usar linguagem direta: "deve", "não deve", "somente".
- Regras em análise devem ficar marcadas como `Pendente`.
- Quando a regra depender de cálculo, fórmula, norma ou documento, registrar a origem.

## Modelo Para Novas Regras

```md
### RN-MOD-000 - Título da regra

**Status:** Ativa | Pendente | Revisar

**Descrição:**  
Texto objetivo da regra.

**Origem:**  
Solicitação do usuário, norma, procedimento interno, contrato, fabricante etc.

**Impacto no sistema:**  
Tela, campo, cálculo, relatório, PDF, permissão ou integração afetada.

**Critério de aceite:**  
Como validar que a regra está funcionando corretamente.
```
