"""Durable artifact provenance and adversarial prospective authority checks."""
import copy,hashlib,json,subprocess,unittest
from pathlib import Path
from research_core_v4.post_publication_integrity_v1 import check_state
R=Path(__file__).resolve().parents[1];S=R/'research_core_v4/state'
def load(n):return json.loads((S/n).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
class Audit(unittest.TestCase):
 def test_report_and_source_bindings(self):
  a=load('FACTOR_RESIDUAL_FINAL_PREOUTCOME_AUDIT_V1.json')
  for n,h in a['report_sha256'].items():self.assertEqual(sha((S/n).read_bytes()),h)
  for n,h in a['source_binding'].items():self.assertEqual(sha((R/n).read_bytes()),h)
 def test_exact_source_at_support_head(self):
  a=load('FACTOR_RESIDUAL_SUPPORT_PREFLIGHT_V1.json')
  for n,h in a['source_binding'].items():self.assertEqual(sha(subprocess.check_output(['git','-C',str(R),'show',a['trigger_head']+':'+n])),h)
 def test_support_cannot_be_relabelled_pass(self):
  a=load('FACTOR_RESIDUAL_SUPPORT_PREFLIGHT_V1.json');self.assertFalse(a['inference_geometry_eligible']);self.assertEqual(a['joint_calendar_blocks'],[15])
  self.assertTrue(all(not q['support_pass'] for c in a['contexts'].values() for q in c.values()))
 def test_production_calibration_failure_retained(self):
  a=load('FACTOR_RESIDUAL_CALIBRATION_PRODUCTION_V1.json');self.assertEqual(a['bootstrap_replicates_per_trial'],1023);self.assertFalse(a['mc_gate_pass']);self.assertGreater(a['null']['normal']['wilson95'][1],.05)
 def test_no_outcome_or_new_data(self):
  a=load('FACTOR_RESIDUAL_SUPPORT_PREFLIGHT_V1.json');self.assertFalse(a['response_opened']);self.assertFalse(a['new_data_acquired']);self.assertEqual((a['broker_contacts'],a['historical_requests']),(0,0))
 def test_old_quote_intake_byte_preserved(self):
  for n in ['QUOTE_SUPPORT_PRIVATE_PROOF_RETURN_INTAKE_V1.json','QUOTE_SUPPORT_PROBE_RETURN_INTAKE_V1.json']:
   self.assertEqual((S/n).read_bytes(),subprocess.check_output(['git','-C',str(R),'show','b51696f590a894fa339b93d4c5162576b458c6aa:research_core_v4/state/'+n]))
 def test_old_quote_wave_nested_state_preserved(self):
  prior=json.loads(subprocess.check_output(['git','-C',str(R),'show','b51696f590a894fa339b93d4c5162576b458c6aa:research_core_v4/state/V4_STATE.json']))
  self.assertEqual(load('V4_STATE.json')['next_prospective_wave']['historical_quote_wave_state'],prior['next_prospective_wave'])
 def test_exactly_one_selection(self):
  a=load('NEXT_INFORMATION_SOURCE_SELECTION_V2.json');selected=[x for x in a['ranked_mechanisms'] if x['selected']]
  self.assertEqual(len(selected),1);self.assertEqual(selected[0]['mechanism'],'CAUSAL_LEAVE_ONE_OUT_FACTOR_RESIDUAL_INFORMATION')
 def test_current_governance(self):check_state(load('V4_STATE.json'))
 def test_real_authority_mutations_fail(self):
  s=load('V4_STATE.json')
  for key in ['response_execution_authorized','real_response_authorized','candidate_promotion_authorized','new_acquisition_authorized','ARM_present','protected_forward_opened']:
   x=copy.deepcopy(s);x['next_prospective_wave'][key]=True
   with self.assertRaises(PermissionError):check_state(x)
 def test_historical_retry_and_singleton_fail(self):
  s=load('V4_STATE.json')
  for key,value in [('real_execution_authorized',True),('automatic_retry',True),('accepted_canonical_result_count',2)]:
   x=copy.deepcopy(s);x['recovery_v4_preparation'][key]=value
   with self.assertRaises(PermissionError):check_state(x)
 def test_no_null_claim_or_unblocked_response(self):
  a=load('FACTOR_RESIDUAL_FINAL_PREOUTCOME_AUDIT_V1.json');self.assertFalse(a['economic_null_claimed']);self.assertTrue(a['factor_family_not_closed'])
  s=load('V4_STATE.json');self.assertTrue(s['next_prospective_wave']['next_real_response_blocked']);self.assertFalse(s['next_prospective_wave']['real_response_opened'])
