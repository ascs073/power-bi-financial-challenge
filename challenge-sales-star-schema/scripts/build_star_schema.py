from __future__ import annotations

import csv
import json
import re
import shutil
import uuid
import zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent
SOURCE_XLSX = REPOSITORY_ROOT / "data" / "financial_sample.xlsx"
DATA_DIR = ROOT / "data"
POWER_QUERY = ROOT / "PowerQuery" / "StarSchema.pq"
PROJECT_DIR = ROOT / "SalesStarSchema"
MODEL_DIR = PROJECT_DIR / "SalesStarSchema.SemanticModel"
REPORT_DIR = PROJECT_DIR / "SalesStarSchema.Report"

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

TABLES: dict[str, dict[str, Any]] = {
    "DimDate": {
        "query": "DimDate",
        "columns": [
            ("DateKey", "int64", "none", True),
            ("Date", "dateTime", "none", False),
            ("Year", "int64", "none", False),
            ("Quarter", "string", "none", False),
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
            ("ProductName", "string", "none", False),
            ("ManufacturingPrice", "decimal", "none", False),
        ],
    },
    "DimCountry": {
        "query": "DimCountry",
        "columns": [
            ("CountryKey", "int64", "none", True),
            ("CountryName", "string", "none", False),
        ],
    },
    "DimSegment": {
        "query": "DimSegment",
        "columns": [
            ("SegmentKey", "int64", "none", True),
            ("SegmentName", "string", "none", False),
        ],
    },
    "DimDiscountBand": {
        "query": "DimDiscountBand",
        "columns": [
            ("DiscountBandKey", "int64", "none", True),
            ("DiscountBand", "string", "none", False),
        ],
    },
    "FactSales": {
        "query": "FactSales",
        "columns": [
            ("FactRowID", "int64", "none", True),
            ("DateKey", "int64", "none", False),
            ("ProductKey", "int64", "none", False),
            ("CountryKey", "int64", "none", False),
            ("SegmentKey", "int64", "none", False),
            ("DiscountBandKey", "int64", "none", False),
            ("UnitsSold", "decimal", "sum", False),
            ("ManufacturingPrice", "decimal", "sum", False),
            ("SalePrice", "decimal", "sum", False),
            ("GrossSales", "decimal", "sum", False),
            ("Discounts", "decimal", "sum", False),
            ("NetSales", "decimal", "sum", False),
            ("COGS", "decimal", "sum", False),
            ("Profit", "decimal", "sum", False),
        ],
    },
}

RELATIONSHIPS = [
    ("FactSales", "DateKey", "DimDate", "DateKey"),
    ("FactSales", "ProductKey", "DimProduct", "ProductKey"),
    ("FactSales", "CountryKey", "DimCountry", "CountryKey"),
    ("FactSales", "SegmentKey", "DimSegment", "SegmentKey"),
    ("FactSales", "DiscountBandKey", "DimDiscountBand", "DiscountBandKey"),
]


def read_financial_sample(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing source workbook: {path}. Restore data/financial_sample.xlsx "
            "from the repository before rebuilding this challenge."
        )
    with zipfile.ZipFile(path) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target_by_id = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in relationships.findall("rel:Relationship", NS)
        }
        first_sheet = workbook.find("m:sheets/m:sheet", NS)
        if first_sheet is None:
            raise ValueError(f"No worksheets found in {path}")
        target = target_by_id[first_sheet.attrib[f"{{{NS['r']}}}id"]]
        sheet_path = target.lstrip("/")
        if not sheet_path.startswith("xl/"):
            sheet_path = f"xl/{sheet_path}"

        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = [
                "".join(text.text or "" for text in item.findall(".//m:t", NS))
                for item in shared_root.findall("m:si", NS)
            ]

        sheet = ElementTree.fromstring(archive.read(sheet_path))
        rows = sheet.findall(".//m:sheetData/m:row", NS)
        if not rows:
            raise ValueError(f"No rows found in worksheet {first_sheet.attrib['name']}")

        def decode_cell(cell: ElementTree.Element) -> Any:
            value_node = cell.find("m:v", NS)
            value = value_node.text if value_node is not None else ""
            cell_type = cell.attrib.get("t")
            if cell_type == "s":
                return shared_strings[int(value)]
            if cell_type == "inlineStr":
                return "".join(text.text or "" for text in cell.findall(".//m:t", NS))
            if cell_type in {"str", "e"}:
                return value
            return value

        def column_index(reference: str) -> int:
            letters = re.match(r"[A-Z]+", reference)
            if letters is None:
                raise ValueError(f"Invalid worksheet cell reference: {reference}")
            index = 0
            for char in letters.group():
                index = index * 26 + ord(char) - ord("A") + 1
            return index - 1

        header_cells = rows[0].findall("m:c", NS)
        headers: list[str] = []
        for cell in header_cells:
            while len(headers) <= column_index(cell.attrib["r"]):
                headers.append("")
            headers[column_index(cell.attrib["r"])] = str(decode_cell(cell)).strip()

        records: list[dict[str, Any]] = []
        for row in rows[1:]:
            values: list[Any] = [""] * len(headers)
            for cell in row.findall("m:c", NS):
                index = column_index(cell.attrib["r"])
                if index < len(values):
                    values[index] = decode_cell(cell)
            if any(value != "" for value in values):
                records.append(dict(zip(headers, values, strict=True)))
        return records


def decimal_value(value: Any, column: str, row_number: int) -> Decimal:
    try:
        return Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(
            f"Invalid numeric value for {column} on source row {row_number}: {value!r}"
        ) from error


def excel_date(value: Any, row_number: int) -> date:
    try:
        return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(
            f"Invalid Excel date on source row {row_number}: {value!r}"
        ) from error


def csv_value(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty table: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(
            {key: csv_value(value) for key, value in row.items()} for row in rows
        )


def build_tables(source: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    required = {
        "Segment", "Country", "Product", "Discount Band", "Units Sold",
        "Manufacturing Price", "Sale Price", "Gross Sales", "Discounts",
        "Sales", "COGS", "Profit", "Date",
    }
    missing = required - (set(source[0]) if source else set())
    if missing:
        raise ValueError(f"Financial Sample is missing required columns: {sorted(missing)}")

    records: list[dict[str, Any]] = []
    for row_number, source_row in enumerate(source, start=2):
        records.append(
            {
                "SourceRowID": row_number - 1,
                "Date": excel_date(source_row["Date"], row_number),
                "Product": str(source_row["Product"]).strip(),
                "Country": str(source_row["Country"]).strip(),
                "Segment": str(source_row["Segment"]).strip(),
                "DiscountBand": str(source_row["Discount Band"]).strip() or "Unspecified",
                "UnitsSold": decimal_value(source_row["Units Sold"], "Units Sold", row_number),
                "ManufacturingPrice": decimal_value(
                    source_row["Manufacturing Price"], "Manufacturing Price", row_number
                ),
                "SalePrice": decimal_value(source_row["Sale Price"], "Sale Price", row_number),
                "GrossSales": decimal_value(source_row["Gross Sales"], "Gross Sales", row_number),
                "Discounts": decimal_value(source_row["Discounts"], "Discounts", row_number),
                "NetSales": decimal_value(source_row["Sales"], "Sales", row_number),
                "COGS": decimal_value(source_row["COGS"], "COGS", row_number),
                "Profit": decimal_value(source_row["Profit"], "Profit", row_number),
            }
        )
    if not records:
        raise ValueError("Financial Sample contains no sales rows.")

    dimensions: dict[str, list[dict[str, Any]]] = {}
    key_maps: dict[str, dict[str, int]] = {}
    for dimension, attribute, key_column, value_column in [
        ("DimProduct", "Product", "ProductKey", "ProductName"),
        ("DimCountry", "Country", "CountryKey", "CountryName"),
        ("DimSegment", "Segment", "SegmentKey", "SegmentName"),
        ("DimDiscountBand", "DiscountBand", "DiscountBandKey", "DiscountBand"),
    ]:
        values = sorted({str(row[attribute]) for row in records})
        key_maps[dimension] = {value: index for index, value in enumerate(values, start=1)}
        dimensions[dimension] = [
            {key_column: index, value_column: value}
            for index, value in enumerate(values, start=1)
        ]
    product_prices: dict[str, Decimal] = {}
    for row in records:
        product = str(row["Product"])
        price = row["ManufacturingPrice"]
        if product in product_prices and product_prices[product] != price:
            raise ValueError(f"Manufacturing price varies for product {product!r}")
        product_prices[product] = price
    for product_row in dimensions["DimProduct"]:
        product_row["ManufacturingPrice"] = product_prices[product_row["ProductName"]]

    min_date = min(row["Date"] for row in records)
    max_date = max(row["Date"] for row in records)
    calendar_rows: list[dict[str, Any]] = []
    current_date = min_date
    while current_date <= max_date:
        year_month_sort = current_date.year * 100 + current_date.month
        calendar_rows.append(
            {
                "DateKey": current_date.year * 10000 + current_date.month * 100 + current_date.day,
                "Date": current_date,
                "Year": current_date.year,
                "Quarter": f"Q{(current_date.month - 1) // 3 + 1}",
                "MonthNumber": current_date.month,
                "MonthName": current_date.strftime("%B"),
                "YearMonth": current_date.strftime("%Y-%m"),
                "YearMonthSort": year_month_sort,
            }
        )
        current_date += timedelta(days=1)
    dimensions["DimDate"] = calendar_rows

    fact_rows: list[dict[str, Any]] = []
    for fact_id, row in enumerate(records, start=1):
        fact_rows.append(
            {
                "FactRowID": fact_id,
                "DateKey": row["Date"].year * 10000 + row["Date"].month * 100 + row["Date"].day,
                "ProductKey": key_maps["DimProduct"][row["Product"]],
                "CountryKey": key_maps["DimCountry"][row["Country"]],
                "SegmentKey": key_maps["DimSegment"][row["Segment"]],
                "DiscountBandKey": key_maps["DimDiscountBand"][row["DiscountBand"]],
                "UnitsSold": row["UnitsSold"],
                "ManufacturingPrice": row["ManufacturingPrice"],
                "SalePrice": row["SalePrice"],
                "GrossSales": row["GrossSales"],
                "Discounts": row["Discounts"],
                "NetSales": row["NetSales"],
                "COGS": row["COGS"],
                "Profit": row["Profit"],
            }
        )
    dimensions["FactSales"] = fact_rows

    for name, rows in dimensions.items():
        write_csv(DATA_DIR / f"{name}.csv", rows)
    return dimensions


def shared_expressions() -> dict[str, str]:
    source = POWER_QUERY.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^shared\s+([A-Za-z_]\w*)\s*=", source))
    expressions: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        body = source[match.end():end].strip()
        if body.endswith(";"):
            body = body[:-1].rstrip()
        expressions[match.group(1)] = body
    required = {"CsvTable", *(table["query"] for table in TABLES.values())}
    missing = required - expressions.keys()
    if missing:
        raise ValueError(f"Missing Power Query definitions: {sorted(missing)}")
    data_folder = str(DATA_DIR.resolve()).replace('"', '""')
    expressions["DataFolder"] = (
        f'"{data_folder}" meta [IsParameterQuery = true, Type = "Text", '
        "IsParameterQueryRequired = true]"
    )
    return expressions


def query_m(query_name: str, expressions: dict[str, str]) -> str:
    query_names = [
        name for name in expressions if name not in {"DataFolder", "CsvTable"}
    ]
    lines = ["let"]
    lines.extend(f"    {name} = {expressions[name]}," for name in query_names)
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
        MODEL_DIR / "definition.pbism",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.0",
            "settings": {},
        },
    )
    write_json(
        MODEL_DIR / ".platform",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "SemanticModel", "displayName": "SalesStarSchema"},
            "config": {"version": "2.0", "logicalId": str(uuid.uuid4())},
        },
    )
    (definition / "database.tmdl").write_text(
        "database SalesStarSchema\n\tcompatibilityLevel: 1600\n\tlanguage: 1033\n",
        encoding="utf-8",
    )
    model = [
        "model SalesStarSchema\n",
        "\tculture: en-US\n",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n",
        "\tdiscourageImplicitMeasures\n",
        "\tsourceQueryCulture: en-US\n",
        "\tdataAccessOptions\n",
        "\t\tlegacyRedirects\n",
        "\t\treturnErrorValuesAsNull\n\n",
        "queryGroup Parameters\n\tannotation PBI_QueryGroupOrder = 0\n\n",
        "queryGroup Tables\n\tannotation PBI_QueryGroupOrder = 1\n\n",
        "".join(f"ref table {name}\n" for name in TABLES),
        "\n",
    ]
    for from_table, from_column, to_table, to_column in RELATIONSHIPS:
        model.extend(
            [
                f"relationship {from_table}_{to_table}_{from_column}\n",
                f"\tfromColumn: {from_table}.{from_column}\n",
                f"\ttoColumn: {to_table}.{to_column}\n",
                "\tcrossFilteringBehavior: oneDirection\n",
                "\tisActive: true\n\n",
            ]
        )
    (definition / "model.tmdl").write_text(
        "".join(model).rstrip() + "\n", encoding="utf-8"
    )

    expression_blocks: list[str] = []
    for name in ("DataFolder", "CsvTable"):
        body = expressions[name]
        expression_blocks.append(
            f"expression {name} =\n"
            + "".join(f"\t\t{line}\n" for line in body.splitlines())
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
            lines.extend(
                [
                    "\tmeasure 'Total Sales' = SUM(FactSales[NetSales])\n",
                    "\t\tformatString: $#,##0;($#,##0);-\n",
                    "\t\tlineageTag: " + str(uuid.uuid4()) + "\n\n",
                    "\tmeasure 'Gross Sales' = SUM(FactSales[GrossSales])\n",
                    "\t\tformatString: $#,##0;($#,##0);-\n",
                    "\t\tlineageTag: " + str(uuid.uuid4()) + "\n\n",
                    "\tmeasure 'Total Discounts' = SUM(FactSales[Discounts])\n",
                    "\t\tformatString: $#,##0;($#,##0);-\n",
                    "\t\tlineageTag: " + str(uuid.uuid4()) + "\n\n",
                    "\tmeasure 'Total Profit' = SUM(FactSales[Profit])\n",
                    "\t\tformatString: $#,##0;($#,##0);-\n",
                    "\t\tlineageTag: " + str(uuid.uuid4()) + "\n\n",
                    "\tmeasure 'Units Sold' = SUM(FactSales[UnitsSold])\n",
                    "\t\tformatString: #,##0.0\n",
                    "\t\tlineageTag: " + str(uuid.uuid4()) + "\n\n",
                    "\tmeasure 'Profit Margin %' = DIVIDE([Total Profit], [Total Sales])\n",
                    "\t\tformatString: 0.0%;(0.0%);-\n",
                    "\t\tlineageTag: " + str(uuid.uuid4()) + "\n\n",
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
            if column in {"Year", "MonthNumber", "YearMonthSort"}:
                lines.append("\t\tformatString: 0\n")
            elif column in {
                "ManufacturingPrice", "SalePrice", "GrossSales", "Discounts",
                "NetSales", "COGS", "Profit",
            }:
                lines.append("\t\tformatString: $#,##0.00;($#,##0.00);-\n")
            elif column == "UnitsSold":
                lines.append("\t\tformatString: #,##0.0\n")
            if table_name == "DimDate" and column == "YearMonth":
                lines.append("\t\tsortByColumn: YearMonthSort\n")
            lines.append("\n")
        query = query_m(table["query"], expressions)
        lines.extend(
            [
                f"\tpartition {table_name} = m\n",
                "\t\tmode: import\n",
                "\t\tqueryGroup: Tables\n",
                "\t\tsource = ```\n",
                "".join(f"\t\t\t{line}\n" for line in query.splitlines()),
                "\t\t\t```\n",
                "\n",
                "\tannotation PBI_ResultType = Table\n",
            ]
        )
        (table_dir / f"{table_name}.tmdl").write_text("".join(lines), encoding="utf-8")


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


def measure_projection(entity: str, name: str) -> dict[str, Any]:
    return {
        "field": {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": name,
            }
        },
        "queryRef": f"{entity}.{name}",
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
            (
                measure_projection(item["entity"], item["name"])
                if item.get("measure")
                else column_projection(item["entity"], item["name"])
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
            "metadata": {"type": "Report", "displayName": "SalesStarSchema"},
            "config": {"version": "2.0", "logicalId": str(uuid.uuid4())},
        },
    )
    write_json(
        REPORT_DIR / "definition.pbir",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {
                "byPath": {"path": "../SalesStarSchema.SemanticModel"}
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
            "displayName": "Painel de vendas",
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        },
    )
    sales = {"entity": "FactSales", "name": "Total Sales", "measure": True}
    profit = {"entity": "FactSales", "name": "Total Profit", "measure": True}
    units = {"entity": "FactSales", "name": "Units Sold", "measure": True}
    margin = {"entity": "FactSales", "name": "Profit Margin %", "measure": True}
    visuals = [
        visual(
            "card", "Vendas líquidas",
            {"Values": [sales]},
            {"x": 24, "y": 18, "z": 0, "height": 105, "width": 220, "tabOrder": 0},
        ),
        visual(
            "card", "Lucro total",
            {"Values": [profit]},
            {"x": 258, "y": 18, "z": 1, "height": 105, "width": 220, "tabOrder": 1},
        ),
        visual(
            "card", "Unidades vendidas",
            {"Values": [units]},
            {"x": 492, "y": 18, "z": 2, "height": 105, "width": 220, "tabOrder": 2},
        ),
        visual(
            "card", "Margem de lucro",
            {"Values": [margin]},
            {"x": 726, "y": 18, "z": 3, "height": 105, "width": 220, "tabOrder": 3},
        ),
        visual(
            "slicer", "Ano",
            {"Values": [{"entity": "DimDate", "name": "Year"}]},
            {"x": 968, "y": 18, "z": 4, "height": 105, "width": 130, "tabOrder": 4},
        ),
        visual(
            "slicer", "Segmento",
            {"Values": [{"entity": "DimSegment", "name": "SegmentName"}]},
            {"x": 1110, "y": 18, "z": 5, "height": 105, "width": 150, "tabOrder": 5},
        ),
        visual(
            "lineChart", "Tendência mensal de vendas",
            {
                "Category": [{"entity": "DimDate", "name": "YearMonth"}],
                "Y": [sales],
            },
            {"x": 24, "y": 140, "z": 6, "height": 250, "width": 620, "tabOrder": 6},
        ),
        visual(
            "donutChart", "Vendas por segmento",
            {
                "Category": [{"entity": "DimSegment", "name": "SegmentName"}],
                "Y": [sales],
            },
            {"x": 664, "y": 140, "z": 7, "height": 250, "width": 280, "tabOrder": 7},
        ),
        visual(
            "clusteredBarChart", "Lucro por país",
            {
                "Category": [{"entity": "DimCountry", "name": "CountryName"}],
                "Y": [profit],
            },
            {"x": 964, "y": 140, "z": 8, "height": 250, "width": 296, "tabOrder": 8},
        ),
        visual(
            "clusteredBarChart", "Vendas por produto",
            {
                "Category": [{"entity": "DimProduct", "name": "ProductName"}],
                "Y": [sales],
            },
            {"x": 24, "y": 410, "z": 9, "height": 280, "width": 920, "tabOrder": 9},
        ),
        visual(
            "treemap", "Vendas por faixa de desconto",
            {
                "Group": [{"entity": "DimDiscountBand", "name": "DiscountBand"}],
                "Values": [{"entity": "FactSales", "name": "NetSales"}],
            },
            {"x": 964, "y": 410, "z": 10, "height": 280, "width": 296, "tabOrder": 10},
        ),
    ]
    for item in visuals:
        visual_id = item["name"]
        write_json(
            page_dir / "visuals" / f"{visual_id}.Visual" / "visual.json",
            item,
        )


def main() -> None:
    source = read_financial_sample(SOURCE_XLSX)
    tables = build_tables(source)
    expressions = shared_expressions()
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    create_model(expressions)
    create_report()
    write_json(
        PROJECT_DIR / "SalesStarSchema.pbip",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": "SalesStarSchema.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    print(f"Read {len(source)} source rows from {SOURCE_XLSX}")
    for name, rows in tables.items():
        print(f"{name}: {len(rows)} rows")
    print(f"Created Power BI project: {PROJECT_DIR / 'SalesStarSchema.pbip'}")
    print(f"Model parameter DataFolder: {DATA_DIR.resolve()}")


if __name__ == "__main__":
    main()
