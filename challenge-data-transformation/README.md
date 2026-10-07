# Desafio — Processando e Transformando Dados com Power BI

Entrega do desafio do Módulo 3, baseada na base de exemplo Company indicada pela formação Power BI Analyst.

## Arquivos

- `CompanyTransformation/CompanyTransformation.pbip`: projeto Power BI editável, com o modelo semântico e duas páginas de verificação.
- `PowerQuery/CompanyTransformations.pq`: consultas M reproduzíveis, incluindo a limpeza, os tipos, as mesclas, o agrupamento e as verificações.
- `data/raw/`: seis arquivos CSV extraídos dos `INSERT`s da amostra.
- `data/processed/`: resultados tabulares das transformações para inspeção e comparação.
- `source/`: scripts SQL de referência e `company_seed.sql`, uma versão de carga corrigida para o schema criado pelo script original.
- `scripts/build_dataset.py`: recria os CSVs e os resultados processados sem dependências externas.
- `scripts/build_powerbi_project.py`: recria o projeto PBIP com o caminho local para os CSVs.
- `tests/test_dataset.py`: testes dos totais, mesclas, chaves e anomalias identificadas.

O relatório contém **Qualidade dos dados** (checagens e funcionários enriquecidos) e **Departamentos e projetos** (colaboradores por gerente, horas por projeto e combinações departamento-local).

## Abrir e atualizar o Power BI

Na pasta `challenge-data-transformation`, execute:

```powershell
python scripts\build_dataset.py
python scripts\build_powerbi_project.py
python -m unittest discover -s tests
```

Em seguida, abra `CompanyTransformation\CompanyTransformation.pbip` no Power BI Desktop e atualize o modelo. O gerador define o parâmetro `DataFolder` para a pasta `data\raw` deste clone. Não é necessário configurar Azure para reproduzir o relatório localmente.

O projeto PBIP está versionado como arquivos de texto. Para converter em `.pbix`, abra o `.pbip` no Power BI Desktop e use **Arquivo → Salvar como**.

## Tratamento aplicado

1. Cabeçalhos e tipos explícitos para as seis tabelas de origem; salário usa `Decimal Number` no Power Query e `decimal` no modelo.
2. Endereço de funcionário separado em número, rua, cidade e estado. O registro de Ramesh contém cinco segmentos; `Fire-Oak` é preservado como o nome composto da rua (`Fire Oak`) para produzir os mesmos quatro campos sem sinalizar uma anomalia falsa.
3. `employee` mesclada com `departament` usando **Left Outer**, preservando todos os funcionários; mescla autorreferenciada associa cada funcionário ao gerente.
4. Nome e sobrenome combinados em `EmployeeName`.
5. `dept_locations` mesclada com `departament` para produzir uma dimensão de combinações departamento-local, com chave composta.
6. Horas de `works_on` agregadas por projeto; funcionários agrupados pelo identificador do supervisor.
7. Colunas técnicas e de origem que não são necessárias ao relatório não são expostas nas tabelas finais.

**Mesclar** (Merge) combina colunas de tabelas relacionadas por uma chave. É apropriado para associar cada linha de localidade a seu departamento. **Acrescentar** (Append) empilha linhas de tabelas com estruturas semelhantes; não associa o departamento ao local e, portanto, não cria a dimensão departamento-local solicitada.

## Resultado das verificações

- 8 funcionários, 3 departamentos, 5 combinações departamento-local, 6 projetos e 16 alocações de horas.
- Nenhum departamento sem gerente; todos os funcionários encontram seu departamento e todas as referências não nulas a gerente são válidas.
- Um funcionário sem supervisor: James E. Borg, o CEO no conjunto de exemplo. É a raiz esperada da hierarquia, não um dado para excluir.
- Na tabela agregada por gerente, essa linha recebe a chave técnica `__NO_SUPERVISOR__`. O marcador evita uma chave nula no modelo semântico e mantém o CEO identificável como funcionário de nível superior.
- Uma alocação de projeto com 0 horas. O registro é mantido e sinalizado para revisão, sem remoção silenciosa.
- As horas somam 275,0 e não há alocações com horas negativas.

## Integração Azure/MySQL

O roteiro para criar o serviço Azure é opcional e não foi executado: requer uma assinatura e pode gerar custos. `source/script_bd_company.sql` cria o schema `azure_company`; o arquivo original de inserções seleciona `company_constraints`. Para evitar essa divergência, use `source/company_seed.sql`, que aponta para `azure_company`. Não grave senhas, chaves ou credenciais do Azure no repositório.

Os passos oficiais estão nos links da [descrição dos desafios](../README.md#referências-oficiais). A base e o roteiro têm como referência o repositório [power_bi_analyst — Desafio de Projeto, Módulo 3](https://github.com/julianazanelatto/power_bi_analyst/tree/main/M%C3%B3dulo%203/Desafio%20de%20Projeto).
