import json
import math
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = [
    "HYPOTHESIS_SPACE_V1.json",
    "V2_SEARCH_BUDGET_V1.json",
    "DISCOVERY_COST_MODEL_V1.json",
    "V2_PROTECTED_FORWARD_START.json",
]

def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))

class M4FreezeAuthorities(unittest.TestCase):
    def test_m4_01_all_four_authorities_exist(self):
        self.assertEqual([name for name in AUTH if (ROOT / name).exists()], AUTH)
    def test_m4_02_budget_is_finite_and_unused(self):
        b = load("V2_SEARCH_BUDGET_V1.json")
        self.assertIsInstance(b["v2_budget"], int); self.assertGreater(b["v2_budget"], 0); self.assertTrue(math.isfinite(b["v2_budget"])); self.assertEqual(b["legacy_prior_attempts"], 16); self.assertEqual(b["v2_attempts_used"], 0); self.assertEqual(b["global_attempts_seen"], 16); self.assertEqual(b["derivation"]["total"], b["v2_budget"])
    def test_m4_03_no_v2_economic_result_opened(self):
        ledger = ROOT / "discovery" / "ledger.jsonl"; entries=[]
        for raw in ledger.read_text(encoding="utf-8").splitlines():
            if raw.strip(): entries.append(json.loads(raw))
        self.assertFalse(any(e.get("entry_type") == "RESULT_RECORDED" for e in entries)); self.assertEqual(len(entries), 0)
    def test_m4_04_protected_forward_is_valid_frozen_utc(self):
        p=load("V2_PROTECTED_FORWARD_START.json"); ts=p["V2_PROTECTED_FORWARD_START"]; self.assertTrue(ts.endswith("Z")); parsed=datetime.fromisoformat(ts.replace("Z", "+00:00")); self.assertEqual(parsed.tzinfo, timezone.utc); self.assertEqual(p["status"], "FROZEN_BEFORE_V2_ECONOMIC_OUTCOMES"); self.assertFalse(p["protected_evidence_opened"]); self.assertEqual(p["v2_economic_outcomes_opened_at_freeze"], 0)
    def test_m4_05_cost_states_and_promotion_rules(self):
        c=load("DISCOVERY_COST_MODEL_V1.json"); self.assertEqual(set(c["allowed_cost_confidence_states"]), {"VERIFIED","CONSERVATIVE_BOUND","UNRESOLVED"}); self.assertEqual({x["state"] for x in c["source_priority"]}, {"VERIFIED","CONSERVATIVE_BOUND","UNRESOLVED"}); self.assertFalse(c["screening_rules"]["gross_positive_is_sufficient"]); self.assertTrue(c["screening_rules"]["survivor_requires_credible_positive_coarse_net"]); self.assertEqual(c["screening_rules"]["sign_changing_reasonable_cost_uncertainty"], "COST_UNRESOLVED"); self.assertTrue(c["screening_rules"]["conservative_bound_false_promotion_forbidden"])
    def test_m4_06_hypothesis_space_is_finite_declarative_and_unanchored(self):
        h=load("HYPOTHESIS_SPACE_V1.json"); self.assertEqual(h["candidate_identities_instantiated_by_m4"], 0); self.assertGreaterEqual(len(h["dimensions"]), 9)
        for values in h["dimensions"].values(): self.assertIsInstance(values, list); self.assertGreater(len(values), 0); self.assertLess(len(values), 100)
        law=h["anti_anchor_law"]; self.assertTrue(law["proxy_not_universe"]); self.assertTrue(law["tested_identity_not_exhausted_market"]); self.assertTrue(law["failed_identity_not_failed_asset_class"])
    def test_m4_07_current_state_freeze(self):
        s=load("CURRENT_STATE.json"); self.assertEqual(s["phase"], "M4_COMPLETE"); self.assertEqual(s["m4"]["status"], "COMPLETE"); self.assertEqual(s["v2_search_budget"], 84); self.assertEqual(s["v2_attempts_used"], 0); self.assertEqual(s["v2_evaluated_identities"], 0); self.assertIsNone(s["latest_economic_outcome"]); self.assertEqual(s["m5"]["status"], "PENDING")
    def test_m4_08_protected_timestamp_matches_state(self):
        p=load("V2_PROTECTED_FORWARD_START.json"); s=load("CURRENT_STATE.json"); self.assertEqual(s["v2_protected_forward_start"], p["V2_PROTECTED_FORWARD_START"]); self.assertEqual(s["legacy_prior_attempts"], 16); self.assertEqual(s["global_attempts_seen"], 16)

if __name__ == "__main__": unittest.main(verbosity=2)
