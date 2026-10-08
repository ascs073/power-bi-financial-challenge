from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent
SOURCE_BUILDER = (
    REPOSITORY_ROOT
    / "challenge-sales-star-schema"
    / "scripts"
    / "build_star_schema.py"
)
REPORT_HELPERS = (
    REPOSITORY_ROOT
    / "challenge-managerial-dashboard"
    / "scripts"
    / "build_managerial_dashboard.py"
)
DATA_DIR = ROOT / "data"
PROJECT_DIR = ROOT / "SalesProfitAnalytics"
MODEL_DIR = PROJECT_DIR / "SalesProfitAnalytics.SemanticModel"
REPORT_DIR = PROJECT_DIR / "SalesProfitAnalytics.Report"

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
        "Profit Previous Month",
        "CALCULATE([Total Profit], DATEADD(DimDate[Date], -1, MONTH))",
        "$#,##0;($#,##0);-",
    ),
    (
        "Profit MoM Change %",
        "DIVIDE([Total Profit] - [Profit Previous Month], [Profit Previous Month])",
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

PAGES = [
    ("Vendas", "ReportSection"),
    ("Lucros", ""),
    ("Análise do período", ""),
]


def load_module(name: str, path: Path) -> ModuleType:
    if not path.is_file():
        raise FileNotFoundError(f"Required shared builder is missing: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load shared builder from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def configure_helpers() -> tuple[ModuleType, ModuleType]:
    data_builder = load_module("sales_profit_source_builder", SOURCE_BUILDER)
    data_builder.DATA_DIR = DATA_DIR
    report_helpers = load_module("sales_profit_report_helpers", REPORT_HELPERS)
    report_helpers.ROOT = ROOT
    report_helpers.DATA_DIR = DATA_DIR
    report_helpers.PROJECT_DIR = PROJECT_DIR
    report_helpers.MODEL_DIR = MODEL_DIR
    report_helpers.REPORT_DIR = REPORT_DIR
    report_helpers.DAX_MEASURES = DAX_MEASURES
    return data_builder, report_helpers


def make_page_visuals(
    report: ModuleType,
    page_index: int,
    page_ids: list[str],
) -> list[dict[str, Any]]:
    visual = report.visual
    nav_positions = [
        {"x": 24, "y": 116, "z": 20, "height": 26, "width": 392, "tabOrder": 0},
        {"x": 444, "y": 116, "z": 21, "height": 26, "width": 392, "tabOrder": 1},
        {"x": 864, "y": 116, "z": 22, "height": 26, "width": 392, "tabOrder": 2},
    ]
    navigation = []
    for index, (name, _) in enumerate(PAGES):
        if index == 0:
            target = "ReportSection"
        else:
            target = f"ReportSection{page_ids[index]}"
        label = f"● {name}" if index == page_index else name
        navigation.append(
            report.navigation_button(label, target, nav_positions[index])
        )

    total_sales = {"measure": "Total Sales"}
    gross_sales = {"measure": "Gross Sales"}
    total_profit = {"measure": "Total Profit"}
    margin = {"measure": "Profit Margin %"}
    units = {"measure": "Units Sold"}
    discounts = {"measure": "Total Discounts"}
    discount_rate = {"measure": "Discount Rate %"}
    sales_mom = {"measure": "Sales MoM Change %"}
    profit_mom = {"measure": "Profit MoM Change %"}
    sales_yoy = {"measure": "Sales YoY Change %"}
    profit_yoy = {"measure": "Profit YoY Change %"}

    if page_index == 0:
        body = [
            visual(
                "card", "Vendas líquidas", {"Values": [total_sales]},
                {"x": 24, "y": 18, "z": 0, "height": 86, "width": 202, "tabOrder": 3},
            ),
            visual(
                "card", "Vendas brutas", {"Values": [gross_sales]},
                {"x": 240, "y": 18, "z": 1, "height": 86, "width": 202, "tabOrder": 4},
            ),
            visual(
                "card", "Unidades vendidas", {"Values": [units]},
                {"x": 456, "y": 18, "z": 2, "height": 86, "width": 202, "tabOrder": 5},
            ),
            visual(
                "card", "Descontos", {"Values": [discounts]},
                {"x": 672, "y": 18, "z": 3, "height": 86, "width": 202, "tabOrder": 6},
            ),
            visual(
                "slicer", "Ano", {"Values": [{"entity": "DimDate", "column": "Year"}]},
                {"x": 892, "y": 18, "z": 4, "height": 86, "width": 150, "tabOrder": 7},
            ),
            visual(
                "slicer", "Segmento",
                {"Values": [{"entity": "DimSegment", "column": "SegmentName"}]},
                {"x": 1060, "y": 18, "z": 5, "height": 86, "width": 200, "tabOrder": 8},
            ),
            visual(
                "lineChart", "Vendas líquidas por mês",
                {
                    "Category": [{"entity": "DimDate", "column": "YearMonth"}],
                    "Y": [total_sales],
                },
                {"x": 24, "y": 150, "z": 6, "height": 238, "width": 790, "tabOrder": 9},
            ),
            visual(
                "donutChart", "Vendas por segmento",
                {
                    "Category": [{"entity": "DimSegment", "column": "SegmentName"}],
                    "Y": [total_sales],
                },
                {"x": 834, "y": 150, "z": 7, "height": 238, "width": 426, "tabOrder": 10},
            ),
            visual(
                "clusteredBarChart", "Vendas por produto",
                {
                    "Category": [{"entity": "DimProduct", "column": "ProductName"}],
                    "Y": [total_sales],
                },
                {"x": 24, "y": 402, "z": 8, "height": 284, "width": 610, "tabOrder": 11},
            ),
            visual(
                "tableEx", "Matriz de vendas por período",
                {
                    "Values": [
                        {"entity": "DimDate", "column": "Year"},
                        {"entity": "DimDate", "column": "Quarter"},
                        {"entity": "DimDate", "column": "MonthName"},
                        total_sales,
                        units,
                    ]
                },
                {"x": 654, "y": 402, "z": 9, "height": 284, "width": 606, "tabOrder": 12},
            ),
        ]
    elif page_index == 1:
        body = [
            visual(
                "card", "Lucro total", {"Values": [total_profit]},
                {"x": 24, "y": 18, "z": 0, "height": 86, "width": 202, "tabOrder": 3},
            ),
            visual(
                "card", "Margem de lucro", {"Values": [margin]},
                {"x": 240, "y": 18, "z": 1, "height": 86, "width": 202, "tabOrder": 4},
            ),
            visual(
                "card", "Vendas líquidas", {"Values": [total_sales]},
                {"x": 456, "y": 18, "z": 2, "height": 86, "width": 202, "tabOrder": 5},
            ),
            visual(
                "card", "Taxa de desconto", {"Values": [discount_rate]},
                {"x": 672, "y": 18, "z": 3, "height": 86, "width": 202, "tabOrder": 6},
            ),
            visual(
                "slicer", "País",
                {"Values": [{"entity": "DimCountry", "column": "CountryName"}]},
                {"x": 892, "y": 18, "z": 4, "height": 86, "width": 150, "tabOrder": 7},
            ),
            visual(
                "slicer", "Segmento",
                {"Values": [{"entity": "DimSegment", "column": "SegmentName"}]},
                {"x": 1060, "y": 18, "z": 5, "height": 86, "width": 200, "tabOrder": 8},
            ),
            visual(
                "clusteredBarChart", "Lucro por produto",
                {
                    "Category": [{"entity": "DimProduct", "column": "ProductName"}],
                    "Y": [total_profit],
                },
                {"x": 24, "y": 150, "z": 6, "height": 236, "width": 610, "tabOrder": 9},
            ),
            visual(
                "clusteredColumnChart", "Margem por segmento",
                {
                    "Category": [{"entity": "DimSegment", "column": "SegmentName"}],
                    "Y": [margin],
                },
                {"x": 654, "y": 150, "z": 7, "height": 236, "width": 606, "tabOrder": 10},
            ),
            visual(
                "treemap", "Lucro por país",
                {
                    "Group": [{"entity": "DimCountry", "column": "CountryName"}],
                    "Values": [total_profit],
                },
                {"x": 24, "y": 402, "z": 8, "height": 284, "width": 390, "tabOrder": 11},
            ),
            visual(
                "clusteredBarChart", "Descontos por faixa",
                {
                    "Category": [{"entity": "DimDiscountBand", "column": "DiscountBand"}],
                    "Y": [discounts],
                },
                {"x": 434, "y": 402, "z": 9, "height": 284, "width": 390, "tabOrder": 12},
            ),
            visual(
                "tableEx", "Rentabilidade por produto",
                {
                    "Values": [
                        {"entity": "DimProduct", "column": "ProductName"},
                        total_sales,
                        total_profit,
                        margin,
                        {"measure": "Profit Share %"},
                    ]
                },
                {"x": 844, "y": 402, "z": 10, "height": 284, "width": 416, "tabOrder": 13},
            ),
        ]
    else:
        body = [
            visual(
                "card", "Variação mensal de vendas", {"Values": [sales_mom]},
                {"x": 24, "y": 18, "z": 0, "height": 86, "width": 202, "tabOrder": 3},
            ),
            visual(
                "card", "Variação mensal de lucro", {"Values": [profit_mom]},
                {"x": 240, "y": 18, "z": 1, "height": 86, "width": 202, "tabOrder": 4},
            ),
            visual(
                "card", "Variação anual de vendas", {"Values": [sales_yoy]},
                {"x": 456, "y": 18, "z": 2, "height": 86, "width": 202, "tabOrder": 5},
            ),
            visual(
                "card", "Variação anual de lucro", {"Values": [profit_yoy]},
                {"x": 672, "y": 18, "z": 3, "height": 86, "width": 202, "tabOrder": 6},
            ),
            visual(
                "slicer", "Ano", {"Values": [{"entity": "DimDate", "column": "Year"}]},
                {"x": 892, "y": 18, "z": 4, "height": 86, "width": 150, "tabOrder": 7},
            ),
            visual(
                "slicer", "País",
                {"Values": [{"entity": "DimCountry", "column": "CountryName"}]},
                {"x": 1060, "y": 18, "z": 5, "height": 86, "width": 200, "tabOrder": 8},
            ),
            visual(
                "lineChart", "Vendas e lucro ao longo do tempo",
                {
                    "Category": [{"entity": "DimDate", "column": "YearMonth"}],
                    "Y": [total_sales, total_profit],
                },
                {"x": 24, "y": 150, "z": 6, "height": 246, "width": 790, "tabOrder": 9},
            ),
            visual(
                "clusteredColumnChart", "Vendas por ano e trimestre",
                {
                    "Category": [
                        {"entity": "DimDate", "column": "Year"},
                        {"entity": "DimDate", "column": "Quarter"},
                    ],
                    "Y": [total_sales],
                },
                {"x": 834, "y": 150, "z": 7, "height": 246, "width": 426, "tabOrder": 10},
            ),
            visual(
                "waterfallChart", "Lucro por trimestre",
                {
                    "Category": [{"entity": "DimDate", "column": "YearMonth"}],
                    "Y": [total_profit],
                },
                {"x": 24, "y": 412, "z": 8, "height": 274, "width": 610, "tabOrder": 11},
            ),
            visual(
                "tableEx", "Matriz de vendas e lucros",
                {
                    "Values": [
                        {"entity": "DimDate", "column": "Year"},
                        {"entity": "DimDate", "column": "Quarter"},
                        total_sales,
                        gross_sales,
                        total_profit,
                        margin,
                        sales_yoy,
                    ]
                },
                {"x": 654, "y": 412, "z": 9, "height": 274, "width": 606, "tabOrder": 12},
            ),
        ]
    return navigation + body


def create_report(report: ModuleType) -> None:
    definition = REPORT_DIR / "definition"
    pages_dir = definition / "pages"
    if pages_dir.exists():
        import shutil
        shutil.rmtree(pages_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)

    report.write_json(
        REPORT_DIR / ".platform",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "Report", "displayName": "SalesProfitAnalytics"},
            "config": {"version": "2.0", "logicalId": str(uuid.uuid4())},
        },
    )
    write_json(
        REPORT_DIR / "definition.pbir",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {
                "byPath": {"path": "../SalesProfitAnalytics.SemanticModel"}
            },
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
    page_ids = [uuid.uuid4().hex[:20] for _ in PAGES]
    write_json(
        pages_dir / "pages.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": page_ids,
            "activePageName": page_ids[0],
        },
    )
    for index, (page_id, page) in enumerate(zip(page_ids, PAGES, strict=True)):
        report.create_page(
            pages_dir,
            page[0],
            make_page_visuals(report, index, page_ids),
            page_id,
        )


def main() -> None:
    builder, report = configure_helpers()
    source_rows = builder.read_financial_sample(builder.SOURCE_XLSX)
    tables = builder.build_tables(source_rows)
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    report.create_model(builder)
    create_report(report)
    write_json(
        PROJECT_DIR / "SalesProfitAnalytics.pbip",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": "SalesProfitAnalytics.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    print(f"Read {len(source_rows)} financial sample rows.")
    for name, rows in tables.items():
        print(f"{name}: {len(rows)} rows")
    print(f"Created Power BI project: {PROJECT_DIR / 'SalesProfitAnalytics.pbip'}")
    print(f"Model parameter DataFolder: {DATA_DIR.resolve()}")


if __name__ == "__main__":
    main()
