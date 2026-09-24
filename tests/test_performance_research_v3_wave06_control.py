import json, unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

from discovery.canonical import verify_spec_hash
from discovery.ledger import read_ledger
from discovery.accounting import assert_current_state_matches_repository
from research_v3.lifecycle import candidate_lifecycle
from research_v3.wave06_execute import V3Wave06ExecutionNotAuthorized, execute_authorized
from m7.competition_performance_v3_wave06_c031_evaluator import gap_reversion_trades

ROOT=Path(__file__).resolve().parents[1]
CID="V2-C031"
SPEC_HASH="4a57910026bc8df63446fa8024ac86a18ce8a732039a9388f704a50bbccfc4e1"

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

def bar(t,o,c=None):
    c=o if c is None else c
    return {"t":t,"o":o,"h":max(o,c)*1.0001,"l":min(o,c)*0.9999,"c":c}

class Wave06ControlTests(unittest.TestCase):
    def test_spec_is_hash_valid_and_live_equivalent(self):
        spec=load("discovery/candidates/V2-C031.json")
        self.assertTrue(verify_spec_hash(spec))
        self.assertEqual(spec["spec_hash"],SPEC_HASH)
        self.assertTrue(spec["causal_availability"]["future_information_forbidden"])
        self.assertFalse(spec["position_admission_policy"]["future_entry_or_exit_availability_may_affect_signal_admission"])
        self.assertTrue(spec["provenance"]["frozen_before_own_economic_outcome"])
        self.assertFalse(spec["provenance"]["protected_evidence_used"])

    def test_state_machine_admits_before_future_fill_and_settles_at_first_observed_open(self):
        utc=timezone.utc; st=datetime(2026,6,15,tzinfo=utc)
        rows=[]; p=100.0
        for i in range(300):
            c=p*(1+(0.0001 if i%2==0 else -0.00008))
            rows.append(bar(st+i*timedelta(minutes=5),p,c)); p=c
        gap_t=rows[-1]["t"]+timedelta(minutes=60)
        gap_open=rows[-1]["c"]*1.01
        rows.append(bar(gap_t,gap_open,gap_open*.9995))
        p=gap_open*.999
        for k in range(1,21):
            t=gap_t+k*timedelta(minutes=5); c=p*.9998
            rows.append(bar(t,p,c)); p=c
        trades,diag=gap_reversion_trades({"X":rows},{"X":0.0001})
        self.assertEqual(diag["X"]["admitted_signals"],1)
        self.assertEqual(diag["X"]["filled_entries"],1)
        self.assertEqual(diag["X"]["settled_trades"],1)
        self.assertEqual(trades[0]["d"],"SHORT")
        self.assertEqual(trades[0]["e"],gap_t+timedelta(minutes=5))
        self.assertEqual(trades[0]["x"],trades[0]["e"]+timedelta(minutes=60))

    def test_freeze_consumes_zero_attempts_and_lifecycle_is_state_aware(self):
        freeze=load("research_v3/WAVE_06_PRE_OUTCOME_FREEZE_V1.json")
        self.assertEqual(freeze["status"],"FROZEN_PENDING_EXACT_HEAD_GREEN")
        self.assertEqual(freeze["candidate_spec_hashes"][CID],SPEC_HASH)
        self.assertEqual(freeze["new_attempts_consumed_by_freeze"],0)
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        lc=candidate_lifecycle(ledger,CID)
        freezes=[x for x in lc.freezes if x["entry_type"]=="CANDIDATE_FROZEN"]
        self.assertEqual(len(freezes),1)
        self.assertEqual(freezes[0]["spec_hash"],SPEC_HASH)
        self.assertLessEqual(len(lc.results),1)
        accounting=assert_current_state_matches_repository(ROOT)
        if lc.results:
            self.assertGreaterEqual(accounting["v2_attempts_used"],19)
            self.assertEqual(
                accounting["v2_search_budget_remaining"],
                accounting["v2_search_budget"]-accounting["v2_attempts_used"],
            )
            self.assertEqual(
                accounting["economic_outcomes_opened"],
                accounting["stage_a_result_recorded_entries"]+accounting["stage_b_current_config_economic_observations"],
            )
            self.assertGreaterEqual(accounting["economic_outcomes_opened"],26)
        else:
            self.assertLessEqual(accounting["v2_attempts_used"],18)
            self.assertEqual(accounting["economic_outcomes_opened"],25)

    def test_execution_gate_rejects_wrong_head_before_economics(self):
        with patch("research_v3.wave06_execute.execute_wave",side_effect=AssertionError("economics must not run")) as economic:
            with self.assertRaises(V3Wave06ExecutionNotAuthorized):
                execute_authorized(ROOT,"missing.zip",execution_head="0"*40,execution_ci_run_id=0)
            economic.assert_not_called()

if __name__=="__main__":
    unittest.main(verbosity=2)
