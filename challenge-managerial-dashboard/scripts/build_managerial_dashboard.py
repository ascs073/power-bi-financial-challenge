from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent
SOURCE_BUILDER = REPOSITORY_ROOT / "challenge-sales-star-schema" / "scripts" / "build_star_schema.py"
DATA_DIR = ROOT / "data"
PROJECT_DIR = ROOT / "ManagerialDashboard"
MODEL_DIR = PROJECT_DIR / "ManagerialDashboard.SemanticModel"
REPORT_DIR = PROJECT_DIR / "ManagerialDashboard.Report"

DAX_MEASURES: list[tuple[str, str, str]] = [
    ("Total Sales", "SUM(FactSales[NetSales])", "$#,##0;($#,##0);-"),
    ("Gross Sales", "SUM(FactSales[GrossSales])", "$#,##0;($#,##0);-"),
    ("Total Profit", "SUM(FactSales[Profit])", "$#,##0;($#,##0);-"),
    ("Profit Margin %", "DIVIDE([Total Profit], [Total Sales])", "0.0%;(0.0%);-"),
    ("Units Sold", "SUM(FactSales[UnitsSold])", "#,##0.0"),
    ("Total Discounts", "SUM(FactSales[Discounts])", "$#,##0;($#,##0);-"),
    ("Discount Rate %", "DIVIDE([Total Discounts], [Gross Sales])", "0.0%;(0.0%);-"),
    ("Sales per Unit", "DIVIDE([Total Sales], [Units Sold])", "$#,##0.00"),
    (
        "Sales Previous Month",
        "CALCULATE([Total Sales], DATEADD(DimDate[Date], -1, MONTH))",
        "$#,##0;($#,##0);-",
    ),
    ("Sales MoM Change", "[Total Sales] - [Sales Previous Month]", "$#,##0;($#,##0);-"),
    (
        "Sales MoM Change %",
        "DIVIDE([Sales MoM Change], [Sales Previous Month])",
        "0.0%;(0.0%);-",
    ),
    (
        "Sales Previous Year",
        "CALCULATE([Total Sales], SAMEPERIODLASTYEAR(DimDate[Date]))",
        "$#,##0;($#,##0);-",
    ),
    (
        "Sales YoY Change %",
        "DIVIDE([Total Sales] - [Sales Previous Year], [Sales Previous Year])",
        "0.0%;(0.0%);-",
    ),
    (
        "Profit Previous Year",
        "CALCULATE([Total Profit], SAMEPERIODLASTYEAR(DimDate[Date]))",
        "$#,##0;($#,##0);-",
    ),
    (
        "Profit YoY Change %",
        "DIVIDE([Total Profit] - [Profit Previous Year], [Profit Previous Year])",
        "0.0%;(0.0%);-",
    ),
    (
        "Profit Share %",
        "DIVIDE([Total Profit], CALCULATE([Total Profit], REMOVEFILTERS(DimProduct), REMOVEFILTERS(DimSegment), REMOVEFILTERS(DimCountry)))",
        "0.0%;(0.0%);-",
    ),
]


def load_source_builder() -> ModuleType:
    if not SOURCE_BUILDER.is_file():
        raise FileNotFoundError(
            f"Missing shared Financial Sample builder: {SOURCE_BUILDER}"
        )
    spec = importlib.util.spec_from_file_location("financial_sample_builder", SOURCE_BUILDER)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load shared builder from {SOURCE_BUILDER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.DATA_DIR = DATA_DIR
    return module


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def create_model(builder: ModuleType) -> None:
    definition = MODEL_DIR / "definition"
    table_dir = definition / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        MODEL_DIR / ".platform",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "SemanticModel", "displayName": "ManagerialDashboard"},
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
        "database ManagerialDashboard\n\tcompatibilityLevel: 1600\n\tlanguage: 1033\n",
        encoding="utf-8",
    )
    model_lines = [
        "model ManagerialDashboard\n",
        "\tculture: en-US\n",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n",
        "\tdiscourageImplicitMeasures\n",
        "\tsourceQueryCulture: en-US\n",
        "\tdataAccessOptions\n",
        "\t\tlegacyRedirects\n",
        "\t\treturnErrorValuesAsNull\n\n",
        "queryGroup Parameters\n\tannotation PBI_QueryGroupOrder = 0\n\n",
        "queryGroup Tables\n\tannotation PBI_QueryGroupOrder = 1\n\n",
        "".join(f"ref table {name}\n" for name in builder.TABLES),
        "\n",
    ]
    for fact_table, fact_key, dimension, dimension_key in builder.RELATIONSHIPS:
        model_lines.extend(
            [
                f"relationship {fact_table}_{dimension}_{fact_key}\n",
                f"\tfromColumn: {fact_table}.{fact_key}\n",
                f"\ttoColumn: {dimension}.{dimension_key}\n",
                "\tcrossFilteringBehavior: oneDirection\n",
                "\tisActive: true\n\n",
            ]
        )
    (definition / "model.tmdl").write_text(
        "".join(model_lines).rstrip() + "\n",
        encoding="utf-8",
    )

    expressions = builder.shared_expressions()
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
        "\n".join(expression_blocks),
        encoding="utf-8",
    )

    for table_name, table in builder.TABLES.items():
        lines = [f"table {table_name}\n", f"\tlineageTag: {uuid.uuid4()}\n\n"]
        if table_name == "FactSales":
            for measure_name, expression, format_string in DAX_MEASURES:
                lines.extend(
                    [
                        f"\tmeasure '{measure_name}' = {expression}\n",
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
                "ManufacturingPrice", "SalePrice", "GrossSales", "Discounts",
                "NetSales", "COGS", "Profit",
            }:
                lines.append("\t\tformatString: $#,##0.00;($#,##0.00);-\n")
            elif column in {"Year", "MonthNumber", "YearMonthSort"}:
                lines.append("\t\tformatString: #,##0\n")
            elif column == "UnitsSold":
                lines.append("\t\tformatString: #,##0.0\n")
            if table_name == "DimDate" and column == "YearMonth":
                lines.append("\t\tsortByColumn: YearMonthSort\n")
            lines.append("\n")
        query = builder.query_m(table["query"], expressions)
        lines.extend(
            [
                f"\tpartition {table_name} = m\n",
                "\t\tmode: import\n",
                "\t\tqueryGroup: Tables\n",
                "\t\tsource = ```\n",
                "".join(f"\t\t\t{line}\n" for line in query.splitlines()),
                "\t\t\t```\n\n",
                "\tannotation PBI_ResultType = Table\n",
            ]
        )
        (table_dir / f"{table_name}.tmdl").write_text(
            "".join(lines).rstrip() + "\n",
            encoding="utf-8",
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


def visual(
    visual_type: str,
    title: str,
    roles: dict[str, list[dict[str, str]]],
    position: dict[str, int],
) -> dict[str, Any]:
    projections: dict[str, list[dict[str, Any]]] = {}
    for role, fields in roles.items():
        projections[role] = [
            measure_projection(field["measure"])
            if "measure" in field
            else column_projection(field["entity"], field["column"])
            for field in fields
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


def navigation_button(
    title: str,
    destination: str,
    position: dict[str, int],
) -> dict[str, Any]:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json",
        "name": uuid.uuid4().hex[:20],
        "position": position,
        "visual": {
            "visualType": "actionButton",
            "query": {"queryState": {}},
            "drillFilterOtherVisuals": True,
            "objects": {
                "title": [
                    {
                        "properties": {
                            "text": {
                                "expr": {"Literal": {"Value": f"'{title}'"}}
                            }
                        }
                    }
                ],
                "visualLink": [
                    {
                        "properties": {
                            "show": {"expr": {"Literal": {"Value": "true"}}},
                            "type": {
                                "expr": {"Literal": {"Value": "'PageNavigation'"}}
                            },
                            "navigationSection": {
                                "expr": {
                                    "Literal": {"Value": f"'{destination}'"}
                                }
                            },
                        }
                    }
                ],
            },
        },
    }


def create_page(
    pages_dir: Path,
    display_name: str,
    visuals: list[dict[str, Any]],
    page_id: str,
) -> None:
    page_dir = pages_dir / f"{page_id}.Page"
    write_json(
        page_dir / "page.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
            "name": page_id,
            "displayName": display_name,
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        },
    )
    for item in visuals:
        write_json(
            page_dir / "visuals" / f"{item['name']}.Visual" / "visual.json",
            item,
        )


def create_report() -> None:
    definition = REPORT_DIR / "definition"
    pages_dir = definition / "pages"
    if pages_dir.exists():
        shutil.rmtree(pages_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        REPORT_DIR / ".platform",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "Report", "displayName": "ManagerialDashboard"},
            "config": {"version": "2.0", "logicalId": str(uuid.uuid4())},
        },
    )
    write_json(
        REPORT_DIR / "definition.pbir",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../ManagerialDashboard.SemanticModel"}},
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
                        "visual": "2.1.0",
                        "report": "2.1.0",
                        "page": "2.0.0",
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

    pages = [
        {
            "name": "Resumo executivo",
            "visuals": [
                visual("card", "Vendas", {"Values": [{"measure": "Total Sales"}]},
                       {"x": 24, "y": 20, "z": 0, "height": 88, "width": 205, "tabOrder": 0}),
                visual("card", "Lucro", {"Values": [{"measure": "Total Profit"}]},
                       {"x": 241, "y": 20, "z": 1, "height": 88, "width": 205, "tabOrder": 1}),
                visual("card", "Margem de lucro", {"Values": [{"measure": "Profit Margin %"}]},
                       {"x": 458, "y": 20, "z": 2, "height": 88, "width": 205, "tabOrder": 2}),
                visual("card", "Unidades vendidas", {"Values": [{"measure": "Units Sold"}]},
                       {"x": 675, "y": 20, "z": 3, "height": 88, "width": 205, "tabOrder": 3}),
                visual("slicer", "Ano", {"Values": [{"entity": "DimDate", "column": "Year"}]},
                       {"x": 900, "y": 20, "z": 4, "height": 88, "width": 110, "tabOrder": 4}),
                visual("slicer", "País", {"Values": [{"entity": "DimCountry", "column": "CountryName"}]},
                       {"x": 1020, "y": 20, "z": 5, "height": 88, "width": 125, "tabOrder": 5}),
                visual("slicer", "Segmento", {"Values": [{"entity": "DimSegment", "column": "SegmentName"}]},
                       {"x": 1155, "y": 20, "z": 6, "height": 88, "width": 105, "tabOrder": 6}),
                visual(
                    "lineChart", "Evolução mensal das vendas",
                    {
                        "Category": [{"entity": "DimDate", "column": "YearMonth"}],
                        "Y": [{"measure": "Total Sales"}],
                    },
                    {"x": 24, "y": 148, "z": 7, "height": 238, "width": 790, "tabOrder": 7},
                ),
                visual(
                    "clusteredBarChart", "Vendas por segmento",
                    {
                        "Category": [{"entity": "DimSegment", "column": "SegmentName"}],
                        "Y": [{"measure": "Total Sales"}],
                    },
                    {"x": 834, "y": 148, "z": 8, "height": 238, "width": 426, "tabOrder": 8},
                ),
                visual(
                    "clusteredColumnChart", "Lucro por país",
                    {
                        "Category": [{"entity": "DimCountry", "column": "CountryName"}],
                        "Y": [{"measure": "Total Profit"}],
                    },
                    {"x": 24, "y": 406, "z": 9, "height": 280, "width": 610, "tabOrder": 9},
                ),
                visual(
                    "clusteredBarChart", "Vendas por produto",
                    {
                        "Category": [{"entity": "DimProduct", "column": "ProductName"}],
                        "Y": [{"measure": "Total Sales"}],
                    },
                    {"x": 654, "y": 406, "z": 10, "height": 280, "width": 606, "tabOrder": 10},
                ),
            ],
        },
        {
            "name": "Rentabilidade",
            "visuals": [
                visual("card", "Lucro total", {"Values": [{"measure": "Total Profit"}]},
                       {"x": 24, "y": 20, "z": 0, "height": 88, "width": 225, "tabOrder": 0}),
                visual("card", "Margem de lucro", {"Values": [{"measure": "Profit Margin %"}]},
                       {"x": 261, "y": 20, "z": 1, "height": 88, "width": 225, "tabOrder": 1}),
                visual("card", "Descontos concedidos", {"Values": [{"measure": "Total Discounts"}]},
                       {"x": 498, "y": 20, "z": 2, "height": 88, "width": 225, "tabOrder": 2}),
                visual("card", "Taxa de desconto", {"Values": [{"measure": "Discount Rate %"}]},
                       {"x": 735, "y": 20, "z": 3, "height": 88, "width": 225, "tabOrder": 3}),
                visual("slicer", "Ano", {"Values": [{"entity": "DimDate", "column": "Year"}]},
                       {"x": 984, "y": 20, "z": 4, "height": 88, "width": 118, "tabOrder": 4}),
                visual("slicer", "Segmento", {"Values": [{"entity": "DimSegment", "column": "SegmentName"}]},
                       {"x": 1112, "y": 20, "z": 5, "height": 88, "width": 148, "tabOrder": 5}),
                visual(
                    "clusteredBarChart", "Lucro por produto",
                    {
                        "Category": [{"entity": "DimProduct", "column": "ProductName"}],
                        "Y": [{"measure": "Total Profit"}],
                    },
                    {"x": 24, "y": 148, "z": 6, "height": 228, "width": 610, "tabOrder": 6},
                ),
                visual(
                    "clusteredColumnChart", "Margem por segmento",
                    {
                        "Category": [{"entity": "DimSegment", "column": "SegmentName"}],
                        "Y": [{"measure": "Profit Margin %"}],
                    },
                    {"x": 654, "y": 148, "z": 7, "height": 228, "width": 606, "tabOrder": 7},
                ),
                visual(
                    "tableEx", "Matriz de desempenho dos produtos",
                    {
                        "Values": [
                            {"entity": "DimProduct", "column": "ProductName"},
                            {"measure": "Total Sales"},
                            {"measure": "Total Profit"},
                            {"measure": "Profit Margin %"},
                            {"measure": "Total Discounts"},
                            {"measure": "Units Sold"},
                        ]
                    },
                    {"x": 24, "y": 396, "z": 8, "height": 290, "width": 1236, "tabOrder": 8},
                ),
            ],
        },
        {
            "name": "Mercados e portfólio",
            "visuals": [
                visual("card", "Vendas líquidas", {"Values": [{"measure": "Total Sales"}]},
                       {"x": 24, "y": 20, "z": 0, "height": 88, "width": 220, "tabOrder": 0}),
                visual("card", "Variação anual", {"Values": [{"measure": "Sales YoY Change %"}]},
                       {"x": 256, "y": 20, "z": 1, "height": 88, "width": 220, "tabOrder": 1}),
                visual("card", "Variação mensal", {"Values": [{"measure": "Sales MoM Change %"}]},
                       {"x": 488, "y": 20, "z": 2, "height": 88, "width": 220, "tabOrder": 2}),
                visual("card", "Vendas por unidade", {"Values": [{"measure": "Sales per Unit"}]},
                       {"x": 720, "y": 20, "z": 3, "height": 88, "width": 220, "tabOrder": 3}),
                visual("slicer", "País", {"Values": [{"entity": "DimCountry", "column": "CountryName"}]},
                       {"x": 966, "y": 20, "z": 4, "height": 88, "width": 132, "tabOrder": 4}),
                visual("slicer", "Faixa de desconto",
                       {"Values": [{"entity": "DimDiscountBand", "column": "DiscountBand"}]},
                       {"x": 1110, "y": 20, "z": 5, "height": 88, "width": 150, "tabOrder": 5}),
                visual(
                    "clusteredBarChart", "Vendas por país",
                    {
                        "Category": [{"entity": "DimCountry", "column": "CountryName"}],
                        "Y": [{"measure": "Total Sales"}],
                    },
                    {"x": 24, "y": 148, "z": 6, "height": 228, "width": 610, "tabOrder": 6},
                ),
                visual(
                    "treemap", "Lucro por produto",
                    {
                        "Group": [{"entity": "DimProduct", "column": "ProductName"}],
                        "Values": [{"measure": "Total Profit"}],
                    },
                    {"x": 654, "y": 148, "z": 7, "height": 228, "width": 606, "tabOrder": 7},
                ),
                visual(
                    "lineChart", "Vendas e lucro por mês",
                    {
                        "Category": [{"entity": "DimDate", "column": "YearMonth"}],
                        "Y": [
                            {"measure": "Total Sales"},
                            {"measure": "Total Profit"},
                        ],
                    },
                    {"x": 24, "y": 396, "z": 8, "height": 290, "width": 610, "tabOrder": 8},
                ),
                visual(
                    "clusteredColumnChart", "Descontos por faixa",
                    {
                        "Category": [{"entity": "DimDiscountBand", "column": "DiscountBand"}],
                        "Y": [{"measure": "Total Discounts"}],
                    },
                    {"x": 654, "y": 396, "z": 9, "height": 290, "width": 606, "tabOrder": 9},
                ),
            ],
        },
    ]
    page_ids = [uuid.uuid4().hex[:20] for _ in pages]
    write_json(
        pages_dir / "pages.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": page_ids,
            "activePageName": page_ids[0],
        },
    )
    navigation_positions = [
        {"x": 24, "y": 116, "z": 20, "height": 26, "width": 392, "tabOrder": 0},
        {"x": 444, "y": 116, "z": 21, "height": 26, "width": 392, "tabOrder": 1},
        {"x": 864, "y": 116, "z": 22, "height": 26, "width": 392, "tabOrder": 2},
    ]
    for page, page_id in zip(pages, page_ids, strict=True):
        navigation = [
            navigation_button(
                destination["name"],
                "ReportSection" if index == 0 else f"ReportSection{page_ids[index]}",
                navigation_positions[index],
            )
            for index, destination in enumerate(pages)
        ]
        create_page(
            pages_dir,
            page["name"],
            navigation + page["visuals"],
            page_id,
        )


def main() -> None:
    builder = load_source_builder()
    source = builder.read_financial_sample(builder.SOURCE_XLSX)
    tables = builder.build_tables(source)
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    create_model(builder)
    create_report()
    write_json(
        PROJECT_DIR / "ManagerialDashboard.pbip",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": "ManagerialDashboard.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    print(f"Read {len(source)} financial sample rows.")
    for table_name, rows in tables.items():
        print(f"{table_name}: {len(rows)} rows")
    print(f"Created Power BI project: {PROJECT_DIR / 'ManagerialDashboard.pbip'}")
    print(f"Model parameter DataFolder: {DATA_DIR.resolve()}")


if __name__ == "__main__":
    main()
