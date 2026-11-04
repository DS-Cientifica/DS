# Etiquetas de calibração com QR Code

## Objetivo

Permitir a impressão antecipada de etiquetas com endereços permanentes sem
publicar dados de calibração antes da aprovação do certificado.

## Isolamento do acesso público

O domínio público deve ser exclusivo, por exemplo
`certificados.exemplo.com.br`. Configure-o em `ALLOWED_HOSTS` e em
`PUBLIC_CERTIFICATE_HOSTS`.

Quando a requisição usa esse host, o middleware aceita somente:

- `/etiquetas/<token>/`;
- `/verificar/<uuid>/`;
- `/verificar/<uuid>/arquivo/`.

Qualquer tentativa de abrir `/admin/`, `/clientes/`, `/dashboard/` ou outra
rota retorna HTTP 404 antes do processamento de sessão e autenticação.

Como defesa adicional, configure no Cloudflare regras que permitam apenas os
prefixos acima e aplique limitação de requisições. O painel administrativo deve
continuar em outro host.

## Geração controlada do lote

Cada etiqueta recebe o mesmo formato adotado para os certificados novos: seis
caracteres aleatórios, contendo exatamente três letras e três números. O código
fica reservado e não pode ser emitido para outro objeto.

Primeiro execute a simulação:

```powershell
python manage.py gerar_lote_etiquetas_qr --lote PILOTO-2026-01 --quantidade 5
```

Depois de conferir a faixa de códigos, confirme:

```powershell
python manage.py gerar_lote_etiquetas_qr --lote PILOTO-2026-01 --quantidade 5 --apply
```

O comando é idempotente por lote: se o lote já existir, nenhuma etiqueta é
acrescentada.

As etiquetas são criadas como `Aguardando impressão` e ainda não podem ser
consumidas por calibrações. Depois de receber e conferir fisicamente a prova,
simule e confirme a ativação:

```powershell
python manage.py ativar_lote_etiquetas_qr --lote PILOTO-2026-01
python manage.py ativar_lote_etiquetas_qr --lote PILOTO-2026-01 --apply
```

## Fluxo

1. A etiqueta nasce como `Disponível` e não expõe cliente, instrumento ou certificado.
2. Ao criar uma calibração, o AXION consome a próxima etiqueta disponível e
   atribui o mesmo código ao número do certificado.
3. A etiqueta passa ao estado `Reservada para calibração`, sem publicar dados.
4. Quando o certificado assinado é publicado, a etiqueta passa a `Vinculada` e
   o sistema registra responsável e data/hora.
5. A consulta da etiqueta passa a redirecionar somente para a consulta pública do certificado.
6. A etiqueta não pode ser excluída nem reutilizada pelo Admin.

## Impressão

No Admin, filtre o lote, selecione as etiquetas e execute a ação
`Imprimir QR Codes das etiquetas selecionadas`. Gere primeiro uma prova de
cinco unidades no material e dimensões reais antes de autorizar o lote de 200.

O endereço usado na impressão deve ser o domínio definitivo. Não imprima QR
Codes com `127.0.0.1`, `localhost` ou endereço temporário do Render.
