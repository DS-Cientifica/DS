# Arquitetura do Projeto AXION

Esta pasta concentra a documentação arquitetural do sistema AXION / DS Científica.

O objetivo é deixar claro como o sistema está organizado, quais módulos existem, como os dados se relacionam, como o projeto roda em desenvolvimento e produção, e quais decisões técnicas precisam ser preservadas por quem fizer manutenção no futuro.

## Documentos

- [Visão geral](visao-geral.md)
- [Módulos do sistema](modulos.md)
- [Modelo de dados](modelo-de-dados.md)
- [Deploy, storage e infraestrutura](deploy-storage.md)
- [Backup local, homologação Render e migração futura](backup-migracao.md)
- [Decisões arquiteturais](decisoes-arquiteturais.md)

## Resumo Rápido

O AXION é um sistema Django 6 com foco em:

- gestão de clientes
- propostas comerciais
- financeiro
- pedidos de compra
- gestão metrológica
- certificados de calibração
- documentos da qualidade
- planejamento de serviços

O sistema usa PostgreSQL, Django Admin customizado, templates HTML para PDFs e armazenamento de arquivos local ou Cloudflare R2, conforme configuração de ambiente.

## Princípios de Manutenção

- Preservar fluxos existentes antes de criar novas estruturas.
- Reaproveitar padrões já usados em propostas, pedidos e certificados.
- Tratar PDFs como documentos profissionais, não como simples páginas do admin.
- Rodar migrations sempre que models forem alterados.
- Validar cadastros pelo Django Admin, pois ele é a principal interface operacional.
- Considerar as limitações do Render Free ao lidar com arquivos.
