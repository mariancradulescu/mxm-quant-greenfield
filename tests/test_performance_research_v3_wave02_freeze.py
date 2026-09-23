import hashlib, json, unittest
from pathlib import Path
from unittest.mock import patch
from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.ledger import read_ledger
from research_v3.wave02_execute import V3Wave02ExecutionNotAuthorized, execute_authorized

ROOT=Path(__file__).resolve().parents[1]
IDS=("V2-C024","V2-C025")
HASHES={"V2-C024":"ae239c3db7908cf68e73170f2bc34c6b3039585d46b3fc7f6549db2fb5f98b04","V2-C025":"d357125ce183a2bd377c5c1b209e9ed7e382751042aa2b0162c6d88bd1efcf27"}
RESULT_REFS={"V2-C024":"discovery/results/V2-C024_STAGE_A_V1.json","V2-C025":"discovery/results/V2-C025_STAGE_A_V1.json"}
EXPECTED_STATUSES={"V2-C024":"GROSS_EDGE_FAIL","V2-C025":"COARSE_NET_FAIL"}
EVAL_SHA256="353e3f8895cf78c9f3113536f7049ce00359ca97e7359dd43bffa67f4d536ae4"
EVAL_BLOB="cfc1feabf0b8b251940d3e7b17f01d915bdc214a"
WRAPPER_BLOB="30d02649960c69d2b8629eead8d38c8cfde9b3ce"

def load(rel): return json.loads((ROOT/rel).read_text(encoding="utf-8"))
def blob_sha1(path):
    data=Path(path).read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

class PerformanceResearchV3Wave02FreezeTests(unittest.TestCase):
    def test_01_candidate_specs_are_frozen_and_hash_valid(self):
        for cid in IDS:
            spec=load(f"discovery/candidates/{cid}.json")
            self.assertTrue(verify_spec_hash(spec))
            self.assertEqual(spec["spec_hash"],HASHES[cid])
            self.assertTrue(spec["provenance"]["frozen_before_own_economic_outcome"])
            self.assertFalse(spec["provenance"]["protected_evidence_used"])

    def test_02_historical_freeze_and_code_bindings_are_immutable(self):
        wave=load("research_v3/WAVE_02_PRE_OUTCOME_FREEZE_V1.json")
        self.assertEqual(wave["status"],"FROZEN_PENDING_EXACT_HEAD_GREEN")
        self.assertEqual(wave["candidate_ids"],list(IDS))
        self.assertEqual(wave["candidate_spec_hashes"],HASHES)
        self.assertEqual(wave["evaluator"]["sha256"],EVAL_SHA256)
        self.assertEqual(wave["evaluator"]["git_blob_sha1"],EVAL_BLOB)
        self.assertEqual(hashlib.sha256((ROOT/wave["evaluator"]["ref"]).read_bytes()).hexdigest(),EVAL_SHA256)
        self.assertEqual(blob_sha1(ROOT/wave["evaluator"]["ref"]),EVAL_BLOB)
        self.assertEqual(blob_sha1(ROOT/"research_v3/wave02_execute.py"),WRAPPER_BLOB)
        self.assertEqual(wave["new_attempts_consumed_by_freeze"],0)
        self.assertFalse(wave["candidate_own_outcomes_opened"])

    def test_03_current_ledger_lifecycle_has_no_duplicates(self):
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        state=load("CURRENT_STATE.json")
        opened=state["performance_research_v3"]["wave02"]["candidate_own_outcomes_opened"]
        for cid in IDS:
            rows=[x for x in ledger if x.get("candidate_id")==cid]
            expected=["CANDIDATE_FROZEN","RESULT_RECORDED"] if opened else ["CANDIDATE_FROZEN"]
            self.assertEqual([x["entry_type"] for x in rows],expected)
        self.assertEqual(state["performance_research_v3"]["wave02"]["v2_attempts_used_before_wave02"],13)
        self.assertEqual(state["performance_research_v3"]["wave02"]["v2_search_budget_remaining_before_wave02"],71)
        if opened:
            self.assertEqual(state["v2_attempts_used"],4)
            self.assertLessEqual(state["v2_search_budget_remaining"],69)
            self.assertEqual(state["economic_outcomes_opened"],19)

    def test_04_authorization_rejects_wrong_gate_before_economics(self):
        auth=load("research_v3/WAVE_02_EXECUTION_AUTHORIZATION_V1.json")
        self.assertEqual(auth["status"],"AUTHORIZED_AFTER_EXACT_HEAD_GREEN")
        self.assertEqual(auth["execution_gate_head"],"09cf04c51d649da83a46b5a4d5ff373ae8abaff6")
        self.assertEqual(auth["execution_gate_ci_run_id"],35818302991)
        with patch("research_v3.wave02_execute.execute_wave",side_effect=AssertionError("economics must not run")) as economic:
            with self.assertRaises(V3Wave02ExecutionNotAuthorized):
                execute_authorized(ROOT,"missing.zip",execution_head="not-authorized",execution_ci_run_id=0)
            economic.assert_not_called()

    def test_05_persisted_results_and_ledger_payloads_are_canonical(self):
        state=load("CURRENT_STATE.json")
        wave02=state["performance_research_v3"]["wave02"]
        self.assertTrue(wave02["candidate_own_outcomes_opened"])
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        for cid in IDS:
            result=load(RESULT_REFS[cid])
            self.assertEqual(result["candidate_id"],cid)
            self.assertEqual(result["spec_hash"],HASHES[cid])
            self.assertEqual(result["status"],EXPECTED_STATUSES[cid])
            self.assertEqual(result["result_hash"],compute_result_hash(result))
            rec=[x for x in ledger if x["candidate_id"]==cid and x["entry_type"]=="RESULT_RECORDED"]
            self.assertEqual(len(rec),1)
            self.assertEqual(rec[0]["payload"]["result"],result)
            self.assertEqual(rec[0]["payload"]["result_hash"],result["result_hash"])
            self.assertEqual(wave02["result_hashes"][cid],result["result_hash"])
        self.assertEqual(wave02["v2_attempts_used_after_wave02"],15)
        self.assertEqual(wave02["v2_search_budget_remaining_after_wave02"],69)
        self.assertEqual(wave02["economic_attempt_delta"],2)
        self.assertEqual(wave02["persistence_additional_attempts_consumed"],0)
        self.assertEqual(wave02["stage_b_extension_candidates"],[])

    def test_06_current_lifecycle_preserves_exact_historical_wave02_accounting(self):
        state=load("CURRENT_STATE.json")
        wave02=state["performance_research_v3"]["wave02"]
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")

        # Historical Wave02 closure is immutable.
        self.assertEqual(wave02["v2_attempts_used_after_wave02"],15)
        self.assertEqual(wave02["v2_search_budget_remaining_after_wave02"],69)
        self.assertEqual(wave02["economic_outcomes_opened_after_wave02"],18)
        self.assertEqual(wave02["economic_attempt_delta"],2)
        self.assertEqual(wave02["persistence_additional_attempts_consumed"],0)
        self.assertEqual(wave02["result_statuses"],EXPECTED_STATUSES)

        # Current lifecycle may legitimately advance after Wave02.
        self.assertEqual(state["v2_evaluated_identities"],16)
        self.assertEqual(state["v2_search_budget_remaining"],84-state["v2_attempts_used"])
        self.assertEqual(state["global_attempts_seen"],state["legacy_prior_attempts"]+state["v2_evaluated_identities"])
        self.assertEqual(state["discovery_ledger_entries"],len(ledger))
        self.assertEqual(
            state["discovery_result_recorded_entries"],
            sum(x["entry_type"]=="RESULT_RECORDED" for x in ledger),
        )
        self.assertGreaterEqual(state["v2_attempts_used"],15)
        self.assertGreaterEqual(state["economic_outcomes_opened"],18)
        self.assertGreaterEqual(state["discovery_ledger_entries"],50)
        self.assertGreaterEqual(state["discovery_result_recorded_entries"],16)

        self.assertFalse(state["protected_evidence_opened"])
        self.assertFalse(state["live_orders_authorized"])
        self.assertFalse(state["competition_start_authorized"])

if __name__=="__main__": unittest.main(verbosity=2)
