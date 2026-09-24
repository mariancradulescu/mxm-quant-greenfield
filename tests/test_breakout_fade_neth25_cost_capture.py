import copy
import json
import unittest
from datetime import timedelta
from pathlib import Path

from research_v3.breakout_fade_neth25_cost_capture import (
    COST_FIELDS,
    EXPECTED_PLAN_SHA,
    _boundary_window,
    validate_cost_plan,
)
from competition.ultra_fast_capture import _utc

ROOT=Path(__file__).resolve().parents[1]

class BreakoutFadeNeth25CostCaptureTests(unittest.TestCase):
    def setUp(self):
        self.plan=json.loads((ROOT/"data/BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_CAPTURE_PLAN_V1.json").read_text())

    def test_frozen_plan_and_preprotected_bounds(self):
        self.assertTrue(validate_cost_plan(self.plan))
        self.assertEqual(self.plan["plan_sha256"],EXPECTED_PLAN_SHA)
        self.assertEqual(self.plan["symbol"],{"broker_symbol":"NETH25","symbol_id":269,"family":"INDEX"})
        protected=_utc(self.plan["protected_forward_start"])
        latest=_utc(self.plan["event_analysis_interval"]["end_utc"])+timedelta(minutes=36)
        self.assertLess(latest,protected)

    def test_boundary_window_is_causal_and_bounded(self):
        boundary=_utc("2026-09-15T08:00:00Z")
        w=_boundary_window(boundary,300,60)
        self.assertEqual(w["boundary_utc"],"2026-09-15T08:00:00Z")
        self.assertEqual(w["start_utc"],"2026-09-15T07:55:00Z")
        self.assertEqual(w["end_utc"],"2026-09-15T08:01:00Z")

    def test_transfer_contract_has_no_price_levels_or_raw_ticks(self):
        transfer=self.plan["transfer_contract"]
        self.assertFalse(transfer["raw_ticks_transferred"])
        self.assertFalse(transfer["raw_conversion_ticks_transferred"])
        self.assertFalse(transfer["price_levels_transferred_in_cost_rows"])
        self.assertEqual(tuple(transfer["fields"]),COST_FIELDS)

    def test_plan_drift_fails_closed(self):
        bad=copy.deepcopy(self.plan)
        bad["event_law"]["volatility_expansion_ratio"]=1.6
        with self.assertRaisesRegex(Exception,"SHA mismatch"):
            validate_cost_plan(bad)

if __name__=="__main__":
    unittest.main()
