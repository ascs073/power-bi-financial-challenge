from __future__ import annotations

import csv
import json
import random
import re
import shutil
import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
POWER_QUERY = ROOT / "PowerQuery" / "EcommerceModel.pq"
PROJECT_DIR = ROOT / "EcommerceDax"
MODEL_DIR = PROJECT_DIR / "EcommerceDax.SemanticModel"
REPORT_DIR = PROJECT_DIR / "EcommerceDax.Report"

CENTS = Decimal("0.01")
START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 12, 31)
ORDER_COUNT = 720
RNG_SEED = 20261007

PRODUCTS = [
    ("PROD-001", "Smartphone Pro", "Celulares", "4499.90", "6299.90"),
    ("PROD-002", "Smartphone Plus", "Celulares", "2799.90", "3899.90"),
    ("PROD-003", "Smartphone Essencial", "Celulares", "1199.90", "1799.90"),
    ("PROD-004", "Notebook Ultrafino", "Informática", "3899.90", "5499.90"),
    ("PROD-005", "Notebook Gamer", "Informática", "5299.90", "7499.90"),
    ("PROD-006", "Tablet 10", "Informática", "1099.90", "1699.90"),
    ("PROD-007", "Monitor 27", "Informática", "899.90", "1399.90"),
    ("PROD-008", "Fone Bluetooth", "Áudio", "249.90", "499.90"),
    ("PROD-009", "Caixa de Som", "Áudio", "379.90", "699.90"),
    ("PROD-010", "Fone Premium", "Áudio", "799.90", "1299.90"),
    ("PROD-011", "Smartwatch", "Wearables", "699.90", "1199.90"),
    ("PROD-012", "Pulseira Inteligente", "Wearables", "169.90", "329.90"),
    ("PROD-013", "Carregador USB-C", "Acessórios", "49.90", "119.90"),
    ("PROD-014", "Capa Protetora", "Acessórios", "24.90", "79.90"),
    ("PROD-015", "Power Bank", "Acessórios", "119.90", "249.90"),
]

GEOGRAPHIES = [
    ("SP", "São Paulo", "Sudeste"),
    ("RJ", "Rio de Janeiro", "Sudeste"),
    ("MG", "Minas Gerais", "Sudeste"),
    ("ES", "Espírito Santo", "Sudeste"),
    ("PR", "Paraná", "Sul"),
    ("SC", "Santa Catarina", "Sul"),
    ("RS", "Rio Grande do Sul", "Sul"),
    ("BA", "Bahia", "Nordeste"),
    ("PE", "Pernambuco", "Nordeste"),
    ("CE", "Ceará", "Nordeste"),
    ("GO", "Goiás", "Centro-Oeste"),
    ("DF", "Distrito Federal", "Centro-Oeste"),
    ("AM", "Amazonas", "Norte"),
    ("PA", "Pará", "Norte"),
]

PAYMENT_METHODS = ["Cartão de crédito", "Pix", "Boleto"]
ORDER_STATUSES = ["Entregue", "Enviado", "Em processamento", "Cancelado", "Reembolsado"]
STATUS_WEIGHTS = [62, 17, 11, 7, 3]
MONTH_NAMES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

TABLES: dict[str, dict[str, Any]] = {
    "DimDate": {
        "query": "DimDate",
        "columns": [
            ("DateKey", "int64", "none", True),
            ("Date", "dateTime", "none", False),
            ("Year", "int64", "none", False),
            ("MonthNumber", "int64", "none", False),
            ("MonthName", "string", "none", False),
            ("YearMonth", "string", "none", False),
            ("YearMonthSort", "int64", "none", False),
        ],
    },
    "DimProduct": {
        "query": "DimProduct",
        "columns": [
            ("ProductKey", "int64", "none", True),
            ("ProductCode", "string", "none", False),
            ("ProductName", "string", "none", False),
            ("Category", "string", "none", False),
            ("UnitCost", "decimal", "none", False),
            ("ListPrice", "decimal", "none", False),
        ],
    },
    "DimCustomer": {
        "query": "DimCustomer",
        "columns": [
            ("CustomerKey", "int64", "none", True),
            ("CustomerCode", "string", "none", False),
            ("CustomerType", "string", "none", False),
        ],
    },
    "DimPaymentMethod": {
        "query": "DimPaymentMethod",
        "columns": [
            ("PaymentMethodKey", "int64", "none", True),
            ("PaymentMethod", "string", "none", False),
        ],
    },
    "DimOrderStatus": {
        "query": "DimOrderStatus",
        "columns": [
            ("OrderStatusKey", "int64", "none", True),
            ("OrderStatus", "string", "none", False),
        ],
    },
    "DimGeography": {
        "query": "DimGeography",
        "columns": [
            ("GeographyKey", "int64", "none", True),
            ("StateCode", "string", "none", False),
            ("StateName", "string", "none", False),
            ("Region", "string", "none", False),
        ],
    },
    "FactSales": {
        "query": "FactSales",
        "columns": [
            ("OrderItemKey", "int64", "none", True),
            ("OrderID", "string", "none", False),
            ("DateKey", "int64", "none", False),
            ("ProductKey", "int64", "none", False),
            ("CustomerKey", "int64", "none", False),
            ("PaymentMethodKey", "int64", "none", False),
            ("OrderStatusKey", "int64", "none", False),
            ("GeographyKey", "int64", "none", False),
            ("Quantity", "int64", "sum", False),
            ("UnitPrice", "decimal", "none", False),
            ("GrossAmount", "decimal", "sum", False),
            ("DiscountAmount", "decimal", "sum", False),
            ("NetAmount", "decimal", "sum", False),
            ("UnitCost", "decimal", "none", False),
            ("Profit", "decimal", "sum", False),
        ],
    },
}

RELATIONSHIPS = [
    ("DateKey", "DimDate", "DateKey"),
    ("ProductKey", "DimProduct", "ProductKey"),
    ("CustomerKey", "DimCustomer", "CustomerKey"),
    ("PaymentMethodKey", "DimPaymentMethod", "PaymentMethodKey"),
    ("OrderStatusKey", "DimOrderStatus", "OrderStatusKey"),
    ("GeographyKey", "DimGeography", "GeographyKey"),
]


def money(value: Decimal | str | float | int) -> Decimal:
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write an empty table: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: value.isoformat() if isinstance(value, date)
                    else format(value, "f") if isinstance(value, Decimal)
                    else value
                    for key, value in row.items()
                }
            )


def build_tables() -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(RNG_SEED)

    geography_map = {
        (state, name, region): index
        for index, (state, name, region) in enumerate(GEOGRAPHIES, start=1)
    }
    geographies = [
        {
            "GeographyKey": geography_map[(state, name, region)],
            "StateCode": state,
            "StateName": name,
            "Region": region,
        }
        for state, name, region in GEOGRAPHIES
    ]

    products = [
        {
            "ProductKey": index,
            "ProductCode": code,
            "ProductName": name,
            "Category": category,
            "UnitCost": money(cost),
            "ListPrice": money(price),
        }
        for index, (code, name, category, cost, price) in enumerate(PRODUCTS, start=1)
    ]
    product_by_key = {row["ProductKey"]: row for row in products}

    customers = [
        {
            "CustomerKey": key,
            "CustomerCode": f"CUST-{key:04d}",
            "CustomerType": "Pessoa física" if key % 5 else "Pessoa jurídica",
        }
        for key in range(1, 181)
    ]
    payment_methods = [
        {"PaymentMethodKey": key, "PaymentMethod": name}
        for key, name in enumerate(PAYMENT_METHODS, start=1)
    ]
    payment_key = {row["PaymentMethod"]: row["PaymentMethodKey"] for row in payment_methods}
    statuses = [
        {"OrderStatusKey": key, "OrderStatus": name}
        for key, name in enumerate(ORDER_STATUSES, start=1)
    ]
    status_key = {row["OrderStatus"]: row["OrderStatusKey"] for row in statuses}

    dates: list[dict[str, Any]] = []
    current = START_DATE
    while current <= END_DATE:
        dates.append(
            {
                "DateKey": current.year * 10000 + current.month * 100 + current.day,
                "Date": current,
                "Year": current.year,
                "MonthNumber": current.month,
                "MonthName": MONTH_NAMES[current.month - 1],
                "YearMonth": current.strftime("%Y-%m"),
                "YearMonthSort": current.year * 100 + current.month,
            }
        )
        current += timedelta(days=1)

    date_range = (END_DATE - START_DATE).days
    fact_sales: list[dict[str, Any]] = []
    order_totals: dict[str, Decimal] = defaultdict(Decimal)
    for order_number in range(1, ORDER_COUNT + 1):
        order_id = f"ORD-{order_number:05d}"
        order_date = START_DATE + timedelta(days=rng.randint(0, date_range))
        customer_key = rng.randint(1, len(customers))
        state, state_name, region = rng.choice(GEOGRAPHIES)
        geography_key = geography_map[(state, state_name, region)]
        payment_method = rng.choices(PAYMENT_METHODS, weights=[55, 35, 10], k=1)[0]
        order_status = rng.choices(ORDER_STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
        item_count = rng.choices([1, 2, 3, 4], weights=[52, 28, 15, 5], k=1)[0]
        selected_products = rng.sample(products, k=item_count)

        for product in selected_products:
            quantity = rng.choices([1, 2, 3], weights=[72, 23, 5], k=1)[0]
            discount_rate = rng.choices(
                [Decimal("0"), Decimal("0.05"), Decimal("0.10"), Decimal("0.15")],
                weights=[42, 30, 20, 8],
                k=1,
            )[0]
            unit_price = product["ListPrice"]
            gross_amount = money(unit_price * quantity)
            discount_amount = money(gross_amount * discount_rate)
            net_amount = money(gross_amount - discount_amount)
            line_cost = money(product["UnitCost"] * quantity)
            fact_sales.append(
                {
                    "OrderItemKey": len(fact_sales) + 1,
                    "OrderID": order_id,
                    "DateKey": order_date.year * 10000 + order_date.month * 100 + order_date.day,
                    "ProductKey": product["ProductKey"],
                    "CustomerKey": customer_key,
                    "PaymentMethodKey": payment_key[payment_method],
                    "OrderStatusKey": status_key[order_status],
                    "GeographyKey": geography_key,
                    "Quantity": quantity,
                    "UnitPrice": unit_price,
                    "GrossAmount": gross_amount,
                    "DiscountAmount": discount_amount,
                    "NetAmount": net_amount,
                    "UnitCost": product["UnitCost"],
                    "Profit": money(net_amount - line_cost),
                }
            )
            order_totals[order_id] += net_amount

    tables: dict[str, list[dict[str, Any]]] = {
        "DimDate": dates,
        "DimProduct": products,
        "DimCustomer": customers,
        "DimPaymentMethod": payment_methods,
        "DimOrderStatus": statuses,
        "DimGeography": geographies,
        "FactSales": fact_sales,
    }
    for table_name, rows in tables.items():
        write_csv(DATA_DIR / f"{table_name}.csv", rows)

    valid_status = {
        row["OrderStatusKey"]: row["OrderStatus"]
        for row in statuses
    }
    valid_lines = [
        row for row in fact_sales
        if valid_status[row["OrderStatusKey"]] not in {"Cancelado", "Reembolsado"}
    ]
    valid_order_ids = {row["OrderID"] for row in valid_lines}
    canceled_order_ids = {
        row["OrderID"] for row in fact_sales
        if valid_status[row["OrderStatusKey"]] == "Cancelado"
    }
    validation = {
        "orders": ORDER_COUNT,
        "order_items": len(fact_sales),
        "valid_orders": len(valid_order_ids),
        "valid_sales": money(sum((row["NetAmount"] for row in valid_lines), Decimal("0"))),
        "valid_profit": money(sum((row["Profit"] for row in valid_lines), Decimal("0"))),
        "canceled_orders": len(canceled_order_ids),
        "customers": len({row["CustomerKey"] for row in valid_lines}),
        "total_order_value_including_canceled": money(sum(order_totals.values(), Decimal("0"))),
    }
    return {**tables, "_Validation": [validation]}


def read_expressions() -> dict[str, str]:
    source = POWER_QUERY.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^shared\s+([A-Za-z_]\w*)\s*=", source))
    expressions: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        body = source[match.end():end].strip()
        if body.endswith(";"):
            body = body[:-1].rstrip()
        expressions[match.group(1)] = body
    expected = {"CsvTable", *(table["query"] for table in TABLES.values())}
    missing = expected - expressions.keys()
    if missing:
        raise ValueError(f"Power Query expressions missing: {sorted(missing)}")
    folder = str(DATA_DIR.resolve()).replace('"', '""')
    expressions["DataFolder"] = (
        f'"{folder}" meta [IsParameterQuery = true, Type = "Text", '
        "IsParameterQueryRequired = true]"
    )
    return expressions


def partition_m(query_name: str, expressions: dict[str, str]) -> str:
    names = [
        name for name in expressions
        if name not in {"DataFolder", "CsvTable"}
    ]
    lines = ["let"]
    lines.extend(f"    {name} = {expressions[name]}," for name in names)
    lines.extend([f"    Result = {query_name}", "in", "    Result"])
    return "\n".join(lines)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_model(expressions: dict[str, str]) -> None:
    definition = MODEL_DIR / "definition"
    table_dir = definition / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        MODEL_DIR / ".platform",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "SemanticModel", "displayName": "EcommerceDax"},
            "config": {"version": "2.0", "logicalId": str(uuid.uuid4())},
        },
    )
    write_json(
        MODEL_DIR / "definition.pbism",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.0",
            "settings": {},
        },
    )
    (definition / "database.tmdl").write_text(
        "database EcommerceDax\n\tcompatibilityLevel: 1600\n\tlanguage: 1046\n",
        encoding="utf-8",
    )
    model_lines = [
        "model EcommerceDax\n",
        "\tculture: pt-BR\n",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n",
        "\tdiscourageImplicitMeasures\n",
        "\tsourceQueryCulture: pt-BR\n",
        "\tdataAccessOptions\n",
        "\t\tlegacyRedirects\n",
        "\t\treturnErrorValuesAsNull\n\n",
        "queryGroup Parameters\n\tannotation PBI_QueryGroupOrder = 0\n\n",
        "queryGroup Tables\n\tannotation PBI_QueryGroupOrder = 1\n\n",
        "".join(f"ref table {name}\n" for name in TABLES),
        "\n",
    ]
    for fact_key, dimension, dimension_key in RELATIONSHIPS:
        model_lines.extend(
            [
                f"relationship FactSales_{dimension}_{fact_key}\n",
                f"\tfromColumn: FactSales.{fact_key}\n",
                f"\ttoColumn: {dimension}.{dimension_key}\n",
                "\tcrossFilteringBehavior: oneDirection\n",
                "\tisActive: true\n\n",
            ]
        )
    (definition / "model.tmdl").write_text(
        "".join(model_lines).rstrip() + "\n", encoding="utf-8"
    )

    expression_blocks: list[str] = []
    for name in ("DataFolder", "CsvTable"):
        expression_blocks.append(
            f"expression {name} =\n"
            + "".join(f"\t\t{line}\n" for line in expressions[name].splitlines())
            + f"\tlineageTag: {uuid.uuid4()}\n"
            f"\tqueryGroup: {'Parameters' if name == 'DataFolder' else 'Tables'}\n"
            "\tannotation PBI_NavigationStepName = Navigation\n"
            f"\tannotation PBI_ResultType = {'Text' if name == 'DataFolder' else 'Function'}\n"
        )
    (definition / "expressions.tmdl").write_text(
        "\n".join(expression_blocks), encoding="utf-8"
    )

    for table_name, table in TABLES.items():
        lines = [f"table {table_name}\n", f"\tlineageTag: {uuid.uuid4()}\n\n"]
        if table_name == "FactSales":
            measures = [
                (
                    "'Vendas Brutas'",
                    "SUM(FactSales[GrossAmount])",
                    '$#,##0.00;($#,##0.00);-',
                ),
                (
                    "'Descontos'",
                    "SUM(FactSales[DiscountAmount])",
                    '$#,##0.00;($#,##0.00);-',
                ),
                (
                    "'Vendas Líquidas'",
                    'CALCULATE(SUM(FactSales[NetAmount]), KEEPFILTERS(DimOrderStatus[OrderStatus] <> "Cancelado"), KEEPFILTERS(DimOrderStatus[OrderStatus] <> "Reembolsado"))',
                    '$#,##0.00;($#,##0.00);-',
                ),
                (
                    "'Pedidos'",
                    "DISTINCTCOUNT(FactSales[OrderID])",
                    "#,##0",
                ),
                (
                    "'Pedidos Válidos'",
                    'CALCULATE(DISTINCTCOUNT(FactSales[OrderID]), KEEPFILTERS(DimOrderStatus[OrderStatus] <> "Cancelado"), KEEPFILTERS(DimOrderStatus[OrderStatus] <> "Reembolsado"))',
                    "#,##0",
                ),
                (
                    "'Ticket Médio'",
                    "DIVIDE([Vendas Líquidas], [Pedidos Válidos])",
                    '$#,##0.00;($#,##0.00);-',
                ),
                (
                    "'Lucro'",
                    'CALCULATE(SUM(FactSales[Profit]), KEEPFILTERS(DimOrderStatus[OrderStatus] <> "Cancelado"), KEEPFILTERS(DimOrderStatus[OrderStatus] <> "Reembolsado"))',
                    '$#,##0.00;($#,##0.00);-',
                ),
                (
                    "'Margem %'",
                    "DIVIDE([Lucro], [Vendas Líquidas])",
                    "0.0%;(0.0%);-",
                ),
                (
                    "'Unidades Vendidas'",
                    'CALCULATE(SUM(FactSales[Quantity]), KEEPFILTERS(DimOrderStatus[OrderStatus] <> "Cancelado"), KEEPFILTERS(DimOrderStatus[OrderStatus] <> "Reembolsado"))',
                    "#,##0",
                ),
                (
                    "'Clientes'",
                    'CALCULATE(DISTINCTCOUNT(FactSales[CustomerKey]), KEEPFILTERS(DimOrderStatus[OrderStatus] <> "Cancelado"), KEEPFILTERS(DimOrderStatus[OrderStatus] <> "Reembolsado"))',
                    "#,##0",
                ),
                (
                    "'Pedidos Cancelados'",
                    'CALCULATE(DISTINCTCOUNT(FactSales[OrderID]), KEEPFILTERS(DimOrderStatus[OrderStatus] = "Cancelado"))',
                    "#,##0",
                ),
                (
                    "'Taxa de Cancelamento'",
                    "DIVIDE([Pedidos Cancelados], [Pedidos])",
                    "0.0%;(0.0%);-",
                ),
                (
                    "'Vendas Mês Anterior'",
                    "CALCULATE([Vendas Líquidas], DATEADD(DimDate[Date], -1, MONTH))",
                    '$#,##0.00;($#,##0.00);-',
                ),
                (
                    "'Variação Mensal %'",
                    "DIVIDE([Vendas Líquidas] - [Vendas Mês Anterior], [Vendas Mês Anterior])",
                    "0.0%;(0.0%);-",
                ),
            ]
            for name, expression, format_string in measures:
                lines.extend(
                    [
                        f"\tmeasure {name} = {expression}\n",
                        f"\t\tformatString: {format_string}\n",
                        f"\t\tlineageTag: {uuid.uuid4()}\n\n",
                    ]
                )
        for column, data_type, summarize, is_key in table["columns"]:
            lines.extend(
                [
                    f"\tcolumn {column}\n",
                    f"\t\tdataType: {data_type}\n",
                    f"\t\tsummarizeBy: {summarize}\n",
                    f"\t\tsourceColumn: {column}\n",
                ]
            )
            if is_key:
                lines.append("\t\tisKey\n")
            if column in {
                "UnitCost", "ListPrice", "UnitPrice", "GrossAmount",
                "DiscountAmount", "NetAmount", "Profit",
            }:
                lines.append("\t\tformatString: $#,##0.00;($#,##0.00);-\n")
            elif column in {"Year", "MonthNumber", "YearMonthSort", "Quantity"}:
                lines.append("\t\tformatString: #,##0\n")
            if table_name == "DimDate" and column == "YearMonth":
                lines.append("\t\tsortByColumn: YearMonthSort\n")
            lines.append("\n")
        partition = partition_m(table["query"], expressions)
        lines.extend(
            [
                f"\tpartition {table_name} = m\n",
                "\t\tmode: import\n",
                "\t\tqueryGroup: Tables\n",
                "\t\tsource = ```\n",
                "".join(f"\t\t\t{line}\n" for line in partition.splitlines()),
                "\t\t\t```\n\n",
                "\tannotation PBI_ResultType = Table\n",
            ]
        )
        (table_dir / f"{table_name}.tmdl").write_text(
            "".join(lines).rstrip() + "\n", encoding="utf-8"
        )


def column_projection(entity: str, name: str) -> dict[str, Any]:
    return {
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": name,
            }
        },
        "queryRef": f"{entity}.{name}",
        "nativeQueryRef": name,
        "active": True,
    }


def measure_projection(name: str) -> dict[str, Any]:
    return {
        "field": {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": "FactSales"}},
                "Property": name,
            }
        },
        "queryRef": f"FactSales.{name}",
        "nativeQueryRef": name,
        "active": True,
    }


def create_visual(
    visual_type: str,
    title: str,
    roles: dict[str, list[dict[str, Any]]],
    position: dict[str, int],
) -> dict[str, Any]:
    projections: dict[str, list[dict[str, Any]]] = {}
    for role, fields in roles.items():
        projections[role] = [
            (
                measure_projection(item["measure"])
                if "measure" in item
                else column_projection(item["entity"], item["column"])
            )
            for item in fields
        ]
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json",
        "name": uuid.uuid4().hex[:20],
        "position": position,
        "visual": {
            "visualType": visual_type,
            "query": {"queryState": projections},
            "drillFilterOtherVisuals": True,
            "objects": {
                "title": [
                    {
                        "properties": {
                            "show": {"expr": {"Literal": {"Value": "true"}}},
                            "text": {"expr": {"Literal": {"Value": f"'{title}'"}}},
                        }
                    }
                ]
            },
        },
    }


def create_report() -> None:
    definition = REPORT_DIR / "definition"
    pages = definition / "pages"
    if pages.exists():
        shutil.rmtree(pages)
    pages.mkdir(parents=True, exist_ok=True)
    page_id = uuid.uuid4().hex[:20]
    write_json(
        REPORT_DIR / ".platform",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "Report", "displayName": "EcommerceDax"},
            "config": {"version": "2.0", "logicalId": str(uuid.uuid4())},
        },
    )
    write_json(
        REPORT_DIR / "definition.pbir",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../EcommerceDax.SemanticModel"}},
        },
    )
    write_json(
        definition / "version.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        },
    )
    write_json(
        definition / "report.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU10",
                    "reportVersionAtImport": {
                        "visual": "2.1.0", "report": "2.1.0", "page": "2.0.0"
                    },
                    "type": "SharedResources",
                }
            },
            "settings": {
                "useStylableVisualContainerHeader": True,
                "exportDataMode": "AllowSummarized",
                "defaultDrillFilterOtherVisuals": True,
                "allowChangeFilterTypes": True,
            },
        },
    )
    write_json(
        pages / "pages.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [page_id],
            "activePageName": page_id,
        },
    )
    page_dir = pages / f"{page_id}.Page"
    write_json(
        page_dir / "page.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
            "name": page_id,
            "displayName": "Dashboard de E-commerce",
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        },
    )
    visuals = [
        create_visual(
            "card", "Receita líquida",
            {"Values": [{"measure": "Vendas Líquidas"}]},
            {"x": 24, "y": 22, "z": 0, "height": 100, "width": 220, "tabOrder": 0},
        ),
        create_visual(
            "card", "Pedidos válidos",
            {"Values": [{"measure": "Pedidos Válidos"}]},
            {"x": 260, "y": 22, "z": 1, "height": 100, "width": 220, "tabOrder": 1},
        ),
        create_visual(
            "card", "Ticket médio",
            {"Values": [{"measure": "Ticket Médio"}]},
            {"x": 496, "y": 22, "z": 2, "height": 100, "width": 220, "tabOrder": 2},
        ),
        create_visual(
            "card", "Margem de lucro",
            {"Values": [{"measure": "Margem %"}]},
            {"x": 732, "y": 22, "z": 3, "height": 100, "width": 220, "tabOrder": 3},
        ),
        create_visual(
            "slicer", "Ano",
            {"Values": [{"entity": "DimDate", "column": "Year"}]},
            {"x": 978, "y": 22, "z": 4, "height": 100, "width": 126, "tabOrder": 4},
        ),
        create_visual(
            "slicer", "Status do pedido",
            {"Values": [{"entity": "DimOrderStatus", "column": "OrderStatus"}]},
            {"x": 1120, "y": 22, "z": 5, "height": 100, "width": 140, "tabOrder": 5},
        ),
        create_visual(
            "lineChart", "Receita líquida por mês",
            {
                "Category": [{"entity": "DimDate", "column": "YearMonth"}],
                "Y": [{"measure": "Vendas Líquidas"}],
            },
            {"x": 24, "y": 142, "z": 6, "height": 250, "width": 620, "tabOrder": 6},
        ),
        create_visual(
            "clusteredBarChart", "Receita por categoria",
            {
                "Category": [{"entity": "DimProduct", "column": "Category"}],
                "Y": [{"measure": "Vendas Líquidas"}],
            },
            {"x": 664, "y": 142, "z": 7, "height": 250, "width": 290, "tabOrder": 7},
        ),
        create_visual(
            "donutChart", "Pedidos por status",
            {
                "Category": [{"entity": "DimOrderStatus", "column": "OrderStatus"}],
                "Y": [{"measure": "Pedidos"}],
            },
            {"x": 974, "y": 142, "z": 8, "height": 250, "width": 286, "tabOrder": 8},
        ),
        create_visual(
            "clusteredBarChart", "Receita por estado",
            {
                "Category": [{"entity": "DimGeography", "column": "StateCode"}],
                "Y": [{"measure": "Vendas Líquidas"}],
            },
            {"x": 24, "y": 410, "z": 9, "height": 280, "width": 610, "tabOrder": 9},
        ),
        create_visual(
            "clusteredColumnChart", "Pedidos por forma de pagamento",
            {
                "Category": [{"entity": "DimPaymentMethod", "column": "PaymentMethod"}],
                "Y": [{"measure": "Pedidos"}],
            },
            {"x": 654, "y": 410, "z": 10, "height": 280, "width": 606, "tabOrder": 10},
        ),
    ]
    for item in visuals:
        write_json(
            page_dir / "visuals" / f"{item['name']}.Visual" / "visual.json",
            item,
        )


def main() -> None:
    tables = build_tables()
    expressions = read_expressions()
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    create_model(expressions)
    create_report()
    write_json(
        PROJECT_DIR / "EcommerceDax.pbip",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": "EcommerceDax.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    print(f"Synthetic dataset generated with seed {RNG_SEED}.")
    for name, rows in tables.items():
        if name != "_Validation":
            print(f"{name}: {len(rows)} rows")
    for key, value in tables["_Validation"][0].items():
        print(f"{key}: {value}")
    print(f"Created Power BI project: {PROJECT_DIR / 'EcommerceDax.pbip'}")
    print(f"Model parameter DataFolder: {DATA_DIR.resolve()}")


if __name__ == "__main__":
    main()
