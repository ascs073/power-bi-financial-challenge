import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_csv(folder: str, file_name: str) -> list[dict[str, str]]:
    with (ROOT / "data" / folder / file_name).open(
        encoding="utf-8", newline=""
    ) as stream:
        return list(csv.DictReader(stream))


class CompanySampleTests(unittest.TestCase):
    def test_source_row_counts(self) -> None:
        expected = {
            "employee.csv": 8,
            "dependent.csv": 7,
            "departament.csv": 3,
            "dept_locations.csv": 5,
            "project.csv": 6,
            "works_on.csv": 16,
        }
        for file_name, row_count in expected.items():
            with self.subTest(table=file_name):
                self.assertEqual(len(read_csv("raw", file_name)), row_count)

    def test_employee_merge_preserves_every_employee(self) -> None:
        employees = read_csv("processed", "Employees_Enriched.csv")
        self.assertEqual(len(employees), 8)
        self.assertTrue(all(row["DepartmentMatch"] == "True" for row in employees))
        self.assertEqual(
            sum(not row["SupervisorSSN"] for row in employees),
            1,
        )
        self.assertTrue(
            any(
                row["EmployeeName"] == "James Borg"
                and row["ManagerName"] == "(Sem gerente - CEO)"
                for row in employees
            )
        )

    def test_department_location_key_is_unique(self) -> None:
        rows = read_csv("processed", "Department_Locations.csv")
        keys = [row["DepartmentLocationKey"] for row in rows]
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(keys), len(set(keys)))

    def test_project_hours_are_aggregated_without_dropping_zero_assignment(self) -> None:
        rows = read_csv("processed", "Projects_Hours.csv")
        self.assertEqual(len(rows), 6)
        self.assertEqual(sum(float(row["TotalHours"]) for row in rows), 275.0)
        self.assertEqual(
            sum(float(row["TotalHours"]) == 0 for row in rows),
            0,
        )
        assignments = read_csv("raw", "works_on.csv")
        self.assertEqual(sum(float(row["Hours"]) == 0 for row in assignments), 1)

    def test_manager_groups_and_quality_findings(self) -> None:
        manager_groups = read_csv("processed", "Employees_By_Manager.csv")
        self.assertEqual(sum(int(row["DirectReports"]) for row in manager_groups), 8)
        self.assertEqual(len(manager_groups), 4)
        self.assertTrue(all(row["ManagerSSN"] for row in manager_groups))
        self.assertEqual(
            sum(row["IsTopLevelEmployee"] == "True" for row in manager_groups),
            1,
        )
        self.assertTrue(
            any(
                row["ManagerSSN"] == "__NO_SUPERVISOR__"
                and row["ManagerName"] == "(Sem gerente - CEO)"
                for row in manager_groups
            )
        )

        checks = {row["Check"]: row for row in read_csv("processed", "Quality_Checks.csv")}
        self.assertEqual(
            (checks["Employees with no supervisor"]["Observed"],
             checks["Employees with no supervisor"]["Status"]),
            ("1", "Expected"),
        )
        self.assertEqual(
            (checks["Departments without a valid manager"]["Observed"],
             checks["Departments without a valid manager"]["Status"]),
            ("0", "Pass"),
        )
        self.assertEqual(
            (checks["Malformed employee addresses"]["Observed"],
             checks["Malformed employee addresses"]["Status"]),
            ("0", "Pass"),
        )
        self.assertEqual(
            (checks["Project assignments with zero hours"]["Observed"],
             checks["Project assignments with zero hours"]["Status"]),
            ("1", "Review"),
        )

    def test_power_bi_project_pages_and_visual_fields(self) -> None:
        project_dir = ROOT / "CompanyTransformation"
        project = json.loads(
            (project_dir / "CompanyTransformation.pbip").read_text(encoding="utf-8")
        )
        report_artifact = next(
            artifact["report"]
            for artifact in project["artifacts"]
            if "report" in artifact
        )
        report_dir = project_dir / report_artifact["path"]
        report_link = json.loads(
            (report_dir / "definition.pbir").read_text(encoding="utf-8")
        )
        model_dir = (report_dir / report_link["datasetReference"]["byPath"]["path"]).resolve()
        pages = json.loads(
            (report_dir / "definition" / "pages" / "pages.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(len(pages["pageOrder"]), 2)
        self.assertTrue((model_dir / "definition.pbism").is_file())
        table_names = {
            path.stem
            for path in (model_dir / "definition" / "tables").glob("*.tmdl")
        }
        visual_count = 0
        for page_name in pages["pageOrder"]:
            page_dir = report_dir / "definition" / "pages" / f"{page_name}.Page"
            self.assertTrue((page_dir / "page.json").is_file())
            for visual_dir in (page_dir / "visuals").glob("*.Visual"):
                visual_path = visual_dir / "visual.json"
                visual = json.loads(visual_path.read_text(encoding="utf-8"))
                projections = visual["visual"]["query"]["queryState"]["Values"][
                    "projections"
                ]
                for projection in projections:
                    entity = projection["field"]["Column"]["Expression"][
                        "SourceRef"
                    ]["Entity"]
                    self.assertIn(entity, table_names)
                visual_count += 1
        self.assertEqual(visual_count, 5)


if __name__ == "__main__":
    unittest.main()
