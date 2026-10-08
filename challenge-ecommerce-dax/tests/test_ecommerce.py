import csv
import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROJECT = ROOT / "EcommerceDax"


def read_table(name: str) -> list[dict[str, str]]:
    with (DATA / f"{name}.csv").open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


class EcommerceDaxTests(unittest.TestCase):
    def test_synthetic_dataset_has_reproducible_grain_and_revenue(self) -> None:
        rows = read_table("FactSales")
        self.assertGreater(len(rows), 720)
        self.assertEqual(len({row["OrderItemKey"] for row in rows}), len(rows))
        self.assertEqual(len({row["OrderID"] for row in rows}), 720)
        self.assertLess(len({row["OrderID"] for row in rows}), len(rows))
        for row in rows:
            gross = Decimal(row["UnitPrice"]) * int(row["Quantity"])
            self.assertEqual(Decimal(row["GrossAmount"]), gross)
            self.assertEqual(
                Decimal(row["NetAmount"]),
                Decimal(row["GrossAmount"]) - Decimal(row["DiscountAmount"]),
            )
            self.assertEqual(
                Decimal(row["Profit"]),
                Decimal(row["NetAmount"]) - Decimal(row["UnitCost"]) * int(row["Quantity"]),
            )
        statuses = {
            row["OrderStatusKey"]: row["OrderStatus"]
            for row in read_table("DimOrderStatus")
        }
        valid = [
            row for row in rows
            if statuses[row["OrderStatusKey"]] not in {"Cancelado", "Reembolsado"}
        ]
        self.assertEqual(len({row["OrderID"] for row in valid}), 652)
        self.assertEqual(
            sum((Decimal(row["NetAmount"]) for row in valid), Decimal("0")),
            Decimal("3331162.90"),
        )
        self.assertEqual(
            sum((Decimal(row["Profit"]) for row in valid), Decimal("0")),
            Decimal("943741.90"),
        )

    def test_all_fact_foreign_keys_resolve(self) -> None:
        facts = read_table("FactSales")
        dimensions = {
            "DateKey": "DimDate",
            "ProductKey": "DimProduct",
            "CustomerKey": "DimCustomer",
            "PaymentMethodKey": "DimPaymentMethod",
            "OrderStatusKey": "DimOrderStatus",
            "GeographyKey": "DimGeography",
        }
        for fact_key, table in dimensions.items():
            keys = {row[fact_key] for row in read_table(table)}
            with self.subTest(dimension=table):
                self.assertTrue(all(row[fact_key] in keys for row in facts))
                self.assertEqual(len(keys), len(read_table(table)))

    def test_date_table_is_continuous_and_month_ordered(self) -> None:
        rows = read_table("DimDate")
        dates = [date.fromisoformat(row["Date"]) for row in rows]
        self.assertEqual(len(dates), 731)
        self.assertEqual(len(set(dates)), len(dates))
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(dates[0], date(2024, 1, 1))
        self.assertEqual(dates[-1], date(2025, 12, 31))
        self.assertEqual(
            sorted({int(row["YearMonthSort"]) for row in rows}),
            [year * 100 + month for year in (2024, 2025) for month in range(1, 13)],
        )

    def test_model_has_six_active_dimension_relationships_and_dax_measures(self) -> None:
        definition = PROJECT / "EcommerceDax.SemanticModel" / "definition"
        model_path = definition / "model.tmdl"
        model = model_path.read_text(encoding="utf-8")
        self.assertEqual(model.count("\nrelationship "), 6)
        self.assertEqual(model.count("crossFilteringBehavior: oneDirection"), 6)
        self.assertEqual(model.count("isActive: true"), 6)
        self.assertIn("fromColumn: FactSales.DateKey", model)
        self.assertIn("toColumn: DimDate.DateKey", model)
        fact = (definition / "tables" / "FactSales.tmdl").read_text(encoding="utf-8")
        dax_reference = (ROOT / "DAX" / "Measures.dax").read_text(encoding="utf-8")
        measures = (
            "Vendas Brutas", "Descontos", "Vendas Líquidas", "Pedidos",
            "Pedidos Válidos", "Ticket Médio", "Lucro", "Margem %",
            "Unidades Vendidas", "Clientes", "Pedidos Cancelados",
            "Taxa de Cancelamento", "Vendas Mês Anterior", "Variação Mensal %",
        )
        for measure in measures:
            with self.subTest(measure=measure):
                self.assertIn(f"measure '{measure}'", fact)
                self.assertIn(f"{measure} =", dax_reference)
        self.assertIn('KEEPFILTERS(DimOrderStatus[OrderStatus] <> "Cancelado")', fact)
        self.assertIn('KEEPFILTERS(DimOrderStatus[OrderStatus] <> "Reembolsado")', fact)
        self.assertIn("DISTINCTCOUNT(FactSales[OrderID])", fact)

    def test_report_contains_kpis_charts_and_filters(self) -> None:
        report = PROJECT / "EcommerceDax.Report"
        pages = json.loads(
            (report / "definition" / "pages" / "pages.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(pages["pageOrder"]), 1)
        page_dir = report / "definition" / "pages" / f"{pages['pageOrder'][0]}.Page"
        visuals = [
            json.loads(path.read_text(encoding="utf-8"))["visual"]
            for path in page_dir.glob("visuals/*.Visual/visual.json")
        ]
        self.assertEqual(len(visuals), 11)
        types = [visual["visualType"] for visual in visuals]
        self.assertEqual(types.count("card"), 4)
        self.assertEqual(types.count("slicer"), 2)
        self.assertIn("lineChart", types)
        self.assertIn("donutChart", types)
        self.assertIn("clusteredBarChart", types)
        self.assertIn("clusteredColumnChart", types)
        definition = PROJECT / "EcommerceDax.SemanticModel" / "definition"
        table_columns: dict[str, set[str]] = {}
        for path in (definition / "tables").glob("*.tmdl"):
            text = path.read_text(encoding="utf-8")
            table_columns[path.stem] = {
                line.strip().split(maxsplit=1)[1]
                for line in text.splitlines()
                if line.startswith("\tcolumn ")
            }
        fact_measures = {
            line.strip().split("=", 1)[0].removeprefix("measure ").strip().strip("'")
            for line in (definition / "tables" / "FactSales.tmdl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.startswith("\tmeasure ")
        }
        for visual in visuals:
            for role_projections in visual["query"]["queryState"].values():
                for projection in role_projections:
                    field = projection["field"]
                    if "Measure" in field:
                        entity = field["Measure"]["Expression"]["SourceRef"]["Entity"]
                        name = field["Measure"]["Property"]
                        self.assertEqual(entity, "FactSales")
                        self.assertIn(name, fact_measures)
                    elif "Column" in field:
                        entity = field["Column"]["Expression"]["SourceRef"]["Entity"]
                        name = field["Column"]["Property"]
                        self.assertIn(name, table_columns[entity])


if __name__ == "__main__":
    unittest.main()
