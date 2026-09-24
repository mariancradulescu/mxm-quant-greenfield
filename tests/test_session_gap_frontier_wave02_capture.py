import json
import unittest
from pathlib import Path

from m6.cost_evidence import DecodedTick
from m6.ctrader_capture import CaptureContractError
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
        rows = align_bid_ask_m5(
            [DecodedTick(0, 100000)], [DecodedTick(0, 110000)],
            start_utc="1970-01-01T00:00:00Z", end_utc="1970-01-01T00:05:00Z",
            symbol_id=9, broker_symbol="EURGBP",
        )
        self.assertAlmostEqual(float(rows[0]["spread"]), 0.1)
        self.assertEqual(tuple(rows[0]), HEADER)
        self.assertEqual(align_bid_ask_m5([DecodedTick(0, 100000)], [], start_utc="1970-01-01T00:00:00Z", end_utc="1970-01-01T00:05:00Z", symbol_id=9, broker_symbol="EURGBP"), [])

    def test_backward_pages_are_sorted_and_exact_duplicates_deduplicated(self):
        rows = align_bid_ask_m5(
            [DecodedTick(180000, 103000), DecodedTick(60000, 101000),
             DecodedTick(0, 100000), DecodedTick(0, 100000)],
            [DecodedTick(180000, 113000), DecodedTick(60000, 111000),
             DecodedTick(0, 110000), DecodedTick(0, 110000)],
            start_utc="1970-01-01T00:00:00Z", end_utc="1970-01-01T00:04:59Z",
            symbol_id=9, broker_symbol="EURGBP",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["bid_open"], rows[0]["bid_close"]), ("1.0", "1.03"))
        self.assertEqual((rows[0]["ask_open"], rows[0]["ask_close"]), ("1.1", "1.13"))
        self.assertEqual(rows[0]["tick_volume"], "6")

    def test_equal_timestamp_conflicting_prices_fail_closed(self):
        with self.assertRaisesRegex(CaptureContractError, "conflicting quote"):
            align_bid_ask_m5(
                [DecodedTick(0, 100000), DecodedTick(0, 100001)],
                [DecodedTick(0, 110000)],
                start_utc="1970-01-01T00:00:00Z", end_utc="1970-01-01T00:04:59Z",
                symbol_id=9, broker_symbol="EURGBP",
            )

    def test_only_two_sided_buckets_are_emitted(self):
        self.assertEqual(align_bid_ask_m5(
            [DecodedTick(0, 100000)], [DecodedTick(300000, 110000)],
            start_utc="1970-01-01T00:00:00Z", end_utc="1970-01-01T00:09:59Z",
            symbol_id=9, broker_symbol="EURGBP",
        ), [])

    def test_current_schedule_is_never_historical_authority(self):
        rows = align_bid_ask_m5(
            [DecodedTick(0, 100000)], [DecodedTick(0, 110000)],
            start_utc="1970-01-01T00:00:00Z", end_utc="1970-01-01T00:04:59Z",
            symbol_id=9, broker_symbol="EURGBP",
        )
        self.assertEqual(rows[0]["trading_session_metadata"], "CURRENT_ACCOUNT_SYMBOL_SCHEDULE_SNAPSHOT")


if __name__ == "__main__":
    unittest.main()
