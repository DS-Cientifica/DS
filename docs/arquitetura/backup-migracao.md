# Backup Local, Homologação Render e Migração Futura

## Objetivo

Definir uma estratégia de transição segura para o AXION:

- manter a base oficial local enquanto o software amadurece
- publicar o sistema no Render apenas para homologação
- reduzir risco de perda de dados
- preparar migração futura com rastreabilidade e validação

## Estratégia recomendada

### Fase 1. Produção operacional local

Base oficial:

- PostgreSQL local
- arquivos locais ou Cloudflare R2, conforme configuração

Objetivo:

- preservar operação atual
- não depender de banco gratuito expirável no Render

### Fase 2. Homologação em nuvem

Base de homologação:

- novo banco vazio no Render
- sem dados críticos do laboratório

Objetivo:

- validar deploy
- validar fluxo do admin
- validar PDFs
- validar permissões
- validar integrações de storage

### Fase 3. Produção em rede/cloud

Quando o sistema estiver robusto:

- congelar alterações temporariamente
- executar backup completo do banco local
- restaurar em banco gerenciado pago
- validar consistência
- liberar uso em rede

## Riscos de usar Render Free como base oficial

- banco Postgres Free expira após 30 dias
- instância expirada fica suspensa
- risco operacional incompatível com histórico metrológico
- filesystem do web service é efêmero

Para base oficial, usar:

- PostgreSQL pago no Render ou outro provedor gerenciado
- política de backup
- restauração testada

## Backup do PostgreSQL local

Script incluído no projeto:

- [backup_postgres_local.ps1](C:/Users/User/Desktop/DS_CIENTIFICA_BACKUP_20260525_080751/07_PROJETOS/Projetos_Ativos/SOFTWARE/axion/projeto_ds_cientifica-rev03-170526/scripts/backup_postgres_local.ps1)

### O que o script faz

- localiza `pg_dump.exe`
- solicita senha se `PGPASSWORD` não estiver definida
- gera backup com timestamp
- grava log do processo
- gera hash SHA256
- remove backups antigos conforme retenção

### Formato padrão

Por padrão o script usa:

- `pg_dump --format=custom`

Vantagens:

- restauração mais robusta com `pg_restore`
- melhor para migração entre ambientes

### Execução manual

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\scripts\backup_postgres_local.ps1
```

### Execução com parâmetros

```powershell
.\scripts\backup_postgres_local.ps1 `
  -DatabaseName "axion_db" `
  -DatabaseUser "postgres" `
  -DatabaseHost "localhost" `
  -DatabasePort 5432 `
  -BackupRoot "D:\Backups\AXION\PostgreSQL" `
  -RetentionDays 30
```

### Uso com SQL plano

```powershell
.\scripts\backup_postgres_local.ps1 -PlainSql
```

### Agendamento no Windows

Criar tarefa no Agendador:

1. Abrir `Task Scheduler`
2. Criar nova tarefa
3. Executar diariamente fora do horário operacional
4. Programa:

```text
powershell.exe
```

5. Argumentos:

```text
-ExecutionPolicy Bypass -File "C:\CAMINHO\DO\PROJETO\scripts\backup_postgres_local.ps1"
```

6. Definir diretório seguro de backup fora da pasta do projeto
7. Replicar esse diretório para OneDrive, Google Drive, NAS ou bucket

## Homologação no Render

### Objetivo

Subir o software na nuvem sem risco de misturar dados reais com ambiente de testes.

### Regras

- usar banco novo e vazio
- não copiar base oficial automaticamente
- usar usuários de teste
- não considerar esse ambiente como repositório oficial de dados

### Configuração mínima

No web service:

- `DJANGO_SECRET_KEY`
- `DEBUG=False`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL` apontando para banco novo

Arquivo de referência para variáveis:

- [.env.render.example](C:/Users/User/Desktop/DS_CIENTIFICA_BACKUP_20260525_080751/07_PROJETOS/Projetos_Ativos/SOFTWARE/axion/projeto_ds_cientifica-rev03-170526/.env.render.example)

Para uploads:

- preferir Cloudflare R2
- evitar depender de disco local do Render

### Critérios de aceite da homologação

- login do admin
- cadastro de cliente
- cadastro de instrumento
- geração de proposta PDF
- geração de certificado PDF
- upload e leitura de arquivos
- teste de permissões de usuário restrito

## Migração futura para produção em nuvem

### Pré-requisitos

- banco pago e estável
- storage de arquivos definido
- backup local validado
- janela de migração aprovada

### Passo a passo recomendado

1. Congelar cadastros temporariamente no ambiente local
2. Executar backup completo do banco local
3. Exportar arquivos críticos de `media/`, se ainda existirem localmente
4. Criar banco de produção em nuvem
5. Restaurar backup no banco novo
6. Configurar `DATABASE_URL`
7. Configurar storage de arquivos
8. Rodar migrations pendentes
9. Validar integridade funcional
10. Liberar acesso aos usuários

### Validação pós-restauração

- quantidade de clientes
- quantidade de instrumentos
- quantidade de certificados
- quantidade de propostas
- amostragem de PDFs antigos
- amostragem de anexos
- conferência de usuários e permissões

## Comandos úteis de migração

### Backup

```powershell
.\scripts\backup_postgres_local.ps1 -DatabaseName "axion_db"
```

### Restore com pg_restore

```powershell
pg_restore `
  --clean `
  --if-exists `
  --no-owner `
  --host=HOST_DESTINO `
  --port=5432 `
  --username=USUARIO_DESTINO `
  --dbname=BANCO_DESTINO `
  "C:\Backups\AXION\PostgreSQL\axion_db_YYYYMMDD_HHMMSS.backup"
```

### Checklist de restore validado

Antes de apontar usuários para a nuvem, confirmar:

1. banco de destino criado e acessível
2. restore concluído sem erro crítico
3. `python manage.py migrate` executado com sucesso
4. `python manage.py check` executado com sucesso
5. login administrativo validado
6. contagem mínima conferida:
   - clientes
   - instrumentos
   - propostas
   - certificados
7. amostragem de anexos e PDFs antigos aberta sem erro
8. geração de nova proposta PDF validada
9. geração de novo certificado PDF validada
10. backup do banco pós-restore armazenado

## Recomendação final

No estágio atual, a melhor prática é:

- produção local com backup diário externo
- homologação em nuvem com banco vazio
- produção em nuvem apenas após validação operacional e restauração testada
