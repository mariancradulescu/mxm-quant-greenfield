import hashlib, json, unittest
from pathlib import Path
from unittest.mock import patch

from discovery.canonical import verify_spec_hash
from discovery.ledger import read_ledger
from research_v3.wave03_execute import V3Wave03ExecutionNotAuthorized, execute_authorized

ROOT=Path(__file__).resolve().parents[1]
CID="V2-C026"
SPEC_HASH="41880f453efd363da860024e8f9b7b299bd14b9f2367156779f3f193f9abc9e9"
EVAL_SHA256="29b250904fa4b3de8e4ce0292ab38332670e624cff9a01ab649ee831fffe057f"
EVAL_BLOB="7c07c1d39053baa1e31ed4eb3d552520d809ccd7"
WRAPPER_BLOB="747d522e23c1621bb138de4d8495973232c837e1"

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

    def test_02_wave03_code_and_evidence_bindings_are_exact(self):
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

    def test_03_c026_is_freeze_only_and_accounting_is_unchanged(self):
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        rows=[x for x in ledger if x.get("candidate_id")==CID]
        self.assertEqual([x["entry_type"] for x in rows],["CANDIDATE_FROZEN"])
        self.assertEqual(rows[0]["sequence"],51)
        state=load("CURRENT_STATE.json")
        self.assertEqual(state["v2_attempts_used"],15)
        self.assertEqual(state["v2_search_budget_remaining"],69)
        self.assertEqual(state["v2_evaluated_identities"],15)
        self.assertEqual(state["economic_outcomes_opened"],18)
        self.assertEqual(state["discovery_ledger_entries"],51)
        self.assertEqual(state["discovery_result_recorded_entries"],16)
        self.assertFalse(state["performance_research_v3"]["wave03"]["candidate_own_outcomes_opened"])

    def test_04_pending_authorization_fails_before_economics(self):
        auth=load("research_v3/WAVE_03_EXECUTION_AUTHORIZATION_V1.json")
        self.assertEqual(auth["status"],"PENDING_EXACT_HEAD_GREEN")
        with patch("research_v3.wave03_execute.execute_wave",side_effect=AssertionError("economics must not run")) as economic:
            with self.assertRaises(V3Wave03ExecutionNotAuthorized):
                execute_authorized(ROOT,"missing.zip",execution_head="x",execution_ci_run_id=0)
            economic.assert_not_called()

    def test_05_wave02_is_green_and_safety_stays_closed(self):
        state=load("CURRENT_STATE.json")
        self.assertEqual(state["performance_research_v3"]["wave02"]["post_persistence_validation_head"],"36b2b26b4d7ff01a9f5dd0a5ecd360ec21ca9ac5")
        self.assertEqual(state["performance_research_v3"]["wave02"]["post_persistence_validation_ci_run_id"],35819512741)
        self.assertEqual(state["performance_research_v3"]["wave02"]["post_persistence_validation_conclusion"],"SUCCESS")
        self.assertFalse(state["protected_evidence_opened"])
        self.assertFalse(state["live_orders_authorized"])
        self.assertFalse(state["competition_start_authorized"])

if __name__=="__main__": unittest.main(verbosity=2)
