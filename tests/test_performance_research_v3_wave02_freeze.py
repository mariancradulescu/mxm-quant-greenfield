import hashlib, json, unittest
from pathlib import Path
from unittest.mock import patch
from discovery.canonical import verify_spec_hash
from discovery.ledger import read_ledger
from research_v3.wave02_execute import V3Wave02ExecutionNotAuthorized, execute_authorized

ROOT=Path(__file__).resolve().parents[1]
IDS=("V2-C024","V2-C025")
HASHES={
 "V2-C024":"ae239c3db7908cf68e73170f2bc34c6b3039585d46b3fc7f6549db2fb5f98b04",
 "V2-C025":"d357125ce183a2bd377c5c1b209e9ed7e382751042aa2b0162c6d88bd1efcf27",
}
EVAL_SHA256="353e3f8895cf78c9f3113536f7049ce00359ca97e7359dd43bffa67f4d536ae4"
EVAL_BLOB="cfc1feabf0b8b251940d3e7b17f01d915bdc214a"
WRAPPER_BLOB="30d02649960c69d2b8629eead8d38c8cfde9b3ce"

def load(rel):
 return json.loads((ROOT/rel).read_text(encoding="utf-8"))

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

 def test_02_wave_and_code_bindings_are_exact(self):
  wave=load("research_v3/WAVE_02_PRE_OUTCOME_FREEZE_V1.json")
  self.assertEqual(wave["status"],"FROZEN_PENDING_EXACT_HEAD_GREEN")
  self.assertEqual(wave["candidate_ids"],list(IDS))
  self.assertEqual(wave["candidate_spec_hashes"],HASHES)
  self.assertEqual(wave["evaluator"]["sha256"],EVAL_SHA256)
  self.assertEqual(wave["evaluator"]["git_blob_sha1"],EVAL_BLOB)
  self.assertEqual(hashlib.sha256((ROOT/wave["evaluator"]["ref"]).read_bytes()).hexdigest(),EVAL_SHA256)
  self.assertEqual(blob_sha1(ROOT/wave["evaluator"]["ref"]),EVAL_BLOB)
  self.assertEqual(blob_sha1(ROOT/"research_v3/wave02_execute.py"),WRAPPER_BLOB)

 def test_03_ledger_has_freeze_only_and_accounting_unchanged(self):
  ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
  for cid in IDS:
   rows=[x for x in ledger if x.get("candidate_id")==cid]
   self.assertEqual([x["entry_type"] for x in rows],["CANDIDATE_FROZEN"])
  state=load("CURRENT_STATE.json")
  self.assertEqual(state["v2_attempts_used"],13)
  self.assertEqual(state["v2_search_budget_remaining"],71)
  self.assertEqual(state["v2_evaluated_identities"],13)
  self.assertEqual(state["economic_outcomes_opened"],16)
  self.assertEqual(state["discovery_ledger_entries"],48)
  self.assertEqual(state["discovery_result_recorded_entries"],14)
  self.assertFalse(state["performance_research_v3"]["wave02"]["candidate_own_outcomes_opened"])

 def test_04_authorization_is_pending_and_real_path_fails_before_economics(self):
  auth=load("research_v3/WAVE_02_EXECUTION_AUTHORIZATION_V1.json")
  self.assertEqual(auth["status"],"PENDING_EXACT_HEAD_GREEN")
  with patch("research_v3.wave02_execute.execute_wave",side_effect=AssertionError("economics must not run")) as economic:
   with self.assertRaises(V3Wave02ExecutionNotAuthorized):
    execute_authorized(ROOT,"missing.zip",execution_head="x",execution_ci_run_id=0)
   economic.assert_not_called()

 def test_05_safety_and_attempt_invariants(self):
  wave=load("research_v3/WAVE_02_PRE_OUTCOME_FREEZE_V1.json")
  self.assertEqual(wave["new_attempts_consumed_by_freeze"],0)
  self.assertFalse(wave["candidate_own_outcomes_opened"])
  self.assertFalse(wave["protected_evidence_opened"])
  self.assertFalse(wave["live_orders"])
  self.assertFalse(wave["competition_start"])

if __name__=="__main__": unittest.main(verbosity=2)
