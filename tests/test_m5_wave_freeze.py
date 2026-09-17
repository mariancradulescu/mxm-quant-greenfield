import json, unittest
from pathlib import Path
from discovery.canonical import verify_spec_hash
from discovery.ledger import read_ledger
ROOT=Path(__file__).resolve().parents[1]
def load(p): return json.loads((ROOT/p).read_text(encoding="utf-8"))
class M5WaveFreeze(unittest.TestCase):
    def test_m5_01_wave_is_frozen_and_finite(self):
        w=load("discovery/WAVE_01_V1.json"); self.assertEqual(w["status"],"FROZEN_BEFORE_ANY_V2_ECONOMIC_OUTCOME"); self.assertEqual(len(w["candidate_ids"]),5); self.assertEqual(len(set(w["candidate_ids"])),5); self.assertEqual(w["economic_outcomes_opened"],0)
    def test_m5_02_candidates_validate_hashes_and_match_wave(self):
        w=load("discovery/WAVE_01_V1.json")
        for cid in w["candidate_ids"]:
            spec=load(f"discovery/candidates/{cid}.json"); self.assertTrue(verify_spec_hash(spec)); self.assertEqual(spec["spec_hash"],w["candidate_spec_hashes"][cid]); self.assertEqual(spec["cost_state"]["state"],"UNRESOLVED")
    def test_m5_03_materially_distinct_and_no_grid(self):
        w=load("discovery/WAVE_01_V1.json"); fam=w["materially_distinct_families"]; self.assertEqual(len(fam),5); self.assertEqual(len(set(fam)),5); self.assertEqual(set(fam),{"TREND_MOMENTUM","MEAN_REVERSION","BREAKOUT_VOLATILITY_EXPANSION","CROSS_SECTIONAL_RANKING","RELATIVE_VALUE_COINTEGRATION"})
    def test_m5_04_ledger_preserves_original_freezes_and_has_no_results(self):
        entries=read_ledger(ROOT/"discovery/ledger.jsonl"); freezes=[e for e in entries if e["entry_type"]=="CANDIDATE_FROZEN"]; self.assertEqual(len(freezes),5); self.assertEqual([e["sequence"] for e in freezes],[1,2,3,4,5]); self.assertFalse(any(e["entry_type"]=="RESULT_RECORDED" for e in entries))
    def test_m5_05_budget_and_protected_boundary_unchanged(self):
        w=load("discovery/WAVE_01_V1.json"); self.assertEqual(w["search_budget"],84); self.assertEqual(w["v2_attempts_used"],0); self.assertEqual(w["protected_forward_start"],"2026-09-17T12:02:58Z")
    def test_m5_06_state_complete_m6_pending_no_outcome(self):
        s=load("CURRENT_STATE.json"); self.assertEqual(s["phase"],"M5_COMPLETE"); self.assertEqual(s["m5"]["status"],"COMPLETE"); self.assertEqual(s["m6"]["status"],"PENDING"); self.assertEqual(s["v2_attempts_used"],0); self.assertEqual(s["v2_evaluated_identities"],0); self.assertIsNone(s["latest_economic_outcome"]); self.assertEqual(s["m5"]["result_entries"],0)
if __name__=="__main__": unittest.main(verbosity=2)
