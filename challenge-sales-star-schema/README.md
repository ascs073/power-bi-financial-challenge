# Dashboard de vendas — modelo estrela no Power BI

Entrega do desafio de modelagem dimensional e análise de vendas. Usa a Financial Sample já versionada em `../data/financial_sample.xlsx`; os relatórios financeiros anteriores não são alterados.

## Abrir o relatório

Abra `SalesStarSchema\SalesStarSchema.pbip` no Power BI Desktop. O relatório editável tem uma página de painel com cartões de indicadores, tendência mensal, vendas por produto e segmento, lucro por país e segmentadores de ano e segmento.

O projeto usa arquivos PBIP/TMDL e CSVs, não requer Azure nem pacotes Python externos. Para reconstruir os dados e o projeto a partir da planilha:

```powershell
python scripts\build_star_schema.py
python -m unittest discover -s tests -v
```

O script grava um novo `DataFolder` local no modelo. Depois de clonar o repositório em outro computador, execute-o novamente antes de abrir o PBIP.

## Modelo dimensional

O grão de `FactSales` é uma linha da Financial Sample: uma combinação de período, país, produto, segmento e faixa de desconto. Como a amostra não tem identificador de pedido, `FactRowID` é apenas uma chave técnica de linha, não um número de transação comercial.

```text
DimDate       1 ─── * FactSales * ─── 1 DimProduct
DimCountry    1 ─── * FactSales * ─── 1 DimSegment
DimDiscountBand 1 ─ * FactSales
```

As relações são ativas, um-para-muitos e filtram em uma direção, das dimensões para a fato. As dimensões têm chaves substitutas inteiras; as métricas permanecem na fato. A `DimDate` é um calendário contínuo de datas entre o menor e o maior dia da amostra, com campos de ano, trimestre e mês ordenável.

| Tabela | Conteúdo |
| --- | --- |
| `FactSales` | Unidades, preços, vendas brutas e líquidas, descontos, custo e lucro |
| `DimDate` | Data, ano, trimestre, mês e chave de ordenação ano-mês |
| `DimProduct` | Produto e preço de fabricação de referência |
| `DimCountry` | País |
| `DimSegment` | Segmento de cliente |
| `DimDiscountBand` | Faixa de desconto |

Medidas explícitas do modelo: Total Sales, Gross Sales, Total Discounts, Total Profit, Units Sold e Profit Margin %.

## Artefatos

- `SalesStarSchema\`: projeto Power BI PBIP, modelo semântico TMDL e relatório PBIR.
- `data\`: CSVs das tabelas fato e dimensões carregados pelo modelo.
- `PowerQuery\StarSchema.pq`: definição de consultas M reproduzíveis.
- `scripts\build_star_schema.py`: extrai a Financial Sample, cria as tabelas e regenera o PBIP.
- `tests\test_star_schema.py`: verifica grão, chaves, relações, totais e visuais.

## Limites da entrega

A planilha de referência não contém clientes individuais, pedidos, lojas nem regiões geográficas além de país. O modelo não inventa essas entidades. Publicar no Power BI Service requer login e workspace da conta do usuário.
