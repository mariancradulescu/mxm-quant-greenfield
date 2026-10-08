"""Exact synthetic and immutable-boundary delivery validation; no market I/O."""
import hashlib,json,pathlib,statistics,unittest,sys,math,socket
R=pathlib.Path(__file__).resolve().parents[2];S='research_core_v4/state/'
def sha(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
def read(p):return json.loads((R/p).read_text())
class Delivery(unittest.TestCase):
 def test_01_frozen_implementations(self):
  for p,h in read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_IMPLEMENTATION_FREEZE_V1.json')['files'].items():self.assertEqual(sha(p),h)
 def test_02_accepted_immutable_science(self):
  for p,h in read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_AUTHORITY_V1.json')['immutable_inputs_sha256'].items():self.assertEqual(sha(p),h)
 def test_03_full_paid_family(self):
  d=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_POWER_PROTOCOL_V1.json');i=read(d['inventory_ref']);self.assertEqual(len(i['leaves']),261);self.assertEqual(d['paid_leaves'],[{k:v for k,v in x.items() if k in ['source','context','horizon_M5']} for x in i['leaves']]);self.assertEqual(d['sources'],i['current_wave']);self.assertEqual(d['parked_sources'],i['parked_sources'])
 def test_04_effect_authority(self):
  p=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_POWER_PROTOCOL_V1.json');d=read(p['power']['effect_authority'])['power'];self.assertEqual(p['power']['effects'],{'NORMAL':d['normal_local_MDE_SD'],'AR025':d['AR025_local_MDE_SD'],'AR050':d['AR050_local_MDE_SD']});self.assertEqual(p['power']['target_simultaneous_lower95'],.8)
 def test_05_simultaneous_precision(self):
  p=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_POWER_PROTOCOL_V1.json')['precision'];z=statistics.NormalDist().inv_cdf(1-.05/(2*p['bounds_family_size']));n=math.ceil(z*z*(1/(4*.02**2)-1));self.assertEqual(p['minimum_n'],n);self.assertEqual(p['trials_per_case'],2**math.ceil(math.log2(n)));self.assertLessEqual(p['maximum_actual_wilson_halfwidth'],.02)
 def test_06_scope_separated(self):
  d=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_SCORE_PROTOCOL_V1.json');self.assertEqual(d['broad_claim']['status'],'OPEN_NOT_TESTED_BY_CURRENT_OPERATIONAL_BENCHMARK');self.assertTrue(d['operational_claim']['not_universal_sigmaB_information']);self.assertEqual(d['operational_claim']['null'],'<=0')
 def test_07_preoutcome_anchor(self):
  d=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_SCORE_PROTOCOL_V1.json')['anchor'];self.assertEqual(d['commit'],'89084af0a21452a17a723fabe19ddd9d636f22af');self.assertEqual(d['policy_sha256'],'dcf0e06070379eaa35c56193b6381f2d9d970104c30b161b1bb124e96aa92c98');self.assertEqual(d['models_sha256'],'9fcc3a00954750597ff25ce3d86bc657008f88a90d950374666a9b18f6484257')
 def test_08_causality_fairness_fixtures(self):
  r=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_SYNTHETIC_CERTIFICATION_RESULT_V1.json');self.assertEqual(r['pipeline']['tests_failed'],0);self.assertEqual(r['pipeline']['tests_passed'],17);self.assertEqual(r['power_engine']['tests_failed'],0);self.assertTrue(r['pipeline']['checks']['causal_prefix_statistics_unchanged_by_future']);self.assertTrue(r['pipeline']['checks']['no_same_day_or_unmatured_or_unpurged_train'])
 def test_09_fixed_trials_and_wilson_result(self):
  from inference import wilson
  p=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_POWER_PROTOCOL_V1.json');r=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_SYNTHETIC_CERTIFICATION_RESULT_V1.json');self.assertEqual(r['protocol_sha256'],sha(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_POWER_PROTOCOL_V1.json'))
  for e in r['null']:
   self.assertEqual(e['trials'],p['precision']['trials_per_case']);lo,hi=wilson(e['false_complete_lead_count'],e['trials'],p['precision']['wilson_z']);self.assertAlmostEqual(float(lo),e['simultaneous_wilson_lower'],14);self.assertAlmostEqual(float(hi),e['simultaneous_wilson_upper'],14);self.assertEqual(e['pass'],hi<=.05)
 def test_10_scientific_gate_and_stop(self):
  r=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_SYNTHETIC_CERTIFICATION_RESULT_V1.json');a=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_AUTHORITY_V1.json');self.assertFalse(a['broker_authorized']);self.assertEqual(a['broker_requests'],0);self.assertEqual(r['status'],'BLOCKED_NULL_FWER_NOT_CERTIFIED');self.assertFalse(r['null'][-1]['pass']);self.assertTrue(all(e['pass'] for e in r['null'][:-1]));self.assertEqual(r['first_blocker'],r['null'][-1]);self.assertGreater(r['first_blocker']['simultaneous_wilson_upper'],.05)
 def test_11_original_receipt_boundary(self):
  a=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_AUTHORITY_V1.json');self.assertEqual(a['original_available_at'],'UNKNOWN_BYTE_EXACT_UNCHANGED');self.assertEqual(a['durable_support_head'],'b80f8dba610153c91b051ffd5073ee3433e300c4');self.assertFalse(a['durable_support_outputs_modified'])
 def test_12_calendar_ceiling_not_duration(self):
  a=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_AUTHORITY_V1.json');self.assertEqual(len(a['blocks']),6);self.assertEqual(sum(b['calendar_days'] for b in a['blocks']),168);self.assertFalse(a['duration_resolved']);self.assertTrue(all(b['requests_made']==0 and b['new_rows_streamed']==0 for b in a['blocks']))
 def test_13_zero_real_and_protected(self):
  a=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_AUTHORITY_V1.json');self.assertEqual(a['new_economic_outcomes'],0);self.assertEqual(a['search_budget_used'],0);self.assertEqual(a['real_feature_response_model_loss_return_PNL_inputs'],0);self.assertFalse(a['protected_forward_opened']);self.assertFalse(a['confirmation_opened']);self.assertEqual(a['orders'],0)
 def test_14_historical_canonical_state_preserved(self):
  a=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_AUTHORITY_V1.json');allowed=set(a['allowed_operational_changes'])|{'current_wave_operational_model_relative_stage0_v1'}
  for p in a['canonical_states']:
   before=read('baseline/'+p);after=read(p)
   self.assertEqual({k:v for k,v in before.items() if k not in allowed},{k:v for k,v in after.items() if k not in allowed})
 def test_15_new_artifact_bindings(self):
  for p,h in read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_AUTHORITY_V1.json')['new_artifacts_sha256'].items():self.assertEqual(sha(p),h)
 def test_16_freeze_ancestry(self):
  a=read(S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_AUTHORITY_V1.json');self.assertEqual(a['protocol_freeze_commit'],'e9194f809f71a76356adf67ab5dfaa24288ed72e');self.assertEqual(a['authoritative_start'],'8759b50eb25673a0c8b67c29cd4853efcac33608');self.assertFalse(a['retuning_after_results'])
if __name__=='__main__':
 def denied(*args,**kwargs):raise RuntimeError('NO_NETWORK_NO_MARKET')
 socket.socket=denied;socket.create_connection=denied;unittest.main()
