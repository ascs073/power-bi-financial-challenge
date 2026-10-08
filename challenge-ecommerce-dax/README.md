# Dashboard de e-commerce com fórmulas DAX

Projeto didático, reproduzível e sem dados pessoais. O diretório local de e-commerce continha apenas exemplos de API (incluindo dois pedidos fictícios), não uma base transacional consistente para análise. Por isso, esta entrega gera um conjunto de dados **sintético e determinístico**, identificado como demonstração — não representa vendas reais nem deve ser interpretado como previsão.

## Abrir e reconstruir

Abra `EcommerceDax\EcommerceDax.pbip` no Power BI Desktop. Para recriar os CSVs e o projeto após clonar o repositório:

```powershell
python scripts\build_ecommerce.py
python -m unittest discover -s tests -v
```

O script não tem dependências de terceiros. Ele cria um histórico demonstrativo de pedidos, itens, produtos, clientes anônimos, pagamentos, situação dos pedidos, datas e localidades. O parâmetro `DataFolder` do PBIP é escrito com o caminho local da pasta `data`.

## Modelo estrela

O grão da `FactSales` é **uma linha de item do pedido**. O `OrderID` se repete quando um pedido contém mais de um produto; as medidas de pedidos usam `DISTINCTCOUNT`, não contagem de linhas.

```text
DimDate ───────────┐
DimProduct ────────┤
DimCustomer ──────┤
DimPaymentMethod ─┼── FactSales
DimOrderStatus ───┤
DimGeography ─────┘
```

Todas as relações são ativas, um-para-muitos e unidirecionais, da dimensão para a fato. Receita líquida, unidades e lucro excluem pedidos cancelados e reembolsados. A medida de pedidos continua contando todos os status para que a taxa de cancelamento use o total correto.

Com a semente demonstrativa `20261007`, o gerador cria 720 pedidos e 1.256 itens. Os resultados de referência são 652 pedidos válidos, receita líquida de R$ 3.331.162,90 e lucro de R$ 943.741,90. Alterar a semente ou as regras de geração muda esses valores.

## Medidas DAX

- **Vendas Brutas** e **Descontos**: totais antes e depois do desconto, incluindo pedidos não concluídos para dar transparência aos dados.
- **Vendas Líquidas**: itens após desconto, excluindo cancelados e reembolsados.
- **Pedidos** e **Pedidos Válidos**: contagem distinta de pedidos; a segunda exclui cancelamentos e reembolsos.
- **Ticket Médio**: vendas líquidas divididas por pedidos válidos.
- **Lucro** e **Margem %**: custo subtraído das vendas líquidas válidas e lucro dividido pela receita.
- **Unidades Vendidas**, **Clientes**, **Taxa de Cancelamento**, **Vendas Mês Anterior** e **Variação Mensal %**.

O painel contém cartões de KPI, tendência mensal, vendas por categoria e forma de pagamento, status dos pedidos e vendas por estado, além de segmentadores de ano e status.

## Arquivos

- `EcommerceDax/`: PBIP, modelo semântico TMDL e relatório PBIR.
- `DAX/Measures.dax`: fórmulas DAX em formato copiável para o Power BI.
- `PowerQuery/EcommerceModel.pq`: consultas de tipagem para as seis tabelas.
- `data/`: seis dimensões e a tabela fato demonstrativa.
- `scripts/build_ecommerce.py`: gera os dados e o PBIP com semente fixa.
- `tests/test_ecommerce.py`: testa grão, relações, agregações, medidas e estrutura do relatório.
