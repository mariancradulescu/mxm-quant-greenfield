import hashlib, json, unittest
from pathlib import Path
from unittest.mock import patch

from discovery.canonical import compute_result_hash, verify_spec_hash
from discovery.ledger import read_ledger
from research_v3.wave03_execute import V3Wave03ExecutionNotAuthorized, execute_authorized

ROOT=Path(__file__).resolve().parents[1]
CID="V2-C026"
SPEC_HASH="41880f453efd363da860024e8f9b7b299bd14b9f2367156779f3f193f9abc9e9"
EVAL_SHA256="29b250904fa4b3de8e4ce0292ab38332670e624cff9a01ab649ee831fffe057f"
EVAL_BLOB="7c07c1d39053baa1e31ed4eb3d552520d809ccd7"
WRAPPER_BLOB="747d522e23c1621bb138de4d8495973232c837e1"
RESULT_REF="discovery/results/V2-C026_STAGE_A_V1.json"

def load(rel): return json.loads((ROOT/rel).read_text(encoding="utf-8"))
def blob_sha1(path):
    data=Path(path).read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

class PerformanceResearchV3Wave03FreezeTests(unittest.TestCase):
    def test_01_c026_spec_is_frozen_and_hash_valid(self):
        spec=load("discovery/candidates/V2-C026.json")
        self.assertTrue(verify_spec_hash(spec))
        self.assertEqual(spec["spec_hash"],SPEC_HASH)
        self.assertEqual(spec["mechanism"]["family"],"SEASONALITY_SESSION_TIME")
        self.assertTrue(spec["provenance"]["frozen_before_own_economic_outcome"])
        self.assertFalse(spec["provenance"]["protected_evidence_used"])

    def test_02_historical_freeze_and_code_bindings_are_immutable(self):
        wave=load("research_v3/WAVE_03_PRE_OUTCOME_FREEZE_V1.json")
        self.assertEqual(wave["status"],"FROZEN_PENDING_EXACT_HEAD_GREEN")
        self.assertEqual(wave["candidate_ids"],[CID])
        self.assertEqual(wave["candidate_spec_hashes"][CID],SPEC_HASH)
        self.assertEqual(wave["evaluator"]["sha256"],EVAL_SHA256)
        self.assertEqual(wave["evaluator"]["git_blob_sha1"],EVAL_BLOB)
        self.assertEqual(hashlib.sha256((ROOT/wave["evaluator"]["ref"]).read_bytes()).hexdigest(),EVAL_SHA256)
        self.assertEqual(blob_sha1(ROOT/wave["evaluator"]["ref"]),EVAL_BLOB)
        self.assertEqual(blob_sha1(ROOT/"research_v3/wave03_execute.py"),WRAPPER_BLOB)
        self.assertEqual(blob_sha1(ROOT/wave["evaluator"]["base_reporting_dependency_ref"]),wave["evaluator"]["base_reporting_dependency_git_blob_sha1"])

        # Exact historical facts belong to the immutable Wave03 freeze authority,
        # never to mutable CURRENT_STATE.
        self.assertEqual(wave["accounting_before"]["v2_attempts_used"],15)
        self.assertEqual(wave["accounting_before"]["v2_search_budget_remaining"],69)
        self.assertEqual(wave["accounting_before"]["v2_evaluated_identities"],15)
        self.assertEqual(wave["accounting_before"]["economic_outcomes_opened"],18)
        self.assertEqual(wave["accounting_before"]["discovery_ledger_entries"],50)
        self.assertEqual(wave["accounting_before"]["discovery_result_recorded_entries"],16)
        self.assertEqual(wave["new_attempts_consumed_by_freeze"],0)
        self.assertFalse(wave["candidate_own_outcomes_opened"])

    def test_03_current_lifecycle_is_monotonic_and_duplicate_free(self):
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        state=load("CURRENT_STATE.json")
        wave03=state["performance_research_v3"]["wave03"]

        rows=[x for x in ledger if x.get("candidate_id")==CID]
        freezes=[x for x in rows if x["entry_type"]=="CANDIDATE_FROZEN"]
        results=[x for x in rows if x["entry_type"]=="RESULT_RECORDED"]
        self.assertEqual(len(freezes),1)
        self.assertLessEqual(len(results),1)
        self.assertEqual(freezes[0]["sequence"],51)
        self.assertEqual(freezes[0]["spec_hash"],SPEC_HASH)
        self.assertEqual(wave03["candidate_own_outcomes_opened"],len(results)==1)

        self.assertEqual(state["v2_evaluated_identities"],16)
        self.assertEqual(state["v2_search_budget_remaining"],84-state["v2_attempts_used"])
        self.assertEqual(state["global_attempts_seen"],state["legacy_prior_attempts"]+state["v2_evaluated_identities"])
        self.assertEqual(state["discovery_ledger_entries"],len(ledger))
        self.assertEqual(
            state["discovery_result_recorded_entries"],
            sum(x["entry_type"]=="RESULT_RECORDED" for x in ledger),
        )
        self.assertEqual(state["v2_attempts_used"],4)
        self.assertEqual(state["economic_outcomes_opened"],19)
        self.assertGreaterEqual(state["discovery_ledger_entries"],51)
        self.assertGreaterEqual(state["discovery_result_recorded_entries"],16)

        if results:
            self.assertEqual(state["v2_attempts_used"],4)
            self.assertEqual(state["v2_search_budget_remaining"],80)
            self.assertEqual(state["economic_outcomes_opened"],19)

        self.assertFalse(state["protected_evidence_opened"])
        self.assertFalse(state["live_orders_authorized"])
        self.assertFalse(state["competition_start_authorized"])

    def test_04_authorization_is_exact_and_wrong_gate_always_fails_before_economics(self):
        auth=load("research_v3/WAVE_03_EXECUTION_AUTHORIZATION_V1.json")
        self.assertIn(auth["status"],("PENDING_EXACT_HEAD_GREEN","AUTHORIZED_AFTER_EXACT_HEAD_GREEN"))
        self.assertEqual(auth["candidate_ids"],[CID])
        self.assertEqual(auth["candidate_spec_hashes"][CID],SPEC_HASH)
        self.assertEqual(auth["evaluator_sha256"],EVAL_SHA256)
        self.assertEqual(auth["evaluator_git_blob_sha1"],EVAL_BLOB)
        self.assertEqual(auth["wrapper_git_blob_sha1"],WRAPPER_BLOB)
        self.assertFalse(auth["candidate_own_outcomes_opened"])
        self.assertFalse(auth["protected_evidence_opened"])
        self.assertFalse(auth["live_orders"])
        self.assertFalse(auth["competition_start"])

        if auth["status"]=="PENDING_EXACT_HEAD_GREEN":
            self.assertIsNone(auth["execution_gate_head"])
            self.assertIsNone(auth["execution_gate_ci_run_id"])
            self.assertIsNone(auth["execution_gate_ci_conclusion"])
        else:
            self.assertIsInstance(auth["execution_gate_head"],str)
            self.assertEqual(len(auth["execution_gate_head"]),40)
            int(auth["execution_gate_head"],16)
            self.assertIsInstance(auth["execution_gate_ci_run_id"],int)
            self.assertGreater(auth["execution_gate_ci_run_id"],0)
            self.assertEqual(auth["execution_gate_ci_conclusion"],"SUCCESS")

        with patch("research_v3.wave03_execute.execute_wave",side_effect=AssertionError("economics must not run")) as economic:
            with self.assertRaises(V3Wave03ExecutionNotAuthorized):
                execute_authorized(ROOT,"missing.zip",execution_head="not-authorized",execution_ci_run_id=0)
            economic.assert_not_called()

    def test_05_post_outcome_result_and_historical_accounting_are_canonical_if_opened(self):
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        state=load("CURRENT_STATE.json")
        wave03=state["performance_research_v3"]["wave03"]
        rec=[x for x in ledger if x.get("candidate_id")==CID and x["entry_type"]=="RESULT_RECORDED"]

        if not rec:
            self.assertFalse(wave03["candidate_own_outcomes_opened"])
            return

        self.assertEqual(len(rec),1)
        result=load(RESULT_REF)
        self.assertEqual(result["candidate_id"],CID)
        self.assertEqual(result["spec_hash"],SPEC_HASH)
        self.assertEqual(result["result_hash"],compute_result_hash(result))
        self.assertEqual(rec[0]["payload"]["result"],result)
        self.assertEqual(rec[0]["payload"]["result_hash"],result["result_hash"])

        self.assertTrue(wave03["candidate_own_outcomes_opened"])
        self.assertEqual(wave03["result_ref"],RESULT_REF)
        self.assertEqual(wave03["result_hash"],result["result_hash"])
        self.assertEqual(wave03["result_status"],result["status"])
        self.assertEqual(wave03["v2_attempts_used_after_wave03"],16)
        self.assertEqual(wave03["v2_search_budget_remaining_after_wave03"],68)
        self.assertEqual(wave03["economic_outcomes_opened_after_wave03"],19)
        self.assertEqual(wave03["economic_attempt_delta"],1)
        self.assertEqual(wave03["persistence_additional_attempts_consumed"],0)
        self.assertEqual(wave03["ledger_result_sequence"],rec[0]["sequence"])

    def test_06_wave02_green_and_safety_remain_closed(self):
        state=load("CURRENT_STATE.json")
        self.assertEqual(state["performance_research_v3"]["wave02"]["post_persistence_validation_head"],"36b2b26b4d7ff01a9f5dd0a5ecd360ec21ca9ac5")
        self.assertEqual(state["performance_research_v3"]["wave02"]["post_persistence_validation_ci_run_id"],35819512741)
        self.assertEqual(state["performance_research_v3"]["wave02"]["post_persistence_validation_conclusion"],"SUCCESS")
        self.assertFalse(state["protected_evidence_opened"])
        self.assertFalse(state["live_orders_authorized"])
        self.assertFalse(state["competition_start_authorized"])

if __name__=="__main__": unittest.main(verbosity=2)
