import json
import unittest
from pathlib import Path
from competition.ultra_fast_capture import (
    EXPECTED_PLAN_SHA,friction_windows,margin_pct_eur200,qualify_friction,
    select_stage_a,validate_plan,
)
from competition.pydroid_ultra_fast_launcher import local_preflight

ROOT=Path(__file__).resolve().parents[1]

class UltraFastDataMinimalCompetitionTests(unittest.TestCase):
    def setUp(self):
        self.plan=json.loads((ROOT/"data"/"COMPETITION_ULTRA_FAST_CAPTURE_PLAN_V1.json").read_text())
        self.protocol=json.loads((ROOT/"data"/"COMPETITION_ULTRA_FAST_DISCOVERY_PROTOCOL_V1.json").read_text())

    def test_01_margin_percentage_factor_100_regression(self):
        self.assertEqual(margin_pct_eur200(33.33),16.665)
        self.assertEqual(margin_pct_eur200(29.05),14.525)
        self.assertEqual(margin_pct_eur200(2.53),1.265)
        self.assertEqual(margin_pct_eur200(0.14),0.07)
        self.assertTrue(validate_plan(self.plan,self.protocol))
        self.assertEqual(self.plan["plan_sha256"],EXPECTED_PLAN_SHA)
        for x in self.plan["shortlist"]:
            self.assertAlmostEqual(x["accepted_min_margin_pct_eur200"],x["accepted_min_margin_eur"]/2,places=9)

    def test_02_bug_scope_and_ranking_impact_are_fail_closed(self):
        law=self.protocol["margin_percentage_law"]
        self.assertFalse(law["exhaustive_structural_csv_affected"])
        self.assertFalse(law["structural_ranking_affected"])
        self.assertFalse(law["capital_efficiency_metric_affected"])
        self.assertTrue(law["frontier_v2_reporting_affected"])
        old=json.loads((ROOT/"discovery"/"COMPETITION_FRONTIER_WAVE_01_V2.json").read_text())
        self.assertEqual(old["selected_markets"][0]["min_margin_pct_eur200"],1666.5)
        v3=json.loads((ROOT/"discovery"/"COMPETITION_FRONTIER_WAVE_01_V3.json").read_text())
        self.assertEqual(v3["old_v2_frontier"]["state"],"SUPERSEDED_UNOPENED")
        self.assertEqual(len(v3["structural_shortlist"]),32)

    def test_03_recent_windows_and_escalation_are_exact(self):
        w=self.protocol["development_windows"]
        self.assertEqual(w["stage_a_latest_13_complete_iso_weeks"]["iso_weeks"],"2026-W25..2026-W37")
        self.assertEqual(w["latest_4_week_diagnostic"]["iso_weeks"],"2026-W34..2026-W37")
        self.assertEqual(w["stage_b_survivor_extension"]["combined_latest_26_weeks"],"2026-W12..2026-W37")
        self.assertEqual(w["stage_c_serious_survivor_extension"]["combined_latest_52_weeks"],"2025-W38..2026-W37")
        self.assertEqual(self.plan["stage_a_interval"],{"start_utc":"2026-06-15T00:00:00Z","end_utc":"2026-09-13T23:59:59Z"})
        self.assertFalse(self.plan["capture_law"]["full_shortlist_13_week_bar_download_permitted"])
        self.assertTrue(self.plan["capture_law"]["stage_a_m5_download_only_after_friction_selection"])

    def test_04_friction_sampling_is_bounded_and_stratified(self):
        self.assertEqual(len(friction_windows(self.protocol,"GLOBAL_24X5")),20)
        self.assertEqual(len(friction_windows(self.protocol,"CRYPTO_24X7")),28)
        self.assertEqual(len(friction_windows(self.protocol,"US_REGIONAL")),8)
        self.assertFalse(self.plan["capture_law"]["raw_tick_transfer_permitted"])
        self.assertEqual(self.plan["capture_law"]["max_tick_pages_per_side_window"],50)

    def test_05_qualification_thresholds(self):
        rules=self.protocol["friction_screen"]["qualification"]
        base={"two_sided_window_coverage":0.8,"quote_state_count":100,"median_m5_range":1.0,"p75_spread_over_median_range":0.2,"p95_spread_over_median_range":0.4,"median_spread_over_mid":0.001}
        self.assertEqual(qualify_friction(base,rules),"FRICTION_PASS")
        watch=dict(base,p75_spread_over_median_range=0.4,p95_spread_over_median_range=0.9)
        self.assertEqual(qualify_friction(watch,rules),"FRICTION_WATCH")
        fail=dict(base,p75_spread_over_median_range=0.8,p95_spread_over_median_range=1.2)
        self.assertEqual(qualify_friction(fail,rules),"FRICTION_FAIL")

    def test_06_selector_is_bounded_no_alpha_and_margin_aware(self):
        law=self.protocol["selection_law"]
        synthetic=[]
        for fam,quota in law["family_target_quotas"].items():
            for i in range(quota+2):
                synthetic.append({"broker_symbol":f"{fam}{i}","family":fam,"variant_family":f"{fam}{i}","friction_state":"FRICTION_PASS","movement_to_effective_p75_friction":10-i,"movement_to_p75_spread":10-i,"accepted_min_margin_pct_eur200":1+i,"schedule_minutes_per_week":7000-i,"p95_spread_over_median_range":0.2+i/100})
        chosen,_=select_stage_a(synthetic,law)
        self.assertEqual(len(chosen),12)
        counts={}
        for x in chosen:counts[x["family"]]=counts.get(x["family"],0)+1
        for fam,quota in law["family_target_quotas"].items():self.assertGreaterEqual(counts.get(fam,0),quota)

    def test_07_pydroid_preflight_has_no_network_or_economics(self):
        p=local_preflight()
        self.assertEqual(p["shortlist"],32)
        self.assertEqual(p["max_stage_a_markets"],12)
        self.assertEqual(p["global_windows"],20)
        self.assertEqual(p["crypto_windows"],28)
        self.assertFalse(p["raw_ticks_transferred"])
        self.assertFalse(p["network_connection_attempted"])
        self.assertFalse(p["credentials_used"])
        self.assertFalse(p["orders_permitted"])
        self.assertFalse(p["account_mutation_permitted"])
        self.assertFalse(p["economic_outcomes_opened"])

    def test_08_accounting_and_protection_remain_unchanged(self):
        s=json.loads((ROOT/"CURRENT_STATE.json").read_text())
        self.assertEqual(s["v2_search_budget"],84)
        self.assertEqual(s["v2_evaluated_identities"],2)
        self.assertEqual(s["v2_attempts_used"],2)
        self.assertFalse(s["protected_evidence_opened"])
        self.assertFalse(s["live_orders_authorized"])
        self.assertFalse(s["competition_start_authorized"])

if __name__=="__main__":unittest.main()
