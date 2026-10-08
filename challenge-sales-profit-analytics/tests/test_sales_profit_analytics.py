import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROJECT = ROOT / "SalesProfitAnalytics"


def read_csv(table: str) -> list[dict[str, str]]:
    with (DATA / f"{table}.csv").open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


class SalesProfitAnalyticsTests(unittest.TestCase):
    def test_fact_row_count_and_reference_totals(self) -> None:
        facts = read_csv("FactSales")
        self.assertEqual(len(facts), 700)
        self.assertEqual(len({row["FactRowID"] for row in facts}), 700)
        self.assertAlmostEqual(
            sum(float(row["NetSales"]) for row in facts),
            118726350.26,
            places=2,
        )
        self.assertAlmostEqual(
            sum(float(row["Profit"]) for row in facts),
            16893702.25,
            places=2,
        )
        self.assertAlmostEqual(
            sum(float(row["GrossSales"]) for row in facts)
            - sum(float(row["Discounts"]) for row in facts),
            118726350.26,
            places=2,
        )

    def test_dimension_keys_and_fact_foreign_keys(self) -> None:
        relationships = {
            "DateKey": ("DimDate", "DateKey"),
            "ProductKey": ("DimProduct", "ProductKey"),
            "CountryKey": ("DimCountry", "CountryKey"),
            "SegmentKey": ("DimSegment", "SegmentKey"),
            "DiscountBandKey": ("DimDiscountBand", "DiscountBandKey"),
        }
        facts = read_csv("FactSales")
        for fact_key, (table, primary_key) in relationships.items():
            dimension_rows = read_csv(table)
            dimension_keys = {row[primary_key] for row in dimension_rows}
            with self.subTest(dimension=table):
                self.assertEqual(len(dimension_keys), len(dimension_rows))
                self.assertTrue(all(row[fact_key] in dimension_keys for row in facts))

    def test_model_relationships_and_dax_measures(self) -> None:
        definition = PROJECT / "SalesProfitAnalytics.SemanticModel" / "definition"
        model = (definition / "model.tmdl").read_text(encoding="utf-8")
        self.assertEqual(model.count("\nrelationship "), 5)
        self.assertEqual(model.count("crossFilteringBehavior: oneDirection"), 5)
        self.assertEqual(model.count("isActive: true"), 5)
        fact = (
            definition / "tables" / "FactSales.tmdl"
        ).read_text(encoding="utf-8")
        dax = (ROOT / "DAX" / "Measures.dax").read_text(encoding="utf-8")
        expected = (
            "Total Sales", "Gross Sales", "Total Profit", "Profit Margin %",
            "Units Sold", "Total Discounts", "Discount Rate %", "Sales per Unit",
            "Sales Previous Month", "Sales MoM Change", "Sales MoM Change %",
            "Profit Previous Month", "Profit MoM Change %", "Sales Previous Year",
            "Sales YoY Change %", "Profit Previous Year", "Profit YoY Change %",
            "Profit Share %",
        )
        for name in expected:
            with self.subTest(measure=name):
                self.assertIn(f"measure '{name}'", fact)
                self.assertIn(f"{name} =", dax)

    def test_report_has_three_pages_and_navigable_buttons(self) -> None:
        report = PROJECT / "SalesProfitAnalytics.Report"
        pages = json.loads(
            (report / "definition" / "pages" / "pages.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(pages["pageOrder"]), 3)
        names: list[str] = []
        all_visuals: list[dict[str, object]] = []
        valid_targets = {
            "ReportSection",
            *(f"ReportSection{page_id}" for page_id in pages["pageOrder"][1:]),
        }
        for page_id in pages["pageOrder"]:
            page_dir = report / "definition" / "pages" / f"{page_id}.Page"
            page = json.loads((page_dir / "page.json").read_text(encoding="utf-8"))
            names.append(page["displayName"])
            all_visuals.extend(
                json.loads(path.read_text(encoding="utf-8"))["visual"]
                for path in page_dir.glob("visuals/*.Visual/visual.json")
            )
        self.assertEqual(names, ["Vendas", "Lucros", "Análise do período"])
        buttons = [
            visual for visual in all_visuals
            if visual["visualType"] == "actionButton"
        ]
        self.assertEqual(len(buttons), 9)
        for button in buttons:
            properties = button["objects"]["visualLink"][0]["properties"]
            self.assertEqual(
                properties["type"]["expr"]["Literal"]["Value"],
                "'PageNavigation'",
            )
            target = properties["navigationSection"]["expr"]["Literal"]["Value"]
            self.assertIn(target.strip("'"), valid_targets)

    def test_visual_fields_resolve_to_model_columns_and_measures(self) -> None:
        definition = PROJECT / "SalesProfitAnalytics.SemanticModel" / "definition"
        table_columns: dict[str, set[str]] = {}
        for path in (definition / "tables").glob("*.tmdl"):
            table_columns[path.stem] = {
                line.strip().split(maxsplit=1)[1]
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.startswith("\tcolumn ")
            }
        measures = {
            line.split("=", 1)[0].removeprefix("\tmeasure ").strip().strip("'")
            for line in (
                definition / "tables" / "FactSales.tmdl"
            ).read_text(encoding="utf-8").splitlines()
            if line.startswith("\tmeasure ")
        }
        pages = json.loads(
            (
                PROJECT / "SalesProfitAnalytics.Report" / "definition"
                / "pages" / "pages.json"
            ).read_text(encoding="utf-8")
        )
        for page_id in pages["pageOrder"]:
            page_dir = (
                PROJECT / "SalesProfitAnalytics.Report" / "definition"
                / "pages" / f"{page_id}.Page"
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
