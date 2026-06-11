# Normas e Referências Metrológicas

Esta página registra as regras de negócio ligadas a normas, documentos CGCRE/Inmetro, procedimentos internos, métodos de calibração e documentos usados como base para cálculos.

Importante: esta documentação não deve copiar o texto integral de normas pagas ou protegidas por direitos autorais. O sistema deve registrar a referência, a versão e a regra interna derivada da norma.

## ISO/IEC 17025

### RN-NOR-001 - Referência à ISO/IEC 17025

**Status:** Ativa

Quando uma regra do sistema estiver relacionada à competência de laboratório, rastreabilidade, validade de resultados, controle de documentos, registros técnicos, incerteza de medição ou emissão de certificados, a regra deve indicar a referência à ISO/IEC 17025 aplicável.

**Origem:**  
ISO/IEC 17025, versão vigente adotada pela empresa.

**Impacto no sistema:**  
Qualidade, calibrações, certificados, registros técnicos, controle de documentos e rastreabilidade.

**Critério de aceite:**  
Cada certificado e cálculo crítico deve possuir base documentada, rastreável e revisável.

### RN-NOR-002 - Controle da versão normativa

**Status:** Ativa

Toda norma, documento CGCRE/Inmetro, método interno ou procedimento usado pelo sistema deve possuir:

- Código do documento
- Título
- Revisão ou versão
- Órgão emissor
- Data de emissão, quando disponível
- Data de vigência ou validade, quando aplicável
- Link ou arquivo vinculado na aba Qualidade
- Grandeza ou processo ao qual se aplica

**Critério de aceite:**  
Ao gerar um certificado, o sistema deve permitir identificar qual documento serviu de base para o método, critério ou cálculo.

## Documentos CGCRE/Inmetro Por Grandeza

### RN-CGCRE-001 - Matriz de referência por grandeza

**Status:** Ativa

Cada grandeza calibrada deve possuir uma matriz de referência com os documentos técnicos aplicáveis.

Exemplos de grandezas:

- Pressão
- Temperatura
- Massa
- Volume
- Dimensional
- Óptica
- Química
- Turbidez
- Colorimetria
- pH
- Condutividade

**Impacto no sistema:**  
Cadastros de métodos, certificados, cálculos de incerteza, rastreabilidade e notas técnicas.

### RN-CGCRE-002 - Base de cálculo por grandeza

**Status:** Ativa

Quando houver documento CGCRE/Inmetro, norma técnica, método interno ou planilha validada que defina cálculo de erro, incerteza, conversão de unidade, critério de aceitação ou arredondamento, o sistema deve registrar essa origem.

O cálculo implementado no sistema deve indicar:

- Grandeza
- Fórmula aplicada
- Unidade de entrada
- Unidade de saída
- Conversão utilizada
- Documento de referência
- Revisão do documento
- Data da implementação
- Responsável pela validação

**Critério de aceite:**  
O resultado emitido no certificado deve poder ser auditado a partir dos dados informados, fórmula aplicada e documento de referência.

### RN-CGCRE-003 - Procedimentos e métodos internos

**Status:** Ativa

Procedimentos internos, métodos de trabalho e instruções técnicas devem ser cadastrados na aba Qualidade e vinculados automaticamente à calibração quando aplicável.

Exemplo:

- Método de calibração de colorímetro
- Método de calibração de turbidímetro
- Método de calibração de pressão
- Documento de fatores de conversão
- Planilha validada de cálculo

**Critério de aceite:**  
Ao selecionar o tipo de calibração, o sistema deve sugerir automaticamente o método correspondente quando existir vínculo configurado.

## Certificados

### RN-NOR-003 - Referência normativa no certificado

**Status:** Ativa

O certificado deve exibir apenas as referências necessárias ao cliente e à rastreabilidade do serviço, sem excesso de texto técnico.

Informações técnicas detalhadas podem permanecer registradas no sistema e nos documentos da Qualidade.

**Exemplos de informação que pode aparecer no certificado:**

- Método utilizado
- Código do documento interno
- Revisão do método
- Padrões utilizados
- Número do certificado dos padrões
- Laboratório responsável pela calibração dos padrões
- Condições ambientais
- Critério de aceitação, quando aplicável

### RN-NOR-004 - Revisão de regra quando norma mudar

**Status:** Ativa

Quando uma norma, documento CGCRE/Inmetro ou procedimento interno for revisado, as regras de negócio e os cálculos relacionados devem ser revisados antes de novos certificados serem emitidos com a nova base.

**Critério de aceite:**  
Deve existir histórico entre a versão anterior e a nova versão do método/cálculo.

## Validação de Cálculos

### RN-CALC-001 - Cálculo validado antes de produção

**Status:** Ativa

Todo cálculo metrológico implementado no sistema deve ser validado contra uma planilha, procedimento ou exemplo conhecido antes de ser usado em produção.

**Critério de aceite:**  
Para cada cálculo crítico deve existir pelo menos um conjunto de dados de teste com resultado esperado.

### RN-CALC-002 - Alteração controlada de cálculo

**Status:** Ativa

Alterações em fórmulas de erro, incerteza, EMA, conversão, arredondamento ou critério de aceitação devem ser tratadas como mudança controlada.

**Impacto no sistema:**  
Calibrações, certificados já emitidos, rastreabilidade, auditoria e validação técnica.

### RN-CALC-003 - Dados técnicos protegidos

**Status:** Ativa

Dados técnicos que afetam cálculo, como padrões, incertezas, resolução, fator de abrangência e documentos de referência, devem ter controle de acesso.

Somente usuários autorizados devem alterar esses dados.

## Tabela Para Controle Das Referências

| Grandeza | Documento | Revisão | Origem | Usado em | Arquivo na Qualidade | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Turbidez | A definir | A definir | Procedimento interno/CGCRE/Inmetro | Certificado de Turbidez | Pendente | Pendente |
| Colorimetria | A definir | A definir | Procedimento interno/CGCRE/Inmetro | Certificado de Colorímetro | Pendente | Pendente |
| Pressão | A definir | A definir | Procedimento interno/CGCRE/Inmetro | Certificado de Pressão | Pendente | Pendente |

## Observações

- As referências oficiais devem ser mantidas na aba Qualidade.
- O sistema deve usar a versão vigente definida pela DS Científica.
- Documentos antigos devem permanecer rastreáveis para certificados emitidos no passado.
- A regra interna pode resumir a exigência da norma, mas o texto integral da norma deve permanecer no documento oficial licenciado ou controlado.
