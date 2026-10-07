from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "CompanyTransformation"
MODEL_DIR = PROJECT_DIR / "CompanyTransformation.SemanticModel"
REPORT_DIR = PROJECT_DIR / "CompanyTransformation.Report"
POWER_QUERY = ROOT / "PowerQuery" / "CompanyTransformations.pq"
RAW_DIR = ROOT / "data" / "raw"

TABLES = {
    "Employees": {
        "query": "Employees_Enriched",
        "columns": [
            ("EmployeeSSN", "string", "none", True),
            ("EmployeeName", "string", "none", False),
            ("FirstName", "string", "none", False),
            ("MiddleInitial", "string", "none", False),
            ("LastName", "string", "none", False),
            ("Bdate", "dateTime", "none", False),
            ("AddressNumber", "string", "none", False),
            ("Street", "string", "none", False),
            ("City", "string", "none", False),
            ("State", "string", "none", False),
            ("Sex", "string", "none", False),
            ("Salary", "decimal", "sum", False),
            ("SupervisorSSN", "string", "none", False),
            ("ManagerName", "string", "none", False),
            ("DepartmentNumber", "int64", "none", False),
            ("DepartmentName", "string", "none", False),
            ("DepartmentMatch", "boolean", "none", False),
        ],
    },
    "DepartmentLocations": {
        "query": "Department_Locations",
        "columns": [
            ("DepartmentLocationKey", "string", "none", True),
            ("DepartmentNumber", "int64", "none", False),
            ("DepartmentName", "string", "none", False),
            ("Location", "string", "none", False),
            ("DepartmentLocation", "string", "none", False),
            ("ManagerName", "string", "none", False),
        ],
    },
    "Projects": {
        "query": "Projects_Hours",
        "columns": [
            ("ProjectNumber", "int64", "none", True),
            ("ProjectName", "string", "none", False),
            ("ProjectLocation", "string", "none", False),
            ("DepartmentNumber", "int64", "none", False),
            ("DepartmentName", "string", "none", False),
            ("TotalHours", "decimal", "sum", False),
        ],
    },
    "EmployeesByManager": {
        "query": "Employees_By_Manager",
        "columns": [
            ("ManagerName", "string", "none", True),
            ("ManagerSSN", "string", "none", False),
            ("DirectReports", "int64", "sum", False),
            ("IsTopLevelEmployee", "boolean", "none", False),
        ],
    },
    "QualityChecks": {
        "query": "Quality_Checks",
        "columns": [
            ("Check", "string", "none", True),
            ("Observed", "int64", "sum", False),
            ("Expected", "string", "none", False),
            ("Status", "string", "none", False),
            ("Details", "string", "none", False),
        ],
    },
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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
    if not expressions:
        raise ValueError(f"No shared Power Query expressions found in {POWER_QUERY}.")
    data_folder = str(RAW_DIR.resolve()).replace('"', '""')
    expressions["DataFolder"] = (
        f'"{data_folder}" meta [IsParameterQuery = true, Type = "Text", '
        "IsParameterQueryRequired = true]"
    )
    return expressions


def table_partition_m(query_name: str, expressions: dict[str, str]) -> str:
    query_names = [
        name for name in expressions if name not in {"DataFolder", "CompanyCsv"}
    ]
    if query_name not in query_names:
        raise ValueError(f"Missing Power Query expression: {query_name}")

    lines = ["let"]
    for name in query_names:
        lines.append(f"    {name} = {expressions[name]},")
    lines.extend([f"    Result = {query_name}", "in", "    Result"])
    return "\n".join(lines)


def create_model(expressions: dict[str, str]) -> None:
    definition = MODEL_DIR / "definition"
    table_folder = definition / "tables"
    table_folder.mkdir(parents=True, exist_ok=True)
    (MODEL_DIR / "definition.pbism").write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
                "version": "4.0",
                "settings": {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (definition / "database.tmdl").write_text(
        "database CompanyTransformation\n"
        "\tcompatibilityLevel: 1600\n"
        "\tlanguage: 1033\n",
        encoding="utf-8",
    )
    (definition / "model.tmdl").write_text(
        "model CompanyTransformation\n"
        "\tculture: en-US\n"
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tdiscourageImplicitMeasures\n"
        "\tsourceQueryCulture: en-US\n"
        "\tdataAccessOptions\n"
        "\t\tlegacyRedirects\n"
        "\t\treturnErrorValuesAsNull\n"
        "\n"
        "queryGroup Parameters\n"
        "\tannotation PBI_QueryGroupOrder = 0\n"
        "\n"
        "queryGroup Tables\n"
        "\tannotation PBI_QueryGroupOrder = 1\n"
        "\n"
        + "".join(f"ref table {name}\n" for name in TABLES)
        + "\n",
        encoding="utf-8",
    )
    expression_text: list[str] = []
    for name in ("DataFolder", "CompanyCsv"):
        body = expressions[name]
        lineage = str(uuid.uuid4())
        expression_text.append(
            f"expression {name} =\n"
            + "".join(f"\t\t{line}\n" for line in body.splitlines())
            + f"\tlineageTag: {lineage}\n"
            f"\tqueryGroup: {'Parameters' if name == 'DataFolder' else 'Tables'}\n"
            f"\tannotation PBI_NavigationStepName = Navigation\n"
            f"\tannotation PBI_ResultType = {'Text' if name == 'DataFolder' else 'Function'}\n"
        )
    (definition / "expressions.tmdl").write_text(
        "\n".join(expression_text), encoding="utf-8"
    )

    for table_name, table in TABLES.items():
        lines = [f"table {table_name}\n", f"\tlineageTag: {uuid.uuid4()}\n\n"]
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
            if column == "Salary":
                lines.append("\t\tformatString: $#,##0.00;($#,##0.00)\n")
            elif column in ("TotalHours", "Observed", "DirectReports"):
                lines.append("\t\tformatString: #,##0.0\n" if column == "TotalHours" else "\t\tformatString: #,##0\n")
            lines.append("\n")
        query = table_partition_m(table["query"], expressions)
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
        (table_folder / f"{table_name}.tmdl").write_text(
            "".join(lines), encoding="utf-8"
        )


def projection(entity: str, field: str) -> dict[str, object]:
    return {
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": field,
            }
        },
        "queryRef": f"{entity}.{field}",
        "nativeQueryRef": field,
    }


def table_visual(name: str, entity: str, fields: list[str], position: dict[str, int]) -> dict[str, object]:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json",
        "name": uuid.uuid4().hex[:20],
        "position": position,
        "visual": {
            "visualType": "tableEx",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": [projection(entity, field) for field in fields]
                    }
                }
            },
            "drillFilterOtherVisuals": True,
            "objects": {
                "title": [
                    {
                        "properties": {
                            "show": {
                                "expr": {"Literal": {"Value": "true"}}
                            },
                            "text": {
                                "expr": {"Literal": {"Value": f"'{name}'"}}
                            },
                        }
                    }
                ]
            },
        },
    }


def create_report() -> None:
    report_definition = REPORT_DIR / "definition"
    pages_dir = report_definition / "pages"
    page1_id = uuid.uuid4().hex[:20]
    page2_id = uuid.uuid4().hex[:20]
    (REPORT_DIR / "definition.pbir").parent.mkdir(parents=True, exist_ok=True)
    write_json(
        REPORT_DIR / "definition.pbir",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {
                "byPath": {"path": "../CompanyTransformation.SemanticModel"}
            },
        },
    )
    write_json(
        report_definition / "version.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        },
    )
    write_json(
        report_definition / "report.json",
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
    write_json(
        pages_dir / "pages.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [page1_id, page2_id],
            "activePageName": page1_id,
        },
    )

    page_specs = [
        (
            page1_id,
            "Qualidade dos dados",
            [
                (
                    "Verificações e anomalias",
                    "QualityChecks",
                    ["Check", "Observed", "Expected", "Status", "Details"],
                    {"x": 28, "y": 56, "z": 0, "height": 300, "width": 1210, "tabOrder": 0},
                ),
                (
                    "Funcionários e relacionamentos",
                    "Employees",
                    ["EmployeeName", "ManagerName", "DepartmentName", "Salary", "DepartmentMatch"],
                    {"x": 28, "y": 380, "z": 1, "height": 285, "width": 1210, "tabOrder": 1},
                ),
            ],
        ),
        (
            page2_id,
            "Departamentos e projetos",
            [
                (
                    "Funcionários por gerente",
                    "EmployeesByManager",
                    ["ManagerName", "DirectReports", "IsTopLevelEmployee"],
                    {"x": 28, "y": 50, "z": 0, "height": 260, "width": 590, "tabOrder": 0},
                ),
                (
                    "Horas por projeto",
                    "Projects",
                    ["ProjectName", "DepartmentName", "ProjectLocation", "TotalHours"],
                    {"x": 650, "y": 50, "z": 1, "height": 260, "width": 590, "tabOrder": 1},
                ),
                (
                    "Dimensão departamento-local",
                    "DepartmentLocations",
                    ["DepartmentLocationKey", "DepartmentLocation", "ManagerName"],
                    {"x": 28, "y": 350, "z": 2, "height": 300, "width": 1210, "tabOrder": 2},
                ),
            ],
        ),
    ]
    for page_id, display_name, visuals in page_specs:
        page_folder = pages_dir / f"{page_id}.Page"
        write_json(
            page_folder / "page.json",
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
                "name": page_id,
                "displayName": display_name,
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280,
            },
        )
        for index, (title, entity, fields, position) in enumerate(visuals):
            visual = table_visual(title, entity, fields, position)
            visual_id = visual["name"]
            write_json(
                page_folder / "visuals" / f"{visual_id}.Visual" / "visual.json",
                visual,
            )


def main() -> None:
    if not RAW_DIR.is_dir():
        raise FileNotFoundError(
            f"Run build_dataset.py first; missing source CSV folder: {RAW_DIR}"
        )
    expressions = shared_expressions()
    missing = [
        table["query"]
        for table in TABLES.values()
        if table["query"] not in expressions
    ]
    if missing:
        raise ValueError(f"Power Query definitions missing: {', '.join(missing)}")

    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(
        PROJECT_DIR / "CompanyTransformation.pbip",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [
                {"report": {"path": "CompanyTransformation.Report"}}
            ],
            "settings": {"enableAutoRecovery": True},
        },
    )
    create_model(expressions)
    create_report()
    print(f"Created Power BI project: {PROJECT_DIR / 'CompanyTransformation.pbip'}")
    print(f"Model parameter DataFolder: {RAW_DIR.resolve()}")


if __name__ == "__main__":
    main()
