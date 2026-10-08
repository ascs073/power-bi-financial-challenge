import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROJECT = ROOT / "ManagerialDashboard"


def read_csv(table_name: str) -> list[dict[str, str]]:
    with (DATA / f"{table_name}.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        return list(csv.DictReader(source))


class ManagerialDashboardTests(unittest.TestCase):
    def test_fact_grain_and_reference_totals(self) -> None:
        facts = read_csv("FactSales")
        self.assertEqual(len(facts), 700)
        self.assertEqual(len({row["FactRowID"] for row in facts}), 700)
        self.assertEqual(
            round(sum(float(row["NetSales"]) for row in facts), 2),
            118726350.26,
        )
        self.assertEqual(
            round(sum(float(row["Profit"]) for row in facts), 2),
            16893702.25,
        )
        self.assertEqual(
            round(sum(float(row["GrossSales"]) for row in facts)
                  - sum(float(row["Discounts"]) for row in facts), 2),
            118726350.26,
        )

    def test_foreign_keys_resolve_and_dimensions_are_unique(self) -> None:
        facts = read_csv("FactSales")
        relations = {
            "DateKey": ("DimDate", "DateKey"),
            "ProductKey": ("DimProduct", "ProductKey"),
            "CountryKey": ("DimCountry", "CountryKey"),
            "SegmentKey": ("DimSegment", "SegmentKey"),
            "DiscountBandKey": ("DimDiscountBand", "DiscountBandKey"),
        }
        for foreign_key, (dimension, primary_key) in relations.items():
            values = [row[primary_key] for row in read_csv(dimension)]
            with self.subTest(dimension=dimension):
                self.assertEqual(len(values), len(set(values)))
                self.assertTrue(all(row[foreign_key] in set(values) for row in facts))

    def test_star_relationships_and_measure_definitions(self) -> None:
        definition = PROJECT / "ManagerialDashboard.SemanticModel" / "definition"
        model = (definition / "model.tmdl").read_text(encoding="utf-8")
        self.assertEqual(model.count("\nrelationship "), 5)
        self.assertEqual(model.count("crossFilteringBehavior: oneDirection"), 5)
        self.assertEqual(model.count("isActive: true"), 5)

        dax = (ROOT / "DAX" / "Measures.dax").read_text(encoding="utf-8")
        fact_model = (
            definition / "tables" / "FactSales.tmdl"
        ).read_text(encoding="utf-8")
        expected_measures = (
            "Total Sales", "Gross Sales", "Total Profit", "Profit Margin %",
            "Units Sold", "Total Discounts", "Discount Rate %", "Sales per Unit",
            "Sales Previous Month", "Sales MoM Change", "Sales MoM Change %",
            "Sales Previous Year", "Sales YoY Change %", "Profit Previous Year",
            "Profit YoY Change %", "Profit Share %",
        )
        for measure in expected_measures:
            with self.subTest(measure=measure):
                self.assertIn(f"measure '{measure}'", fact_model)
                self.assertIn(f"{measure} =", dax)
        self.assertIn("SAMEPERIODLASTYEAR(DimDate[Date])", fact_model)
        self.assertIn("DATEADD(DimDate[Date], -1, MONTH)", fact_model)

    def test_report_has_three_named_pages_and_managerial_visuals(self) -> None:
        report = PROJECT / "ManagerialDashboard.Report"
        pages = json.loads(
            (report / "definition" / "pages" / "pages.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(pages["pageOrder"]), 3)
        display_names: list[str] = []
        all_visuals: list[dict[str, object]] = []
        page_identifiers: dict[str, str] = {}
        for page_id in pages["pageOrder"]:
            page_dir = report / "definition" / "pages" / f"{page_id}.Page"
            page = json.loads((page_dir / "page.json").read_text(encoding="utf-8"))
            display_names.append(page["displayName"])
            page_identifiers[page["displayName"]] = (
                "ReportSection" if page_id == pages["pageOrder"][0]
                else f"ReportSection{page_id}"
            )
            all_visuals.extend(
                json.loads(path.read_text(encoding="utf-8"))["visual"]
                for path in page_dir.glob("visuals/*.Visual/visual.json")
            )
        self.assertEqual(
            display_names,
            ["Resumo executivo", "Rentabilidade", "Mercados e portfólio"],
        )
        self.assertGreaterEqual(
            sum(visual["visualType"] == "card" for visual in all_visuals),
            12,
        )
        self.assertGreaterEqual(
            sum(visual["visualType"] == "slicer" for visual in all_visuals),
            5,
        )
        self.assertTrue(
            any(visual["visualType"] == "tableEx" for visual in all_visuals)
        )
        self.assertTrue(
            any(visual["visualType"] == "lineChart" for visual in all_visuals)
        )
        buttons = [
            visual for visual in all_visuals
            if visual["visualType"] == "actionButton"
        ]
        self.assertEqual(len(buttons), 9)
        for button in buttons:
            links = button["objects"]["visualLink"][0]["properties"]
            self.assertEqual(
                links["type"]["expr"]["Literal"]["Value"],
                "'PageNavigation'",
            )
            self.assertIn(
                links["navigationSection"]["expr"]["Literal"]["Value"].strip("'"),
                page_identifiers.values(),
            )

    def test_visual_fields_exist_in_the_model(self) -> None:
        definition = PROJECT / "ManagerialDashboard.SemanticModel" / "definition"
        table_columns: dict[str, set[str]] = {}
        for path in (definition / "tables").glob("*.tmdl"):
            text = path.read_text(encoding="utf-8")
            table_columns[path.stem] = {
                line.strip().split(maxsplit=1)[1]
                for line in text.splitlines()
                if line.startswith("\tcolumn ")
            }
        measures = {
            line.split("=", 1)[0].removeprefix("\tmeasure ").strip().strip("'")
            for line in (definition / "tables" / "FactSales.tmdl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.startswith("\tmeasure ")
        }
        page_list = json.loads(
            (PROJECT / "ManagerialDashboard.Report" / "definition" / "pages" / "pages.json")
            .read_text(encoding="utf-8")
        )
        for page_id in page_list["pageOrder"]:
            page_dir = (
                PROJECT / "ManagerialDashboard.Report" / "definition" / "pages"
                / f"{page_id}.Page"
            )
            for path in page_dir.glob("visuals/*.Visual/visual.json"):
                visual = json.loads(path.read_text(encoding="utf-8"))["visual"]
                for projections in visual["query"]["queryState"].values():
                    for projection in projections:
                        field = projection["field"]
                        if "Measure" in field:
                            source = field["Measure"]
                            self.assertIn(source["Property"], measures)
                        elif "Column" in field:
                            source = field["Column"]
                            entity = source["Expression"]["SourceRef"]["Entity"]
                            self.assertIn(source["Property"], table_columns[entity])


if __name__ == "__main__":
    unittest.main()
