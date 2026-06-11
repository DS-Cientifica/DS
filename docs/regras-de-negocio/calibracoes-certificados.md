# Calibrações e Certificados

## Regras Gerais

### RN-CAL-000 - Base normativa e técnica

**Status:** Ativa

Toda calibração deve possuir rastreabilidade técnica para normas, documentos CGCRE/Inmetro, procedimentos internos, métodos de calibração ou planilhas validadas que sustentem os cálculos e o certificado emitido.

Quando houver cálculo de erro, incerteza, conversão de unidade, critério de aceitação ou resultado final automático, o sistema deve registrar a origem técnica usada.

Ver também: [Normas e Referências Metrológicas](./normas-e-referencias.md).

### RN-CAL-001 - Certificados especializados

**Status:** Ativa

As calibrações especializadas devem possuir telas próprias quando os cálculos, campos e certificado exigirem comportamento específico.

Exemplos atuais:

- Calibração de Turbidez
- Calibração de Colorímetro
- Calibração de Pressão

### RN-CAL-002 - Certificado em PDF

**Status:** Ativa

Cada calibração especializada deve gerar um certificado em PDF com identidade visual profissional, contendo no mínimo:

- Logo da empresa
- Nome DS Científica
- Dados de contato da empresa
- Título do certificado
- Código do documento
- Número do certificado
- Dados do cliente
- Dados do equipamento calibrado
- Condições ambientais
- Padrões utilizados
- Método utilizado
- Resultados da calibração
- Notas
- Observações
- Campo de assinatura

### RN-CAL-003 - Número do certificado

**Status:** Ativa

O número do certificado deve ser gerado de forma rastreável, considerando o tipo de calibração e dados do cliente/equipamento quando aplicável.

Exemplos:

- `TURB-456-BOSCH-01`
- `COLOR-456-BOSCH-01`
- `PRE-456-BOSCH-01`

### RN-CAL-004 - Código do documento

**Status:** Ativa

O certificado deve exibir o código do documento interno, por exemplo:

- `CCDS-0001 Rev.00` para Turbidez
- `CCDS-0002 Rev.00` para Colorímetro

Para pressão, o código deve seguir o mesmo padrão definido para os certificados especializados.

## Padrões e Incertezas

### RN-CAL-005 - Cadastro único de padrões

**Status:** Ativa

Os padrões devem ser cadastrados uma única vez e reutilizados nas calibrações. Durante a calibração, o usuário deve apenas selecionar os padrões aplicáveis.

### RN-CAL-006 - Dados técnicos usados apenas no cálculo

**Status:** Ativa

Dados como resolução e incerteza do padrão podem ser usados nos cálculos, mas não devem aparecer no certificado quando não forem necessários para o cliente.

### RN-CAL-007 - Campos obrigatórios

**Status:** Ativa

Quando informações obrigatórias estiverem ausentes, o certificado deve destacar o alerta visualmente para evitar emissão incompleta.

## Resultado e Critério de Aceitação

### RN-CAL-008 - Origem do critério

**Status:** Ativa

Quando houver critério de aceitação, o sistema deve permitir informar a origem do critério, por exemplo:

- Cliente
- Fabricante
- Norma
- Outro

### RN-CAL-009 - Resultado final automático

**Status:** Ativa

O resultado final deve ser gerado automaticamente a partir dos pontos calibrados e do critério de aceitação definido.

Se qualquer ponto estiver fora do critério, o resultado final deve indicar que o equipamento está inadequado ou não conforme.

Se todos os pontos atenderem ao critério, o resultado final deve indicar que o equipamento está adequado ou conforme.

## Turbidez

### RN-TURB-001 - Certificado de turbidez

**Status:** Ativa

O certificado de turbidez deve usar a unidade NTU e manter layout semelhante ao modelo definido para DS Científica.

## Colorímetro

### RN-COLOR-001 - Tipos de colorímetro

**Status:** Ativa

A calibração de colorímetro deve permitir selecionar o tipo de aplicação, como:

- Cloro
- Flúor
- Cor
- Fotocolorímetro
- Outro

As unidades aceitas incluem `mg/L` e `UA` para absorbância.

### RN-COLOR-002 - Método de calibração

**Status:** Ativa

O método de calibração deve ser preenchido automaticamente conforme o tipo de colorímetro selecionado, quando houver documento correspondente cadastrado na Qualidade.

## Pressão

### RN-PRE-001 - Tipos de instrumento de pressão

**Status:** Ativa

A calibração de pressão deve permitir selecionar o tipo de instrumento, por exemplo:

- Manômetro
- Transmissor de pressão
- Indicador de pressão
- Indicador e transmissor de pressão
- Outro

### RN-PRE-002 - Resultado por ida e retorno

**Status:** Ativa

O certificado de pressão deve apresentar os resultados considerando medições crescentes e decrescentes, quando aplicável.

### RN-PRE-003 - Grau de liberdade e fator de abrangência

**Status:** Ativa

Quando tecnicamente aplicável, o grau de liberdade pode ser tratado como tendendo ao infinito e o fator de abrangência pode ser fixado conforme critério adotado.

### RN-PRE-004 - Local de calibração

**Status:** Ativa

Para calibração de pressão, o local padrão deve usar a classificação de Pressão, não Óptico.
