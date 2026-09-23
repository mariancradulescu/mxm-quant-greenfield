import json, unittest
from pathlib import Path
from unittest.mock import patch
from discovery.canonical import verify_spec_hash
from discovery.ledger import read_ledger
from discovery.accounting import assert_current_state_matches_repository
from research_v3.lifecycle import candidate_lifecycle
from research_v3.wave05_execute import V3Wave05ExecutionNotAuthorized, execute_authorized

ROOT=Path(__file__).resolve().parents[1]
IDS=("V2-C029","V2-C030")
HASHES={"V2-C029":"fec1489eb0ae538497b7b70ef1c0ff6b47233fda24cce46a290922b4e713ce61","V2-C030":"1e6d96b8338867d38ef600acba6c218cee2ed020941e5e3a2695408eeb6c4a27"}

def load(rel): return json.loads((ROOT/rel).read_text(encoding="utf-8"))

class Wave05FreezeTests(unittest.TestCase):
    def test_specs_are_hash_valid_and_live_equivalent(self):
        for cid in IDS:
            s=load(f"discovery/candidates/{cid}.json")
            self.assertTrue(verify_spec_hash(s)); self.assertEqual(s["spec_hash"],HASHES[cid])
            self.assertTrue(s["causal_availability"]["future_information_forbidden"])
            self.assertFalse(s["position_admission_policy"]["future_exit_availability_may_affect_admission"])
            self.assertTrue(s["provenance"]["frozen_before_own_economic_outcome"])
            self.assertFalse(s["provenance"]["predecessor_outcome_opened"])
            self.assertFalse(s["provenance"]["protected_evidence_used"])

    def test_freeze_and_ledger_consume_zero_attempts(self):
        f=load("research_v3/WAVE_05_PRE_OUTCOME_FREEZE_V1.json")
        self.assertEqual(f["status"],"FROZEN_PENDING_EXACT_HEAD_GREEN")
        self.assertEqual(f["candidate_spec_hashes"],HASHES)
        self.assertEqual(f["new_attempts_consumed_by_freeze"],0)
        self.assertFalse(f["candidate_own_outcomes_opened"])
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        s=load("CURRENT_STATE.json")
        for cid,seq in (("V2-C029",63),("V2-C030",64)):
            lc=candidate_lifecycle(ledger,cid)
            freezes=[x for x in lc.freezes if x["entry_type"]=="CANDIDATE_FROZEN"]
            self.assertEqual(len(freezes),1)
            self.assertEqual(freezes[0]["sequence"],seq); self.assertEqual(freezes[0]["spec_hash"],HASHES[cid])
            self.assertLessEqual(len(lc.results),1)
        accounting=assert_current_state_matches_repository(ROOT)
        if s["performance_research_v3"]["wave05"]["candidate_own_outcomes_opened"]:
            self.assertEqual(s["v2_attempts_used"],18); self.assertEqual(s["v2_search_budget_remaining"],66)
            self.assertEqual(s["economic_outcomes_opened"],25)
            self.assertEqual(accounting["stage_a_result_recorded_entries"],23)
            self.assertEqual(accounting["distinct_identity_outcomes_opened"],18)
        else:
            self.assertEqual(s["v2_attempts_used"],16); self.assertEqual(s["v2_search_budget_remaining"],68)
            self.assertEqual(s["economic_outcomes_opened"],23)
            self.assertEqual(accounting["stage_a_result_recorded_entries"],21)
            self.assertEqual(accounting["distinct_identity_outcomes_opened"],16)
        self.assertEqual(s["discovery_ledger_entries"],len(ledger))

    def test_execution_gate_is_lifecycle_aware_and_rejects_wrong_head_before_economics(self):
        auth_path=ROOT/"research_v3/WAVE_05_EXECUTION_AUTHORIZATION_V1.json"
        with patch("research_v3.wave05_execute.execute_wave",side_effect=AssertionError("economics must not run")) as economic:
            if auth_path.exists():
                auth=load("research_v3/WAVE_05_EXECUTION_AUTHORIZATION_V1.json")
                self.assertEqual(auth["status"],"AUTHORIZED_AFTER_EXACT_HEAD_GREEN")
                self.assertEqual(auth["candidate_spec_hashes"],HASHES)
                self.assertFalse(auth["candidate_own_outcomes_opened"])
                with self.assertRaises(V3Wave05ExecutionNotAuthorized):
                    execute_authorized(ROOT,"missing.zip",execution_head="0"*40,execution_ci_run_id=0)
            else:
                with self.assertRaises(V3Wave05ExecutionNotAuthorized):
                    execute_authorized(ROOT,"missing.zip",execution_head="0"*40,execution_ci_run_id=0)
            economic.assert_not_called()

if __name__=="__main__": unittest.main(verbosity=2)
