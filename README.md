# Desafio Power BI — Financial Sample

Projetos dos desafios de Power BI Analyst baseados na amostra financeira.

## Entrega

- `Financial_Sample_Interactive_Report.pbix`: relatório editável de duas páginas com navegação e visuais interativos.
- `Financial_Sample.pbix`: relatório do desafio anterior, com as duas páginas de referência e a análise geográfica.
- `data/financial_sample.xlsx`: amostra financeira usada no desafio.

### Relatório interativo

Abra `Financial_Sample_Interactive_Report.pbix` no Power BI Desktop. O relatório contém:

1. **Visão geral de vendas** — indicadores e visuais de vendas por segmento, produto e país; segmentador de data; botões de favoritos para alternar entre gráfico de barras e pizza e entre mapa e treemap.
2. **Análise de lucro** — árvore de decomposição, variação trimestral, lucro por produto e segmento; segmentador de ano e botão para voltar à visão geral.

### Relatório do desafio anterior

A página **Análise geográfica** em `Financial_Sample.pbix` contém:

1. **Vendas e unidades vendidas por país** — mapa com vendas no tamanho das bolhas e unidades vendidas nas dicas de ferramenta.
2. **Lucro total por país** — mapa preenchido, colorido pelo lucro total.
3. **Lucro por segmento** — gráfico de pizza com valores e percentuais.

Os relatórios usam os campos `Country`, ` Sales`, `Units Sold`, `Profit`, `Segment`, `Product` e `Date` da amostra. O nome da coluna de vendas no arquivo de origem contém um espaço inicial (` Sales`).

## Publicar e compartilhar

Para publicar, abra o PBIX no Power BI Desktop, escolha **Página Inicial → Publicar** e selecione o workspace desejado. A publicação requer uma conta do Power BI. Para exportar um suplemento do PowerPoint, use **Arquivo → Exportar → PowerPoint** após publicar ou abrir o relatório no serviço do Power BI.

O arquivo PBIX é a entrega editável caso a exportação para PowerPoint não esteja disponível.

## Origem

O relatório e a amostra financeira têm como referência o repositório [power_bi_analyst](https://github.com/julianazanelatto/power_bi_analyst), em especial o material do desafio do Módulo 2. A terceira página foi preenchida para atender aos visuais solicitados.

## Desafio — Processando e Transformando Dados com Power BI

A entrega adicional está em [`challenge-data-transformation/`](./challenge-data-transformation/README.md). Ela inclui o projeto PBIP, os scripts Power Query, os dados de origem/processados e as verificações da base Company. Os desafios anteriores e seus arquivos continuam preservados.

### Referências oficiais

- [Instruções do desafio — arquivo DOCX](https://hermes.dio.me/files/assets/a8bf65e2-a503-46c9-9453-bd6bdf329e83.docx)
- [Slides do desafio — arquivo PPTX](https://hermes.dio.me/files/assets/e7d723b3-fe92-42fa-b12c-cd33b56d81c8.pptx)
- [Repositório de dados e scripts de referência](https://github.com/julianazanelatto/power_bi_analyst/tree/main/M%C3%B3dulo%203/Desafio%20de%20Projeto)
