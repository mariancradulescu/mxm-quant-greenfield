from __future__ import annotations
import json, unittest
from pathlib import Path
from research_core_v4.crash_recovery_control_v3 import validate_current_control_plane
ROOT=Path(__file__).resolve().parents[1]
def load(r): return json.loads((ROOT/r).read_text())
class RecoveryV3Tests(unittest.TestCase):
 def test_fail_closed_prearm_blocked(self):
  r=validate_current_control_plane()
  self.assertEqual(r["status"],"PASS_GREENFIELD_RECOVERY_V3_FAIL_CLOSED_PRE_ARM_BLOCKED_NO_REAL_RESPONSE_EXECUTION")
  self.assertEqual(r["accepted_canonical_result_count"],0); self.assertFalse(r["real_execution_authorized"]); self.assertFalse(r["arm_present"]); self.assertFalse(r["attempt_lock_present"]); self.assertFalse(r["input_staging_present"]); self.assertEqual(r["process_attempts_started"],0)
  self.assertTrue(r["scientific_source_unchanged"]); self.assertTrue(r["historical_locks_unchanged"]); self.assertTrue(r["private_runtime_proposal_preserved_and_superseded"]); self.assertTrue(r["execution_is_byte_identical_reference"])
  self.assertTrue(r["exact_source_bytes_recovered"]); self.assertEqual(r["required_secret_status"],"ABSENT"); self.assertGreater(r["conservative_margin_vs_installed_timeout"],3)
 def test_runtime_evidence_scope_is_corrected(self):
  old=load("research_core_v4/state/V4_GREENFIELD_REFERENCE_RUNTIME_BENCHMARK_RESULT_V1.json"); new=load("research_core_v4/state/V4_RUNTIME_EVIDENCE_SCOPE_CORRECTION_V1.json")
  self.assertAlmostEqual(old["full_synthetic_result"]["combined_profiled_seconds"],49.85226556699999)
  self.assertFalse(new["correction"]["end_to_end_measured_claim_authorized"])
  self.assertAlmostEqual(new["conservative_total_runtime_upper_bound_seconds"],983.2452655669999)
  self.assertGreater(new["conservative_margin_vs_installed_workflow_timeout"],3)
 def test_semantic_identity(self):
  x=load("research_core_v4/state/V4_GREENFIELD_EXECUTION_SEMANTIC_EQUIVALENCE_V1.json"); self.assertTrue(x["execution_implementation"]["identity_with_reference"]); self.assertFalse(x["execution_implementation"]["fast_reimplementation_created"]); self.assertFalse(x["deterministic_context_sharding"]["adopted"])
 def test_exact_inputs_recovered_but_not_staged(self):
  x=load("research_core_v4/state/V4_EXACT_18_INPUT_RECOVERY_AUDIT_V1.json"); s=load("research_core_v4/state/V4_STATE.json")
  self.assertEqual(x["verification"]["verified_series_count"],18); self.assertTrue(x["verification"]["all_series_sha256_match"])
  self.assertEqual(s["recovery_v3_preparation"]["status"],"FAIL_CLOSED_PRE_ARM_BLOCKED"); self.assertTrue(s["recovery_v3_preparation"]["exact_source_bytes_recovered"]); self.assertEqual(s["recovery_v3_preparation"]["required_secret_status"],"ABSENT"); self.assertFalse(s["recovery_v3_preparation"]["input_staging_certificate_present"]); self.assertFalse(s["recovery_v3_preparation"]["arm_present"])
if __name__=="__main__": unittest.main()
