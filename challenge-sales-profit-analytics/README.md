# Relatório de vendas e lucros com Data Analytics

Relatório Power BI de três páginas baseado na Financial Sample: **Vendas**, **Lucros** e **Análise do período**. O arquivo PBIX fornecido como referência e as instruções na pasta original orientaram a organização das páginas e a combinação de tendências, comparações, segmentadores e matriz; este projeto é uma implementação independente e editável.

## Abrir e reconstruir

Abra `SalesProfitAnalytics\SalesProfitAnalytics.pbip` no Power BI Desktop. Para regenerar as tabelas e o projeto após clonar:

```powershell
python scripts\build_sales_profit_analytics.py
python -m unittest discover -s tests -v
```

O gerador usa `../data/financial_sample.xlsx` e os utilitários de modelo estrela presentes neste repositório. Depois da reconstrução, `DataFolder` aponta para a pasta `data` local deste desafio.

## Páginas e perguntas de negócio

1. **Vendas** — quanto vendemos e em quais segmentos, produtos e meses? Inclui vendas brutas e líquidas, descontos, unidades, tendência mensal, composição e matriz por período.
2. **Lucros** — onde a receita se converte em lucro? Compara lucro e margem por produto/segmento e mostra desconto concedido para contextualizar a rentabilidade.
3. **Análise do período** — como vendas e lucro variam no tempo? Compara vendas líquidas/brutas por mês, lucro por ano/trimestre e evolução percentual mensal.

Cada página possui botões de navegação para as três páginas e segmentadores adequados à análise. O modelo segue a estrela `FactSales` + `DimDate`, `DimProduct`, `DimCountry`, `DimSegment` e `DimDiscountBand`, com relações ativas unidirecionais.

## Métricas e limitações

As medidas incluem vendas líquidas e brutas, lucro, margem, unidades, descontos, taxa de desconto, valor médio por unidade, variações mensal e anual, participação de lucro e valor do período anterior. As definições estão em `DAX/Measures.dax` e no modelo semântico.

A amostra contém 700 linhas, cinco países, cinco segmentos, seis produtos e datas entre 2013 e 2014. O modelo não inventa metas ou orçamento, ausentes da fonte. `NetSales` corresponde à coluna original ` Sales` (com espaço inicial), normalizada pelo gerador.

## Arquivos

- `SalesProfitAnalytics/`: PBIP, relatório PBIR de três páginas e modelo semântico TMDL.
- `DAX/Measures.dax`: medidas DAX copiáveis.
- `PowerQuery/SalesProfitModel.pq`: consultas M para as seis tabelas.
- `data/`: arquivos CSV da fato e dimensões.
- `scripts/build_sales_profit_analytics.py`: reconstrói as tabelas e o PBIP.
- `tests/test_sales_profit_analytics.py`: valida totais, chaves, relações, campos e navegação dos visuais.
