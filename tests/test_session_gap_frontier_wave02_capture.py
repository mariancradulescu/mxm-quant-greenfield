import json
import unittest
from pathlib import Path

from research_v3.session_gap_frontier_wave02_capture import (
    EXPECTED_SYMBOLS, HEADER, align_bid_ask_m5, validate_plan,
)

ROOT = Path(__file__).resolve().parents[1]


class FrontierWave02CaptureTests(unittest.TestCase):
    def test_exact_scope_and_bid_ask_fields_are_frozen(self):
        plan = json.loads((ROOT / "data/SESSION_GAP_FRONTIER_WAVE_02_M5_CAPTURE_PLAN_V1.json").read_text())
        self.assertTrue(validate_plan(plan))
        self.assertEqual({x["broker_symbol"]: x["symbol_id"] for x in plan["symbols"]}, EXPECTED_SYMBOLS)
        self.assertEqual(plan["resolution"], "M5")
        self.assertEqual(plan["fields"], [
            "timestamp_utc", "symbol_id", "broker_symbol", "bid_open", "bid_high",
            "bid_low", "bid_close", "ask_open", "ask_high", "ask_low", "ask_close",
            "tick_volume", "spread", "trading_session_metadata",
        ])

    def test_alignment_never_invents_missing_quote_side(self):
        class Tick:
            def __init__(self, timestamp_ms, price):
                self.timestamp_ms = timestamp_ms
                self.price = price
        rows = align_bid_ask_m5(
            [Tick(0, 1.0)], [Tick(0, 1.1)],
            start_utc="1970-01-01T00:00:00Z", end_utc="1970-01-01T00:05:00Z",
            symbol_id=9, broker_symbol="EURGBP",
        )
        self.assertAlmostEqual(float(rows[0]["spread"]), 0.1)
        self.assertEqual(tuple(rows[0]), HEADER)
        self.assertEqual(align_bid_ask_m5([Tick(0, 1.0)], [], start_utc="1970-01-01T00:00:00Z", end_utc="1970-01-01T00:05:00Z", symbol_id=9, broker_symbol="EURGBP"), [])


if __name__ == "__main__":
    unittest.main()
