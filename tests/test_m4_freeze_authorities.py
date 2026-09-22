import json
import math
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ["HYPOTHESIS_SPACE_V1.json","V2_SEARCH_BUDGET_V1.json","DISCOVERY_COST_MODEL_V1.json","V2_PROTECTED_FORWARD_START.json"]
def load(name): return json.loads((ROOT / name).read_text(encoding="utf-8"))
class M4FreezeAuthorities(unittest.TestCase):
    def test_m4_01_all_four_authorities_exist(self): self.assertEqual([n for n in AUTH if (ROOT/n).exists()],AUTH)
    def test_m4_02_budget_is_finite_and_unused_at_m4_freeze(self):
        b=load("V2_SEARCH_BUDGET_V1.json"); self.assertIsInstance(b["v2_budget"],int); self.assertGreater(b["v2_budget"],0); self.assertTrue(math.isfinite(b["v2_budget"])); self.assertEqual(b["legacy_prior_attempts"],16); self.assertEqual(b["v2_attempts_used"],0); self.assertEqual(b["global_attempts_seen"],16); self.assertEqual(b["derivation"]["total"],b["v2_budget"])
    def test_m4_03_no_v2_economic_result_opened(self):
        state = load("CURRENT_STATE.json")
        self.assertFalse(state["m4"]["candidate_economic_outcomes_opened"])
        self.assertEqual(state["m4"]["status"], "COMPLETE")
    def test_m4_04_protected_forward_is_valid_frozen_utc(self):
        p=load("V2_PROTECTED_FORWARD_START.json"); ts=p["V2_PROTECTED_FORWARD_START"]; self.assertTrue(ts.endswith("Z")); self.assertEqual(datetime.fromisoformat(ts.replace("Z","+00:00")).tzinfo,timezone.utc); self.assertEqual(p["status"],"FROZEN_BEFORE_V2_ECONOMIC_OUTCOMES"); self.assertFalse(p["protected_evidence_opened"]); self.assertEqual(p["v2_economic_outcomes_opened_at_freeze"],0)
    def test_m4_05_cost_states_and_promotion_rules(self):
        c=load("DISCOVERY_COST_MODEL_V1.json"); self.assertEqual(set(c["allowed_cost_confidence_states"]),{"VERIFIED","CONSERVATIVE_BOUND","UNRESOLVED"}); self.assertEqual({x["state"] for x in c["source_priority"]},{"VERIFIED","CONSERVATIVE_BOUND","UNRESOLVED"}); self.assertFalse(c["screening_rules"]["gross_positive_is_sufficient"]); self.assertTrue(c["screening_rules"]["survivor_requires_credible_positive_coarse_net"]); self.assertEqual(c["screening_rules"]["sign_changing_reasonable_cost_uncertainty"],"COST_UNRESOLVED"); self.assertTrue(c["screening_rules"]["conservative_bound_false_promotion_forbidden"])
    def test_m4_06_hypothesis_space_is_finite_declarative_and_unanchored(self):
        h=load("HYPOTHESIS_SPACE_V1.json"); self.assertEqual(h["candidate_identities_instantiated_by_m4"],0); self.assertGreaterEqual(len(h["dimensions"]),9)
        for values in h["dimensions"].values(): self.assertIsInstance(values,list); self.assertGreater(len(values),0); self.assertLess(len(values),100)
        law=h["anti_anchor_law"]; self.assertTrue(law["proxy_not_universe"]); self.assertTrue(law["tested_identity_not_exhausted_market"]); self.assertTrue(law["failed_identity_not_failed_asset_class"])
    def test_m4_07_current_state_preserves_m4_complete(self):
        state = load("CURRENT_STATE.json")
        self.assertEqual(state["m4"]["status"], "COMPLETE")
        self.assertEqual(state["v2_search_budget"], 84)
        self.assertEqual(state["v2_protected_forward_start"], "2026-09-17T12:02:58Z")
        self.assertFalse(state["m4"]["candidate_economic_outcomes_opened"])
        self.assertFalse(state["protected_evidence_opened"])
    def test_m4_08_protected_timestamp_matches_state(self):
        p=load("V2_PROTECTED_FORWARD_START.json"); b=load("V2_SEARCH_BUDGET_V1.json"); self.assertEqual(s["v2_protected_forward_start"],p["V2_PROTECTED_FORWARD_START"]); self.assertEqual(b["legacy_prior_attempts"],16); self.assertEqual(b["v2_attempts_used"],0); self.assertEqual(b["global_attempts_seen"],16)
    def test_m4_09_single_name_equity_coverage_correction_checkpoint(self):
        h=load("HYPOTHESIS_SPACE_V1.json"); classes=h["dimensions"]["market_asset_class"]; self.assertIn("SINGLE_NAME_EQUITY_OR_SHARE_CFD",classes); self.assertIn("EQUITY_INDEX",classes); self.assertEqual(load("V2_SEARCH_BUDGET_V1.json")["v2_budget"],84); self.assertEqual(load("V2_PROTECTED_FORWARD_START.json")["V2_PROTECTED_FORWARD_START"],"2026-09-17T12:02:58Z"); s=load("CURRENT_STATE.json"); self.assertEqual(s["m4"]["m4_1_correction"]["status"],"PASS"); self.assertEqual(s["m4"]["m4_1_correction"]["m5_status_at_correction"],"PENDING")
if __name__ == "__main__": unittest.main(verbosity=2)
