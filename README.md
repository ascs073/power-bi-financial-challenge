# Desafio Power BI — Financial Sample

Relatório do desafio de Power BI Analyst, com as duas páginas de referência preservadas e a terceira página criada para analisar vendas e lucro por país e segmento.

## Entrega

- `Financial_Sample.pbix`: relatório editável do Power BI Desktop.
- `data/financial_sample.xlsx`: amostra financeira usada no desafio.

Abra `Financial_Sample.pbix` no Power BI Desktop. A página **Análise geográfica** contém:

1. **Vendas e unidades vendidas por país** — mapa com vendas no tamanho das bolhas e unidades vendidas nas dicas de ferramenta.
2. **Lucro total por país** — mapa preenchido, colorido pelo lucro total.
3. **Lucro por segmento** — gráfico de pizza com valores e percentuais.

Os títulos e as dicas de ferramenta identificam as métricas diretamente. O relatório usa os campos `Country`, ` Sales`, `Units Sold`, `Profit` e `Segment` da tabela financeira. O nome da coluna de vendas no arquivo de origem contém um espaço inicial (` Sales`).

## Publicar e compartilhar

Para publicar, abra o PBIX no Power BI Desktop, escolha **Página Inicial → Publicar** e selecione o workspace desejado. A publicação requer uma conta do Power BI. Para exportar um suplemento do PowerPoint, use **Arquivo → Exportar → PowerPoint** após publicar ou abrir o relatório no serviço do Power BI.

O arquivo PBIX é a entrega editável caso a exportação para PowerPoint não esteja disponível.

## Origem

O relatório e a amostra financeira têm como referência o repositório [power_bi_analyst](https://github.com/julianazanelatto/power_bi_analyst), em especial o material do desafio do Módulo 2. A terceira página foi preenchida para atender aos visuais solicitados.
