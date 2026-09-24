import inspect, json, unittest
from pathlib import Path
from research_v3.session_gap_frontier_four_panel_outer_capture import (
    EXPECTED_PLAN_SHA, EXPECTED_SYMBOLS, build_outer_protocol, validate_outer_plan
)
from research_v3.pydroid_session_gap_frontier_four_panel_outer_launcher import local_preflight

ROOT=Path(__file__).resolve().parents[1]

class SessionGapFrontierFourPanelOuterCaptureTests(unittest.TestCase):
    def test_frozen_plan_binding(self):
        plan=json.loads((ROOT/"data/SESSION_GAP_FRONTIER_FOUR_PANEL_INDEPENDENT_OUTER_CAPTURE_PLAN_V1.json").read_text())
        self.assertEqual(plan["plan_sha256"],EXPECTED_PLAN_SHA)
        self.assertTrue(validate_outer_plan(plan))
        self.assertEqual(
            {x["broker_symbol"]:int(x["symbol_id"]) for x in plan["symbols"]},
            EXPECTED_SYMBOLS
        )
        self.assertEqual(list(EXPECTED_SYMBOLS),["ZARJPY","US400","XPDUSD","NETH25"])
        self.assertLess(plan["outer_interval"]["end_utc"],plan["source_development_interval"]["start_utc"])
        self.assertEqual((plan["economic_outcomes_opened"],plan["v2_attempts_consumed"]),(0,0))

    def test_outer_is_fixed_before_capture(self):
        freeze=json.loads((ROOT/"research_v3/SESSION_GAP_FRONTIER_FOUR_PANEL_FREEZE_V1.json").read_text())
        self.assertEqual(freeze["status"],"FROZEN_BEFORE_INDEPENDENT_OUTER_CAPTURE")
        self.assertEqual(freeze["selected_symbols"],["ZARJPY","US400","XPDUSD","NETH25"])
        self.assertEqual(freeze["confirmatory_outer"]["multiplicity"],"HOLM_BONFERRONI_ALPHA_0_05_ACROSS_EXACTLY_FOUR_FIXED_SYMBOLS")
        self.assertFalse(freeze["confirmatory_outer"]["development_bytes_may_be_outer"])

    def test_protocol_uses_frozen_global_windows(self):
        plan=json.loads((ROOT/"data/SESSION_GAP_FRONTIER_FOUR_PANEL_INDEPENDENT_OUTER_CAPTURE_PLAN_V1.json").read_text())
        base=json.loads((ROOT/"data/COMPETITION_ULTRA_FAST_DISCOVERY_PROTOCOL_V3.json").read_text())
        p=build_outer_protocol(plan,base)
        self.assertEqual(p["friction_screen"]["profiles"]["GLOBAL_24X5"]["sample_dates"],plan["friction_authority"]["sample_dates"])
        self.assertEqual(p["friction_screen"]["profiles"]["GLOBAL_24X5"]["utc_windows"],plan["friction_authority"]["GLOBAL_24X5_windows"])

    def test_preflight_read_only_and_disjoint(self):
        r=local_preflight()
        self.assertEqual((r["symbols"],r["resolution"]),(4,"M5"))
        self.assertTrue(r["disjoint"])
        self.assertFalse(r["network_connection_attempted"])
        self.assertFalse(r["credentials_used"])
        self.assertFalse(r["orders_permitted"])
        self.assertFalse(r["account_mutation_permitted"])
        self.assertFalse(r["protected_evidence_opened"])
        self.assertFalse(r["outer_outcome_opened"])
        self.assertFalse(r["economic_outcomes_opened"])
        self.assertEqual(r["v2_attempts_consumed"],0)

    def test_collector_has_no_order_requests(self):
        import research_v3.session_gap_frontier_four_panel_outer_capture as m
        s=inspect.getsource(m)
        for token in ("ProtoOANewOrderReq","ProtoOACancelOrderReq","ProtoOAClosePositionReq","ProtoOAAmendOrderReq"):
            self.assertNotIn(token,s)

if __name__=="__main__":
    unittest.main()
