from __future__ import annotations
import json, unittest
from pathlib import Path
from research_core_v4.crash_recovery_control_v3 import validate_current_control_plane
ROOT=Path(__file__).resolve().parents[1]
def load(r): return json.loads((ROOT/r).read_text())
class RecoveryV3Tests(unittest.TestCase):
 def test_prepared_not_armed(self):
  r=validate_current_control_plane()
  self.assertEqual(r["status"],"PASS_GREENFIELD_RECOVERY_V3_PREPARED_NOT_ARMED_NO_REAL_RESPONSE_EXECUTION"); self.assertEqual(r["accepted_canonical_result_count"],0); self.assertFalse(r["real_execution_authorized"]); self.assertFalse(r["arm_present"]); self.assertFalse(r["input_staging_present"]); self.assertEqual(r["process_attempts_started"],0); self.assertTrue(r["scientific_source_unchanged"]); self.assertTrue(r["historical_locks_unchanged"]); self.assertTrue(r["private_runtime_proposal_preserved_and_superseded"]); self.assertTrue(r["execution_is_byte_identical_reference"]); self.assertGreater(r["runtime_margin_multiple"],10)
 def test_runtime_evidence(self):
  x=load("research_core_v4/state/V4_GREENFIELD_REFERENCE_RUNTIME_BENCHMARK_RESULT_V1.json"); self.assertTrue(x["evidence_boundary"]["synthetic_only"]); self.assertFalse(x["evidence_boundary"]["real_market_response_values_used"]); self.assertEqual(x["full_synthetic_result"]["event_count"],118262); self.assertLess(x["full_synthetic_result"]["combined_profiled_seconds"],900)
 def test_semantic_identity(self):
  x=load("research_core_v4/state/V4_GREENFIELD_EXECUTION_SEMANTIC_EQUIVALENCE_V1.json"); self.assertTrue(x["execution_implementation"]["identity_with_reference"]); self.assertFalse(x["execution_implementation"]["fast_reimplementation_created"]); self.assertFalse(x["deterministic_context_sharding"]["adopted"])
 def test_no_current_private_runtime_or_authorization(self):
  s=load("research_core_v4/state/V4_STATE.json"); self.assertFalse(s["first_wave"]["deterministic_crash_recovery_authorized"]); self.assertFalse(s["first_wave"]["current_recovery_execution_authorized"]); self.assertEqual(s["recovery_v2_preparation"]["status"],"HISTORICAL_PRIVATE_RUNTIME_PROPOSAL_SUPERSEDED_BEFORE_USE"); self.assertEqual(s["recovery_v3_preparation"]["canonical_repository"],"mariancradulescu/mxm-quant-greenfield"); self.assertFalse(s["recovery_v3_preparation"]["second_repository_allowed"])
if __name__=="__main__": unittest.main()
