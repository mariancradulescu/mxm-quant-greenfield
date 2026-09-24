import unittest
from pathlib import Path

from research_v3.broker_native_panel_screen import (
    CONSUMED_SYMBOLS,
    PanelScreenError,
    load_feasible_products,
    select_panel,
)


class BrokerNativePanelScreenTests(unittest.TestCase):
    def test_selects_disjoint_both_feasible_non_test_diverse_panel(self):
        products = {
            "AUDUSD": (1, "BOTH_FEASIBLE", False),
            "ADAUSD": (2, "BOTH_FEASIBLE", False),
            "AAPL.US": (3, "BOTH_FEASIBLE", False),
            "US500": (4, "BOTH_FEASIBLE", False),
            "TEST.US": (5, "BOTH_FEASIBLE", True),
            "EURUSD": (6, "BUY_ONLY", False),
        }
        result = select_panel(products, excluded_symbols={"AUDUSD"}, panel_size=3)
        symbols = [row["broker_symbol"] for row in result["selected_symbols"]]
        self.assertEqual(symbols, ["AAPL.US", "ADAUSD", "US500"])
        self.assertTrue(set(symbols).isdisjoint({"AUDUSD"}))
        self.assertEqual(result["policy"]["economic_outcomes_opened"], 0)

    def test_loads_repository_index_without_market_data(self):
        root = Path(__file__).resolve().parents[1]
        products = load_feasible_products(
            root / "data" / "PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_V1.json"
        )
        result = select_panel(products, panel_size=8)
        self.assertEqual(len(result["selected_symbols"]), 8)
        self.assertTrue(all(row["symbol_id"] > 0 for row in result["selected_symbols"]))
        self.assertTrue(
            set(row["broker_symbol"] for row in result["selected_symbols"]).isdisjoint(CONSUMED_SYMBOLS)
        )

    def test_rejects_insufficient_eligible_products(self):
        with self.assertRaises(PanelScreenError):
            select_panel({"X": (1, "BUY_ONLY", False)}, panel_size=1)


if __name__ == "__main__":
    unittest.main()
