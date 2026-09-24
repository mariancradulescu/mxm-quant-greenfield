import json
import pathlib
import unittest

from research_v3.session_gap_six_panel_outer_capture import EXPECTED_PLAN_SHA, EXPECTED_SYMBOLS, validate_outer_plan
from research_v3.pydroid_session_gap_six_panel_outer_launcher import local_preflight

ROOT=pathlib.Path(__file__).resolve().parents[1]

class SessionGapSixPanelOuterCaptureTests(unittest.TestCase):
    def test_outer_plan_is_disjoint_unopened_and_non_economic(self):
        p=json.loads((ROOT/"data/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_CAPTURE_PLAN_V1.json").read_text())
        self.assertEqual(p["plan_sha256"],EXPECTED_PLAN_SHA)
        self.assertTrue(validate_outer_plan(p))
        self.assertLess(p["outer_interval"]["end_utc"],p["source_wave01_interval"]["start_utc"])
        self.assertFalse(p["outer_contract"]["source_wave01_bytes_may_be_outer"])
        self.assertTrue(p["outer_contract"]["outer_unopened_before_freeze"])
        self.assertEqual(p["economic_outcomes_opened"],0)
        self.assertEqual(p["v2_attempts_consumed"],0)

    def test_fixed_panel_and_outer_window_are_exact(self):
        p=json.loads((ROOT/"data/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_CAPTURE_PLAN_V1.json").read_text())
        self.assertEqual({x["broker_symbol"]:int(x["symbol_id"]) for x in p["symbols"]},EXPECTED_SYMBOLS)
        self.assertEqual(p["outer_interval"],{"start_utc":"2026-03-30T00:00:00Z","end_utc":"2026-07-19T23:59:59Z"})
        self.assertEqual(p["resolution"],"M5")

    def test_friction_is_candidate_independent_and_historical(self):
        p=json.loads((ROOT/"data/SESSION_GAP_SIX_PANEL_INDEPENDENT_OUTER_CAPTURE_PLAN_V1.json").read_text())
        f=p["friction_authority"]
        self.assertEqual(f["method"],"V6_TRUE_INTRA_WINDOW_SPREAD_TAILS_PLUS_SAME_WINDOW_BROKER_NATIVE_COMMISSION_CONVERSION")
        self.assertFalse(f["raw_tick_transfer"])
        self.assertFalse(f["current_or_future_rate_substitution"])
        for d in f["sample_dates"]:
            self.assertGreaterEqual(d,"2026-03-30")
            self.assertLessEqual(d,"2026-07-19")

    def test_launcher_preflight_never_contacts_broker(self):
        r=local_preflight()
        self.assertEqual(r["symbols"],6); self.assertEqual(r["resolution"],"M5"); self.assertTrue(r["disjoint"])
        self.assertFalse(r["network_connection_attempted"]); self.assertFalse(r["credentials_used"])
        self.assertFalse(r["orders_permitted"]); self.assertFalse(r["account_mutation_permitted"])
        self.assertFalse(r["protected_evidence_opened"]); self.assertFalse(r["outer_outcome_opened"])
        self.assertFalse(r["economic_outcomes_opened"]); self.assertEqual(r["v2_attempts_consumed"],0)

    def test_supersession_happened_before_outer_outcome(self):
        d=json.loads((ROOT/"evidence/SESSION_GAP_SIX_PANEL_SAME_WAVE01_PROPOSAL_SUPERSESSION_V1.json").read_text())
        self.assertEqual(d["status"],"SUPERSEDED_BEFORE_ANY_OUTER_OUTCOME")
        self.assertFalse(d["material_conflict"]["same_wave01_outer_outcome_opened"])
        self.assertTrue(d["preserved"]["wave01_structural_report"])
        self.assertTrue(d["preserved"]["six_symbol_panel"])
        self.assertEqual(d["repair_effect"],{"economic_outcomes_opened":0,"v2_attempts_consumed":0})

if __name__=="__main__": unittest.main()
