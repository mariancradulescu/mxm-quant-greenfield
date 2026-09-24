import json, unittest
from pathlib import Path
from discovery.ledger import read_ledger
ROOT=Path(__file__).resolve().parents[1]
class ScopeGovernanceTests(unittest.TestCase):
    def test_consumed_scope_matrix_is_complete_and_family_open(self):
        reg=json.loads((ROOT/"evidence/MECHANISM_SCOPE_REGISTRY_V1.json").read_text())
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        ids=sorted({r["candidate_id"] for r in ledger if r.get("entry_type")=="RESULT_RECORDED" and str(r.get("candidate_id","")).startswith("V2-C")})
        rows={r["candidate_id"]:r for r in reg["rows"]}
        self.assertEqual(sorted(rows),ids)
        self.assertEqual(reg["consumed_identity_count"],len(ids))
        for cid in ids:
            spec=json.loads((ROOT/f"discovery/candidates/{cid}.json").read_text())
            self.assertEqual(rows[cid]["semantic_fingerprint"],spec["spec_hash"])
            self.assertEqual(rows[cid]["exact_symbol_universe"],spec["universe"])
            self.assertFalse(rows[cid]["mechanism_family_closed"])
    def test_universe_governor_does_not_equate_v6_with_full_universe(self):
        g=json.loads((ROOT/"data/AUTONOMOUS_UNIVERSE_GOVERNOR_V1.json").read_text())
        self.assertEqual(g["current_development_capture"]["symbol_count"],10)
        self.assertEqual(g["source_universe"]["accessible_symbols"],1690)
        self.assertEqual(g["source_universe"]["both_direction_eur200_feasible"],1609)
        self.assertTrue(g["diagnosis"]["research_universe_too_narrow_for_mechanism_level_inference"])
        self.assertFalse(g["constraints"]["blind_test_all_1600"])
        self.assertFalse(g["constraints"]["permanent_restriction_to_current_10"])
    def test_gate_is_closed_from_exact_head_green_and_capital_contract_is_simulation_only(self):
        s=json.loads((ROOT/"CURRENT_STATE.json").read_text())
        g=s["research_scope_governance"]
        self.assertEqual(g["status"],"EXACT_HEAD_GREEN")
        self.assertTrue(g["exact_head_green"])
        self.assertTrue(g["new_identity_creation_allowed"])
        self.assertEqual(g["exact_head_green_evidence"]["conclusion"],"SUCCESS")
        c=json.loads((ROOT/"data/CAPITAL_FLOW_AWARE_CAUSAL_GOVERNOR_V1.json").read_text())
        self.assertTrue(c["research_simulation_only"])
        self.assertFalse(c["live_order_logic"])
if __name__=="__main__": unittest.main(verbosity=2)
