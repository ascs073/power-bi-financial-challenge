from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SQL = ROOT / "source" / "company_seed.sql"
ORIGINAL_SEED_SQL = ROOT / "source" / "insercao_de_dados_e_queries_sql.sql"
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "data" / "processed"

SCHEMAS = {
    "employee": [
        "Fname", "Minit", "Lname", "Ssn", "Bdate", "Address",
        "Sex", "Salary", "Super_ssn", "Dno",
    ],
    "dependent": ["Essn", "Dependent_name", "Sex", "Bdate", "Relationship"],
    "departament": [
        "Dname", "Dnumber", "Mgr_ssn", "Mgr_start_date", "Dept_create_date",
    ],
    "dept_locations": ["Dnumber", "Dlocation"],
    "project": ["Pname", "Pnumber", "Plocation", "Dnum"],
    "works_on": ["Essn", "Pno", "Hours"],
}


def parse_sql_value(value: str) -> str:
    value = value.strip()
    if value.upper() == "NULL":
        return ""
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def parse_values(values: str) -> list[list[str]]:
    rows: list[list[str]] = []
    row: list[str] = []
    value: list[str] = []
    in_string = False
    depth = 0
    index = 0

    while index < len(values):
        char = values[index]
        if char == "'":
            if in_string and index + 1 < len(values) and values[index + 1] == "'":
                value.extend(("'", "'"))
                index += 2
                continue
            in_string = not in_string
            value.append(char)
        elif not in_string and char == "(":
            depth += 1
            if depth > 1:
                value.append(char)
        elif not in_string and char == ")":
            depth -= 1
            if depth == 0:
                row.append(parse_sql_value("".join(value)))
                rows.append(row)
                row, value = [], []
            else:
                value.append(char)
        elif not in_string and depth == 1 and char == ",":
            row.append(parse_sql_value("".join(value)))
            value = []
        elif depth:
            value.append(char)
        index += 1

    if in_string or depth:
        raise ValueError("Unterminated SQL string or row in INSERT statement.")
    return rows


def read_seed_tables() -> dict[str, list[dict[str, str]]]:
    if not SOURCE_SQL.exists():
        original = ORIGINAL_SEED_SQL.read_text(encoding="utf-8-sig")
        inserts = re.findall(
            r"insert\s+into\s+[a-z_]+\s+values\s*.*?;",
            original,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if len(inserts) != len(SCHEMAS):
            raise ValueError(
                f"Expected {len(SCHEMAS)} INSERT statements in the source SQL; "
                f"found {len(inserts)}."
            )
        SOURCE_SQL.write_text(
            "USE azure_company;\n\n"
            + "\n\n".join(statement.strip() for statement in inserts)
            + "\n",
            encoding="utf-8",
        )
    sql = SOURCE_SQL.read_text(encoding="utf-8-sig")
    tables: dict[str, list[dict[str, str]]] = {name: [] for name in SCHEMAS}
    insert = re.compile(
        r"insert\s+into\s+([a-z_]+)\s+values\s*(.*?);",
        flags=re.IGNORECASE | re.DOTALL,
    )

    for match in insert.finditer(sql):
        table = match.group(1).lower()
        if table not in SCHEMAS:
            continue
        for values in parse_values(match.group(2)):
            columns = SCHEMAS[table]
            if len(values) != len(columns):
                raise ValueError(
                    f"{table} row has {len(values)} values; expected {len(columns)}."
                )
            tables[table].append(dict(zip(columns, values)))

    missing = [name for name, rows in tables.items() if not rows]
    if missing:
        raise ValueError(f"Seed SQL is missing INSERT data for: {', '.join(missing)}")
    return tables


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def split_address(address: str) -> tuple[str, str, str, str, bool]:
    parts = address.split("-")
    if len(parts) == 4:
        return parts[0], parts[1], parts[2], parts[3], True
    if len(parts) == 5:
        return parts[0], f"{parts[1]} {parts[2]}", parts[3], parts[4], True
    padded = (parts + [""] * 4)[:4]
    return padded[0], padded[1], padded[2], padded[3], False


def build_outputs(tables: dict[str, list[dict[str, str]]]) -> dict[str, list[dict[str, object]]]:
    employees = tables["employee"]
    departments = tables["departament"]
    locations = tables["dept_locations"]
    projects = tables["project"]
    assignments = tables["works_on"]

    employee_by_ssn = {employee["Ssn"]: employee for employee in employees}
    department_by_number = {row["Dnumber"]: row for row in departments}
    employee_rows: list[dict[str, object]] = []
    manager_counts: Counter[str] = Counter()
    malformed_addresses = 0

    for employee in employees:
        address_number, street, city, state, address_is_valid = split_address(
            employee["Address"]
        )
        if not address_is_valid:
            malformed_addresses += 1

        supervisor = employee_by_ssn.get(employee["Super_ssn"])
        department = department_by_number.get(employee["Dno"])
        manager_name = (
            f"{supervisor['Fname']} {supervisor['Lname']}"
            if supervisor
            else "(Sem gerente - CEO)"
        )
        department_name = department["Dname"] if department else ""
        manager_counts[employee["Super_ssn"] or ""] += 1
        employee_rows.append(
            {
                "EmployeeSSN": employee["Ssn"],
                "EmployeeName": f"{employee['Fname']} {employee['Lname']}",
                "FirstName": employee["Fname"],
                "MiddleInitial": employee["Minit"],
                "LastName": employee["Lname"],
                "BirthDate": employee["Bdate"],
                "AddressNumber": address_number,
                "Street": street,
                "City": city,
                "State": state,
                "Sex": employee["Sex"],
                "Salary": Decimal(employee["Salary"]).quantize(Decimal("0.01")),
                "SupervisorSSN": employee["Super_ssn"],
                "ManagerName": manager_name,
                "DepartmentNumber": employee["Dno"],
                "DepartmentName": department_name,
                "DepartmentMatch": bool(department),
            }
        )

    department_locations: list[dict[str, object]] = []
    for location in locations:
        department = department_by_number[location["Dnumber"]]
        manager = employee_by_ssn.get(department["Mgr_ssn"])
        department_locations.append(
            {
                "DepartmentLocationKey": f"{department['Dnumber']}|{location['Dlocation']}",
                "DepartmentNumber": department["Dnumber"],
                "DepartmentName": department["Dname"],
                "Location": location["Dlocation"],
                "DepartmentLocation": f"{department['Dname']} - {location['Dlocation']}",
                "ManagerName": f"{manager['Fname']} {manager['Lname']}" if manager else "",
            }
        )

    hours_by_project: defaultdict[str, Decimal] = defaultdict(Decimal)
    zero_hour_assignments = 0
    invalid_hour_assignments = 0
    for assignment in assignments:
        hours = Decimal(assignment["Hours"])
        hours_by_project[assignment["Pno"]] += hours
        zero_hour_assignments += hours == 0
        invalid_hour_assignments += hours < 0

    project_rows: list[dict[str, object]] = []
    for project in projects:
        department = department_by_number[project["Dnum"]]
        project_rows.append(
            {
                "ProjectNumber": project["Pnumber"],
                "ProjectName": project["Pname"],
                "ProjectLocation": project["Plocation"],
                "DepartmentNumber": project["Dnum"],
                "DepartmentName": department["Dname"],
                "TotalHours": hours_by_project[project["Pnumber"]],
            }
        )

    manager_rows: list[dict[str, object]] = []
    for manager_ssn, count in manager_counts.items():
        manager = employee_by_ssn.get(manager_ssn)
        manager_rows.append(
            {
                "ManagerSSN": manager_ssn or "__NO_SUPERVISOR__",
                "ManagerName": f"{manager['Fname']} {manager['Lname']}" if manager else "(Sem gerente - CEO)",
                "DirectReports": count,
                "IsTopLevelEmployee": not manager_ssn,
            }
        )
    manager_rows.sort(key=lambda row: str(row["ManagerName"]))

    employees_without_department = sum(
        not bool(row["DepartmentMatch"]) for row in employee_rows
    )
    departments_without_manager = sum(
        not row["Mgr_ssn"] or row["Mgr_ssn"] not in employee_by_ssn
        for row in departments
    )
    missing_manager_links = sum(
        bool(row["SupervisorSSN"])
        and row["SupervisorSSN"] not in employee_by_ssn
        for row in employee_rows
    )
    duplicate_department_locations = len(department_locations) - len(
        {row["DepartmentLocationKey"] for row in department_locations}
    )
    salary_nulls = sum(not employee["Salary"] for employee in employees)
    checks = [
        {
            "Check": "Employees with no supervisor",
            "Observed": sum(not employee["Super_ssn"] for employee in employees),
            "Expected": "1 top-level employee (CEO)",
            "Status": "Expected",
            "Details": "James E. Borg is the CEO in the sample; a blank Super_ssn is intentional.",
        },
        {
            "Check": "Departments without a valid manager",
            "Observed": departments_without_manager,
            "Expected": 0,
            "Status": "Pass" if departments_without_manager == 0 else "Review",
            "Details": "All three departments have a manager present in the employee table.",
        },
        {
            "Check": "Employees without a matching department",
            "Observed": employees_without_department,
            "Expected": 0,
            "Status": "Pass" if employees_without_department == 0 else "Review",
            "Details": "Employee-to-department enrichment uses a left outer join.",
        },
        {
            "Check": "Employees with an invalid supervisor reference",
            "Observed": missing_manager_links,
            "Expected": 0,
            "Status": "Pass" if missing_manager_links == 0 else "Review",
            "Details": "The CEO's null supervisor is not an invalid reference.",
        },
        {
            "Check": "Employees with a null salary",
            "Observed": salary_nulls,
            "Expected": 0,
            "Status": "Pass" if salary_nulls == 0 else "Review",
            "Details": "Salary is kept as a fixed-precision decimal (currency).",
        },
        {
            "Check": "Malformed employee addresses",
            "Observed": malformed_addresses,
            "Expected": 0,
            "Status": "Pass" if malformed_addresses == 0 else "Review",
            "Details": "Addresses are split into number, street, city and state.",
        },
        {
            "Check": "Duplicate department-location combinations",
            "Observed": duplicate_department_locations,
            "Expected": 0,
            "Status": "Pass" if duplicate_department_locations == 0 else "Review",
            "Details": "Department number and location form the composite key.",
        },
        {
            "Check": "Project assignments with zero hours",
            "Observed": zero_hour_assignments,
            "Expected": "Review zero-hour assignments; do not discard silently",
            "Status": "Review" if zero_hour_assignments else "Pass",
            "Details": "A zero-hour assignment is retained because it is present in the source.",
        },
        {
            "Check": "Project assignments with negative hours",
            "Observed": invalid_hour_assignments,
            "Expected": 0,
            "Status": "Pass" if invalid_hour_assignments == 0 else "Review",
            "Details": "Negative hours would require confirmation from the data owner.",
        },
    ]

    return {
        "Employees_Enriched": employee_rows,
        "Department_Locations": department_locations,
        "Projects_Hours": project_rows,
        "Employees_By_Manager": manager_rows,
        "Quality_Checks": checks,
    }


def main() -> None:
    tables = read_seed_tables()
    for table, rows in tables.items():
        write_csv(RAW_DIR / f"{table}.csv", SCHEMAS[table], rows)

    outputs = build_outputs(tables)
    columns = {
        "Employees_Enriched": [
            "EmployeeSSN", "EmployeeName", "FirstName", "MiddleInitial",
            "LastName", "BirthDate", "AddressNumber", "Street", "City", "State",
            "Sex", "Salary", "SupervisorSSN", "ManagerName", "DepartmentNumber",
            "DepartmentName", "DepartmentMatch",
        ],
        "Department_Locations": [
            "DepartmentLocationKey", "DepartmentNumber", "DepartmentName",
            "Location", "DepartmentLocation", "ManagerName",
        ],
        "Projects_Hours": [
            "ProjectNumber", "ProjectName", "ProjectLocation",
            "DepartmentNumber", "DepartmentName", "TotalHours",
        ],
        "Employees_By_Manager": [
            "ManagerSSN", "ManagerName", "DirectReports",
            "IsTopLevelEmployee",
        ],
        "Quality_Checks": ["Check", "Observed", "Expected", "Status", "Details"],
    }
    for name, rows in outputs.items():
        write_csv(OUTPUT_DIR / f"{name}.csv", columns[name], rows)

    print(
        f"Built {sum(map(len, tables.values()))} source records and "
        f"{sum(map(len, outputs.values()))} transformed records."
    )
    for table, rows in tables.items():
        print(f"  raw/{table}.csv: {len(rows)} rows")
    for table, rows in outputs.items():
        print(f"  processed/{table}.csv: {len(rows)} rows")


if __name__ == "__main__":
    main()
