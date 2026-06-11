# Decisões Arquiteturais

Este documento registra decisões importantes para manter coerência nas próximas evoluções do projeto.

## 1. Django Admin como Interface Principal

Decisão:

O Django Admin é a interface operacional principal do sistema.

Motivo:

- acelera desenvolvimento
- permite cadastro e manutenção rápida
- combina bem com fluxos internos da empresa

Consequências:

- alterações precisam ser testadas no admin
- inlines são parte crítica do fluxo
- templates do admin podem ser customizados, mas com cuidado

## 2. PDFs por Templates HTML

Decisão:

Propostas, pedidos, certificados e planejamentos usam templates HTML/CSS próprios.

Motivo:

- facilita ajuste visual
- permite impressão via navegador
- mantém controle de identidade visual

Consequências:

- cálculos devem vir prontos da view/model
- templates não devem conter lógica pesada
- sempre testar A4 e salvar como PDF

## 3. Calibrações Especializadas por Tipo

Decisão:

Criar models específicos para calibrações especializadas, como turbidez, colorímetro e pressão.

Motivo:

- cada calibração tem campos, cálculos e certificado próprios
- reduz risco de uma calibração quebrar outra
- mantém rastreabilidade técnica

Consequências:

- repetir padrão: model principal, padrões, pontos, incertezas, admin, PDF e JS
- preservar a calibração geral existente
- futuras calibrações devem seguir essa estrutura

## 4. Cloudflare R2 para Mídia Persistente

Decisão:

Usar Cloudflare R2 para uploads em produção.

Motivo:

- Render Free não preserva arquivos locais
- R2 tem baixo custo para o volume esperado
- é compatível com API S3

Consequências:

- configurar variáveis `AWS_*`
- testar URL pública ou domínio customizado
- avaliar privacidade dos documentos

## 5. PostgreSQL como Banco Principal

Decisão:

Usar PostgreSQL local e no Render.

Motivo:

- compatível com produção
- confiável para dados relacionais
- adequado ao Django

Consequências:

- migrations são obrigatórias
- testar alterações de model antes do deploy
- evitar editar migrations antigas já aplicadas

## 6. Reaproveitar Componentes Existentes

Decisão:

Novas funcionalidades devem reaproveitar padrões já existentes de propostas, pedidos de compra, certificados e planejamento.

Motivo:

- reduz duplicação
- mantém experiência visual consistente
- acelera manutenção

Consequências:

- antes de criar algo novo, procurar padrão similar
- manter nomes e estruturas coerentes
- evitar refatorações grandes sem necessidade

## 7. Campos Opcionais em Inlines Devem Ser Tolerantes

Decisão:

Campos opcionais usados em inlines devem tolerar vazio e, quando necessário, `NULL`.

Motivo:

- o admin pode enviar linhas incompletas
- inlines com campos novos podem quebrar com `IntegrityError`

Consequências:

- usar `blank=True`
- avaliar `null=True` em campos opcionais
- definir `default=""` quando fizer sentido
- testar salvamento com campos vazios

## 8. Documentos Técnicos Devem Priorizar Clareza e Rastreabilidade

Decisão:

Certificados e documentos técnicos devem mostrar apenas informações necessárias ao cliente e à rastreabilidade.

Motivo:

- evita exposição de cálculo interno desnecessário
- mantém documento profissional
- facilita auditoria

Consequências:

- incertezas podem entrar no cálculo sem aparecer em todos os blocos
- critérios e resultados devem ser claros
- padrões e métodos devem ser rastreáveis

## 9. Permissões Devem Ser Tratadas no Menu e no Acesso Real

Decisão:

Usuários restritos devem ter menu filtrado e acesso bloqueado nos módulos não autorizados.

Motivo:

- esconder o menu não basta
- dados internos precisam de controle real

Consequências:

- testar dashboard
- testar admin direto por URL
- revisar grupos/permissões ao criar módulos

## 10. Evolução Incremental

Decisão:

O projeto deve evoluir por pequenas entregas funcionais.

Motivo:

- o sistema já está em uso
- mudanças grandes aumentam risco
- cada módulo tem dependências reais

Consequências:

- preferir migrations pequenas
- validar uma funcionalidade por vez
- manter histórico de decisões nesta pasta
