# Mapeamento dos formulários de calibração

Data do levantamento: 2026-08-15.

## Escopo e regra de cadastro

- Origem: `C:\Users\User\Desktop\fORMULARIO DE CALIBRAÇÃO`.
- Quantidade: 34 arquivos, sendo 31 conteúdos SHA-256 distintos.
- Destino: `qualidade.Documento`.
- Estado inicial: `Em elaboração` e revisão `RASCUNHO`.
- Código, datas de emissão/revisão, responsável e aprovação permanecem em branco até análise crítica e aprovação formal.
- Os originais são preservados; a senha informada é usada apenas para leitura e não é cadastrada no sistema.

## Classificação

- 29 formulários: planilhas de calibração/ensaio e o protocolo de esterilização.
- 2 procedimentos externos: ensaio de desempenho e incerteza do processo de esterilização.
- 2 documentos de apoio: dados de equipamentos ópticos e filtro óptico.
- 1 formulário legado XLS: turbidímetro.

Os dois procedimentos e o protocolo em PDF pertencem à Evagon e trazem aprovações de 2021. Essas aprovações são apenas metadados da fonte e não representam aprovação pela DS Científica.

## Leitura e proteção

- PDFs: 30, 11 e 4 páginas; abertos e inspecionados visualmente.
- ODS: 26 arquivos; 21 dos 22 arquivos ODS protegidos tiveram a senha validada e suas abas lidas.
- `FM-7.2.1-xxxRV00 Calibração de Balança_.ods` usa criptografia de pacote completo e será preservado sem alteração; a leitura interna automatizada ficou pendente.
- XLSX/XLS: assinaturas e estruturas de arquivo validadas antes da importação.

## Duplicidades binárias que exigem decisão antes da aprovação

1. Os dois arquivos de calibração de meio térmico com e sem hífen têm o mesmo SHA-256.
2. Os dois arquivos de calibração externa de temperatura têm o mesmo SHA-256.
3. `Calibração de Autoclave` e `Qualificação de Autoclave` têm o mesmo SHA-256, apesar dos títulos tecnicamente distintos.

Os 34 nomes serão cadastrados porque foram fornecidos explicitamente, mas as duplicidades ficarão sinalizadas nas observações e não devem ser aprovadas sem reconciliação.

## Pendências normativas antes de tornar vigente

- atribuir código documental único e revisão controlada;
- definir elaborador, revisor e aprovador com segregação de funções;
- registrar datas efetivas de emissão e aprovação;
- verificar referências normativas atuais e documentos Cgcre aplicáveis;
- validar fórmulas, proteção de células, unidades, arredondamento e orçamento de incerteza;
- confirmar rastreabilidade dos padrões, critérios de aceitação e regra de decisão;
- retirar marcas, aprovações e referências externas não autorizadas;
- eliminar ou justificar as duplicidades binárias;
- realizar validação de método/planilha e registrar evidências antes da liberação.
