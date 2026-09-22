import json
import unittest
from datetime import datetime,timezone
from pathlib import Path
from competition.frontier_data_capture import EXPECTED_PLAN_SHA,canonical_plan_sha,normalize_m5,validate_plan
from competition.pydroid_frontier_data_launcher import local_preflight

ROOT=Path(__file__).resolve().parents[1]

class CompetitionFrontierDataCaptureTests(unittest.TestCase):
    def test_01_plan_hash_and_broad_scope(self):
        plan=json.loads((ROOT/"data"/"COMPETITION_FRONTIER_WAVE_01_V2_DATA_CAPTURE_PLAN.json").read_text())
        self.assertTrue(validate_plan(plan))
        self.assertEqual(canonical_plan_sha(plan),EXPECTED_PLAN_SHA)
        self.assertEqual(len(plan["symbols"]),16)
        self.assertEqual(plan["resolution"],"M5")
        self.assertEqual(plan["economic_outcomes_opened"],0)
        self.assertEqual(plan["v2_attempts_consumed"],0)
        self.assertFalse(plan["protected_evidence_opened"])

    def test_02_frontier_is_exhaustive_universe_successor_not_four_identity_cap(self):
        f=json.loads((ROOT/"discovery"/"COMPETITION_FRONTIER_WAVE_01_V2.json").read_text())
        self.assertEqual(f["supersedes"],"discovery/COMPETITION_FRONTIER_WAVE_01_V1.json")
        self.assertEqual(len(f["selected_markets"]),16)
        self.assertEqual(len(f["research_slots"]),12)
        self.assertFalse(f["selection_law"]["alpha_outcomes_used"])
        self.assertFalse(f["selection_law"]["existing_historical_data_defines_universe"])
        self.assertFalse(f["identity_accounting"]["old_arbitrary_max_new_identities_4_applies"])
        self.assertEqual(f["identity_accounting"]["economic_identities_opened"],0)

    def test_03_m5_normalization_is_completed_bar_causal(self):
        def minute(s):return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()//60)
        bars=[
          {"utcTimestampInMinutes":minute("2026-09-16T23:50:00Z"),"low":100000,"deltaOpen":10,"deltaHigh":20,"deltaClose":15,"volume":7},
          {"utcTimestampInMinutes":minute("2026-09-16T23:55:00Z"),"low":100000,"deltaOpen":10,"deltaHigh":20,"deltaClose":15,"volume":7},
          {"utcTimestampInMinutes":minute("2026-09-17T12:00:00Z"),"low":100000,"deltaOpen":10,"deltaHigh":20,"deltaClose":15,"volume":7},
        ]
        rows=normalize_m5(bars,digits=5,start_utc="2022-01-03T00:00:00Z",end_utc="2026-09-16T23:59:59Z",protected_utc="2026-09-17T12:02:58Z")
        self.assertEqual([x["time_utc"] for x in rows],["2026-09-16T23:50:00Z"])

    def test_04_no_credential_preflight_is_read_only(self):
        p=local_preflight()
        self.assertEqual(p["symbols"],16)
        self.assertEqual(p["resolution"],"M5")
        self.assertFalse(p["network_connection_attempted"])
        self.assertFalse(p["credentials_used"])
        self.assertFalse(p["orders_permitted"])
        self.assertFalse(p["account_mutation_permitted"])
        self.assertFalse(p["economic_outcomes_opened"])

    def test_05_acceptance_is_exhaustive_and_stopout_remains_unknown(self):
        a=json.loads((ROOT/"data"/"BROKER_NATIVE_COMPETITION_UNIVERSE_ACCEPTANCE_V2.json").read_text())
        self.assertEqual(a["inventory_integrity"]["current_symbol_count"],5324)
        self.assertEqual(a["inventory_integrity"]["current_new_entry_accessible_count"],1690)
        self.assertEqual(a["directional_feasibility"]["forex_spot_both_feasible"],93)
        self.assertEqual(a["margin_call_semantics"]["stop_out_margin_level"],"UNKNOWN_FOR_ACCOUNT_SPECIFIC_CERTIFICATION")
        self.assertFalse(a["account_identity"]["cryptographic_continuity_to_prior_capture_claimed"])
        self.assertEqual(a["account_identity"]["indirect_continuity_evidence"]["accepted_prior_product_identity_matches"],11)

if __name__=="__main__":unittest.main()
