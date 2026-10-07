import csv
import json
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROJECT = ROOT / "SalesStarSchema"


def read_csv(table: str) -> list[dict[str, str]]:
    with (DATA / f"{table}.csv").open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


class SalesStarSchemaTests(unittest.TestCase):
    def test_fact_grain_and_sales_totals(self) -> None:
        fact = read_csv("FactSales")
        self.assertEqual(len(fact), 700)
        self.assertEqual(len({row["FactRowID"] for row in fact}), len(fact))
        self.assertEqual(
            round(sum(float(row["NetSales"]) for row in fact), 2),
            round(sum(float(row["GrossSales"]) - float(row["Discounts"]) for row in fact), 2),
        )
        self.assertAlmostEqual(
            sum(float(row["Profit"]) for row in fact),
            sum(float(row["NetSales"]) - float(row["COGS"]) for row in fact),
            delta=0.02,
        )

    def test_all_fact_foreign_keys_resolve(self) -> None:
        fact = read_csv("FactSales")
        dimensions = {
            "DateKey": {row["DateKey"] for row in read_csv("DimDate")},
            "ProductKey": {row["ProductKey"] for row in read_csv("DimProduct")},
            "CountryKey": {row["CountryKey"] for row in read_csv("DimCountry")},
            "SegmentKey": {row["SegmentKey"] for row in read_csv("DimSegment")},
            "DiscountBandKey": {row["DiscountBandKey"] for row in read_csv("DimDiscountBand")},
        }
        for key, values in dimensions.items():
            with self.subTest(key=key):
                self.assertTrue(all(row[key] in values for row in fact))

    def test_dimension_keys_are_unique_and_date_calendar_is_continuous(self) -> None:
        key_by_table = {
            "DimDate": "DateKey",
            "DimProduct": "ProductKey",
            "DimCountry": "CountryKey",
            "DimSegment": "SegmentKey",
            "DimDiscountBand": "DiscountBandKey",
        }
        for table, key in key_by_table.items():
            with self.subTest(table=table):
                rows = read_csv(table)
                keys = [row[key] for row in rows]
                self.assertEqual(len(keys), len(set(keys)))
        expected_rows = {
            "DimDate": 457,
            "DimProduct": 6,
            "DimCountry": 5,
            "DimSegment": 5,
            "DimDiscountBand": 4,
        }
        for table, count in expected_rows.items():
            with self.subTest(table=table):
                self.assertEqual(len(read_csv(table)), count)
        dates = [row["Date"] for row in read_csv("DimDate")]
        self.assertEqual(len(dates), len(set(dates)))
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(
            len(dates),
            (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days + 1,
        )

    def test_model_has_star_relationships_and_measures(self) -> None:
        model_dir = PROJECT / "SalesStarSchema.SemanticModel" / "definition"
        model_text = (model_dir / "model.tmdl").read_text(encoding="utf-8")
        self.assertEqual(model_text.count("\nrelationship "), 5)
        for fact_key, dimension, dimension_key in (
            ("DateKey", "DimDate", "DateKey"),
            ("ProductKey", "DimProduct", "ProductKey"),
            ("CountryKey", "DimCountry", "CountryKey"),
            ("SegmentKey", "DimSegment", "SegmentKey"),
            ("DiscountBandKey", "DimDiscountBand", "DiscountBandKey"),
        ):
            with self.subTest(dimension=dimension):
                self.assertIn(f"fromColumn: FactSales.{fact_key}", model_text)
                self.assertIn(f"toColumn: {dimension}.{dimension_key}", model_text)
                self.assertIn("crossFilteringBehavior: oneDirection", model_text)
                self.assertIn("isActive: true", model_text)
        fact_model = (model_dir / "tables" / "FactSales.tmdl").read_text(encoding="utf-8")
        for measure in (
            "Total Sales", "Gross Sales", "Total Discounts",
            "Total Profit", "Units Sold", "Profit Margin %",
        ):
            self.assertIn(f"measure '{measure}'", fact_model)
        self.assertTrue((model_dir.parent / ".platform").is_file())

    def test_report_has_dashboard_visuals_and_slicers(self) -> None:
        report = PROJECT / "SalesStarSchema.Report"
        pages = json.loads(
            (report / "definition" / "pages" / "pages.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(pages["pageOrder"]), 1)
        page = report / "definition" / "pages" / f"{pages['pageOrder'][0]}.Page"
        visual_files = list(page.glob("visuals/*.Visual/visual.json"))
        self.assertEqual(len(visual_files), 11)
        visuals = [json.loads(path.read_text(encoding="utf-8"))["visual"] for path in visual_files]
        types = [item["visualType"] for item in visuals]
        self.assertEqual(types.count("card"), 4)
        self.assertEqual(types.count("slicer"), 2)
        self.assertIn("lineChart", types)
        self.assertIn("donutChart", types)
        self.assertGreaterEqual(types.count("clusteredBarChart"), 2)


if __name__ == "__main__":
    unittest.main()
