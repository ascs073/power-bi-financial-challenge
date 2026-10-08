# Dashboard gerencial para tomada de decisões

Relatório de gestão feito com a Financial Sample da pasta indicada. O desenho segue os princípios de posicionamento, contraste, proporção visual, segmentação e navegação abordados no arquivo de instruções local `8c8b9d8e-2d05-4d68-ad5b-631bed568839.docx`, com a amostra financeira e como referência estrutural o PBIX `38ae8dcf-114a-4db3-836c-24d9beadb821.pbix`. Os arquivos-fonte de exemplo não são necessários para abrir este projeto; a amostra financeira está versionada no repositório.

## Abrir e reconstruir

Abra `ManagerialDashboard\ManagerialDashboard.pbip` no Power BI Desktop. O relatório possui três páginas:

1. **Resumo executivo** — vendas, lucro, margem, unidades, evolução mensal, comparação anual e segmentadores de ano, país e segmento.
2. **Rentabilidade** — lucro e margem por produto e segmento, desconto aplicado e uma matriz de desempenho dos produtos.
3. **Mercados e portfólio** — vendas e lucro por país, resultado por produto e faixa de desconto, com segmentadores para análise.

Cada página tem um menu superior de botões para navegar entre as três seções. Os separadores preservam o contexto da análise dentro de cada página.

Para recriar os CSVs e o PBIP após clonar o repositório:

```powershell
python scripts\build_managerial_dashboard.py
python -m unittest discover -s tests -v
```

O gerador usa a amostra `../data/financial_sample.xlsx`, cria dimensões e fato com o gerador compartilhado do desafio de modelo estrela e grava `DataFolder` com o caminho local deste clone. Sem Azure ou dependências Python de terceiros.

## Modelo e medidas de decisão

O modelo estrela mantém `FactSales` no grão de uma linha da amostra e relações ativas, unidirecionais, um-para-muitos com `DimDate`, `DimProduct`, `DimCountry`, `DimSegment` e `DimDiscountBand`.

As medidas incluem vendas líquidas, vendas brutas, lucro, margem, unidades, descontos e percentual de desconto, além de variações mensal e anual. Não há metas ou orçamento na amostra; por isso o relatório não inventa metas nem sinais de atingimento.

As medidas estão em `DAX/Measures.dax` e no modelo semântico TMDL. O projeto Power BI mantém as páginas editáveis em PBIR.

## Referência dos dados

A Financial Sample tem 700 linhas, cinco países, cinco segmentos, seis produtos e datas entre 2013 e 2014. A coluna original de vendas inclui espaço inicial no nome (` Sales`); o gerador normaliza esse cabeçalho para `NetSales`. Valores e períodos são apresentados como estão na amostra.

Os arquivos do desafio ficam independentes em `data/`, `DAX/`, `scripts/` e `ManagerialDashboard/`. Nenhum dos relatórios anteriores é sobrescrito.
