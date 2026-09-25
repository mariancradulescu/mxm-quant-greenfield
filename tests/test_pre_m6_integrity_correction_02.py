import copy,hashlib,json,math,unittest
from pathlib import Path

from discovery.canonical import verify_spec_hash
from discovery.ledger import derive_active_spec_hashes,read_ledger
from discovery.schema import (
    ALLOWED_RESULT_STATES,COST_CONFIDENCE_STATES,METRIC_AVAILABILITY_STATES,
    SchemaError,validate_candidate_spec,validate_result,
)

ROOT=Path(__file__).resolve().parents[1]
ACTIVE_IDS=[f'V2-C{i:03d}' for i in range(6,13)]
OLD_HASHES={
 'V2-C010':'4adb3df0b848c6520c2632b168b8b07291a18b169f108ea7466ea48a77216beb',
 'V2-C011':'8de1afb991a4a0334281e1be264f2dab1af490980e3f7018bb7d6914ce55b8e9',
 'V2-C012':'5270ec00bcdbac8c431c55500d0af812df8f069fc6d0782afa8a36d62cd2ad18',
}
NEW_HASHES={
 'V2-C010':'810670fbe6ed57c704a499c32799e6750417a431928eb55f8766b1ff87e46fc1',
 'V2-C011':'6fcf1f3f665fe6412a434c8272b18c2a5156d70f723409bc1340810bea8080fd',
 'V2-C012':'3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845',
}
def load(p): return json.loads((ROOT/p).read_text(encoding='utf-8'))
def git_blob_sha_bytes(data): return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def git_blob_sha_file(p): return git_blob_sha_bytes((ROOT/p).read_bytes())
def metrics():
 return {
  'event_count':0,'gross_pnl':0.0,'coarse_net_pnl':0.0,'gross_return':0.0,'coarse_net_return':0.0,
  'gross_per_event':0.0,'net_per_event':0.0,'cost_burden':0.0,'turnover':0.0,
  'weekly_events':{'2026-W01':0},'active_weeks':0,'longest_inactive_gap':0,
  'weekday_distribution':{'MON':0},'session_distribution':{'ALL':0},'hold_duration':{'mean_bars':0.0},
  'exposure':0.0,'drawdown':0.0,'symbol_contribution':{'SYNTHETIC':0.0},
  'direction_contribution':{'LONG':0.0},'subperiod_contribution':{'DEV':0.0},'regime_contribution':{'ALL':0.0}
 }
def result(status='COST_UNRESOLVED'):
 return {
  'candidate_id':'V2-C900','spec_hash':'a'*64,'stage':'A','status':status,
  'implementation_validity':{'state':'VALID','reason':'fixture'},'metrics':metrics(),
  'eur200_feasibility':{'state':'NOT_EVALUATED','reason':'fixture'},
  'cost_confidence':{'state':'UNRESOLVED','reason':'fixture'},
  'data_completeness':{'state':'SUFFICIENT','reason':'fixture'},
  'provenance':{
   'data_evidence':{'identity':'DATA','binding':{'type':'DATASET_SHA256','sha256':'1'*64}},
   'cost_evidence':{'identity':'COST','state':'UNRESOLVED','sha256':'2'*64},
   'evaluator':{'version':'fixture-v1','sha256':'3'*64}
  }
 }
def set_cost(r,state):
 r['cost_confidence']={'state':state,'reason':'fixture'}; r['provenance']['cost_evidence']['state']=state; return r

class PreM6IntegrityCorrection02(unittest.TestCase):
 def test_01_wave01_exact_original_git_blob_restored(self):
  self.assertEqual(git_blob_sha_file('discovery/WAVE_01_V1.json'),'36da471054fa59ac12596e5a6b0cac98ce06b5e4'); self.assertEqual(load('discovery/WAVE_01_V1.json')['status'],'FROZEN_BEFORE_ANY_V2_ECONOMIC_OUTCOME')
 def test_02_separate_wave01_deferral_authority_valid(self):
  d=load('discovery/WAVE_01_DEFERRAL_V1.json'); self.assertEqual(d['wave_id'],'WAVE_01'); self.assertEqual(d['base_wave_git_blob_sha'],'36da471054fa59ac12596e5a6b0cac98ce06b5e4'); self.assertEqual(d['state'],'DEFERRED_PRE_OUTCOME_DATA_AVAILABILITY_ANCHOR'); self.assertEqual(d['economic_outcomes_opened'],0); self.assertEqual(d['attempts_consumed'],0); self.assertFalse(d['economic_failure']); self.assertFalse(d['contamination']); self.assertTrue(d['c001_c005_preserved']); self.assertEqual(d['replacement_active_primary_frontier'],'PRIMARY_WAVE_02')
 def test_03_frozen_research_contract_git_blob_unchanged(self):
  self.assertEqual(git_blob_sha_file('RESEARCH_CONTRACT_V2.md'),'771ce30de94fd98614035792f13dc88e45e48dfb')
 def test_04_pre_m6_contract_correction_is_narrow_pointer_supersession(self):
  text=(ROOT/'RESEARCH_CONTRACT_V2_PRE_M6_CORRECTION_V1.md').read_text(); self.assertIn('supersedes only the stale Bootstrap/M6 target',text); self.assertIn('M6 target = PRIMARY_WAVE_02',text); self.assertIn('search budget remains 84',text); self.assertIn('opened zero V2 economic outcomes',text)
 def test_05_runtime_rejects_empty_position_admission_policy(self):
  s=load('discovery/candidates/V2-C006.json'); s['position_admission_policy']={}
  with self.assertRaises(SchemaError): validate_candidate_spec(s)
 def test_06_runtime_rejects_empty_stage_a_economic_unit(self):
  s=load('discovery/candidates/V2-C006.json'); s['stage_a_economic_unit']={}
  with self.assertRaises(SchemaError): validate_candidate_spec(s)
 def test_07_arbitrary_string_quantitative_metric_rejected(self):
  r=result(); r['metrics']['gross_pnl']='zero'
  with self.assertRaises(SchemaError): validate_result(r)
 def test_08_boolean_quantitative_metric_rejected(self):
  r=result(); r['metrics']['event_count']=False
  with self.assertRaises(SchemaError): validate_result(r)
 def test_09_nonfinite_numeric_metrics_rejected(self):
  for value in (math.inf,-math.inf,math.nan):
   r=result(); r['metrics']['gross_return']=value
   with self.assertRaises(SchemaError): validate_result(r)
 def test_10_explicit_unavailable_and_not_applicable_metric_envelopes_accepted(self):
  for state in ('UNAVAILABLE','NOT_APPLICABLE'):
   r=result(); r['metrics']['gross_pnl']={'state':state,'reason':'legitimately unavailable fixture'}; self.assertTrue(validate_result(r))
 def test_11_discovery_survivor_with_invalid_implementation_rejected(self):
  r=set_cost(result('DISCOVERY_SURVIVOR'),'VERIFIED'); r['implementation_validity']={'state':'INVALID','reason':'fixture'}
  with self.assertRaises(SchemaError): validate_result(r)
 def test_12_discovery_survivor_with_non_sufficient_data_rejected(self):
  for state in ('INSUFFICIENT','UNRESOLVED'):
   r=set_cost(result('DISCOVERY_SURVIVOR'),'VERIFIED'); r['data_completeness']={'state':state,'reason':'fixture'}
   with self.assertRaises(SchemaError): validate_result(r)
 def test_13_discovery_survivor_with_unresolved_cost_rejected(self):
  r=result('DISCOVERY_SURVIVOR')
  with self.assertRaises(SchemaError): validate_result(r)
 def test_14_cost_unresolved_requires_unresolved_cost_confidence(self):
  r=set_cost(result('COST_UNRESOLVED'),'VERIFIED')
  with self.assertRaises(SchemaError): validate_result(r)
 def test_15_coarse_net_fail_requires_credible_resolved_cost(self):
  r=result('COARSE_NET_FAIL')
  with self.assertRaises(SchemaError): validate_result(r)
 def test_16_cost_provenance_state_must_match_cost_confidence(self):
  r=result(); r['provenance']['cost_evidence']['state']='VERIFIED'
  with self.assertRaises(SchemaError): validate_result(r)
 def test_17_gross_edge_fail_does_not_require_resolved_cost(self):
  self.assertTrue(validate_result(result('GROSS_EDGE_FAIL')))
 def test_18_implementation_invalid_binding_rule_is_explicit(self):
  r=result('IMPLEMENTATION_INVALID'); r['implementation_validity']={'state':'INVALID','reason':'fixture'}; self.assertTrue(validate_result(r)); r['implementation_validity']={'state':'VALID','reason':'fixture'}
  with self.assertRaises(SchemaError): validate_result(r)
 def test_19_data_and_structural_terminal_bindings_are_explicit(self):
  r=result('DATA_INSUFFICIENT'); r['data_completeness']={'state':'INSUFFICIENT','reason':'fixture'}; self.assertTrue(validate_result(r)); s=result('STRUCTURALLY_INFEASIBLE'); s['eur200_feasibility']={'state':'INFEASIBLE','reason':'fixture'}; self.assertTrue(validate_result(s))
 def test_20_json_schema_runtime_representative_parity(self):
  c=load('discovery/candidate.schema.json'); rs=load('discovery/result.schema.json'); self.assertEqual(c['properties']['position_admission_policy']['minProperties'],1); self.assertEqual(c['properties']['stage_a_economic_unit']['minProperties'],1); self.assertEqual(set(rs['properties']['status']['enum']),ALLOWED_RESULT_STATES); self.assertEqual(set(rs['$defs']['unavailableMetric']['properties']['state']['enum'])|{'AVAILABLE'},METRIC_AVAILABILITY_STATES); self.assertEqual(set(rs['$defs']['costEnvelope']['properties']['state']['enum']),COST_CONFIDENCE_STATES); self.assertEqual(rs['properties']['metrics']['properties']['event_count']['$ref'],'#/$defs/nonnegativeIntegerMetric'); self.assertEqual(rs['properties']['metrics']['properties']['gross_pnl']['$ref'],'#/$defs/numericMetric'); self.assertEqual(rs['properties']['metrics']['properties']['weekly_events']['$ref'],'#/$defs/structuredMetric')
 def test_21_c010_horizon_corrected_hash_valid_and_refrozen(self):
  s=load('discovery/candidates/V2-C010.json'); self.assertEqual(s['hypothesis_dimensions']['holding_horizon'],'OVERNIGHT_TO_MULTI_DAY'); self.assertEqual(s['spec_hash'],NEW_HASHES['V2-C010']); self.assertTrue(verify_spec_hash(s)); self.assertEqual(s['provenance']['pre_m6_integrity_correction_02']['old_spec_hash'],OLD_HASHES['V2-C010'])
 def test_22_c011_horizon_corrected_hash_valid_and_refrozen(self):
  s=load('discovery/candidates/V2-C011.json'); self.assertEqual(s['hypothesis_dimensions']['holding_horizon'],'OVERNIGHT_TO_MULTI_DAY'); self.assertEqual(s['spec_hash'],NEW_HASHES['V2-C011']); self.assertTrue(verify_spec_hash(s)); self.assertEqual(s['provenance']['pre_m6_integrity_correction_02']['old_spec_hash'],OLD_HASHES['V2-C011'])
 def test_23_c012_one_sided_semantics_unambiguous_hash_valid(self):
  s=load('discovery/candidates/V2-C012.json'); self.assertNotIn('lagger_max_abs_z_in_signal_direction',s['parameters']); self.assertEqual(s['parameters']['lagger_max_z_in_leader_direction'],0.5); self.assertEqual(s['direction']['LONG_NAS100'],'leader_z >= 1.5 and lagger_z <= 0.5'); self.assertEqual(s['direction']['SHORT_NAS100'],'leader_z <= -1.5 and lagger_z >= -0.5'); self.assertIn('one-sided',s['rationale']); self.assertEqual(s['spec_hash'],NEW_HASHES['V2-C012']); self.assertTrue(verify_spec_hash(s))
 def test_24_original_ledger_entries_1_17_byte_content_preserved(self):
     lines = (ROOT / "discovery/ledger.jsonl").read_bytes().splitlines(keepends=True)
     first17 = b"".join(lines[:17])
     self.assertEqual(len(lines), 26)
     self.assertEqual(git_blob_sha_bytes(first17), "32257059c64fa1e2174023a09186d26c23330b14")
 def test_25_new_refreeze_entries_append_after_17_only(self):
     entries = read_ledger(ROOT / "discovery/ledger.jsonl")
     tail = entries[17:20]
     self.assertEqual([(e["sequence"], e["entry_type"], e["candidate_id"]) for e in tail], [(18, "CANDIDATE_REFROZEN_PRE_OUTCOME", "V2-C010"), (19, "CANDIDATE_REFROZEN_PRE_OUTCOME", "V2-C011"), (20, "CANDIDATE_REFROZEN_PRE_OUTCOME", "V2-C012")])
     self.assertTrue(all(e["payload"]["reason"] == "PRE_OUTCOME_SEMANTIC_INTEGRITY_CORRECTION" and e["payload"]["outcome_seen"] is False and e["payload"]["attempt_consumed"] is False for e in tail))
     self.assertFalse(any(e["entry_type"] == "CANDIDATE_REFROZEN_PRE_OUTCOME" for e in entries[20:]))
 def test_26_active_hashes_derive_to_completion_authority(self):
  active=derive_active_spec_hashes(read_ledger(ROOT/'discovery/ledger.jsonl')); completion=load('discovery/PRIMARY_WAVE_02_PRE_OUTCOME_COMPLETION_V1.json')
  for cid in ACTIVE_IDS: self.assertEqual(active[cid],completion['active_candidate_hashes'][cid]); self.assertEqual(active[cid],load(f'discovery/candidates/{cid}.json')['spec_hash'])
 def test_27_original_primary_wave02_freeze_git_blob_preserved(self):
  self.assertEqual(git_blob_sha_file('discovery/PRIMARY_WAVE_02_V1.json'),'1659b44bb9c4ddcaa0bb9809e5e69140f4657562')
 def test_28_active_wave02_completion_binds_original_and_corrected_hashes(self):
  c=load('discovery/PRIMARY_WAVE_02_PRE_OUTCOME_COMPLETION_V1.json'); b=load('discovery/PRIMARY_WAVE_02_V1.json'); self.assertEqual(c['base_wave_authority'],'discovery/PRIMARY_WAVE_02_V1.json'); self.assertEqual(c['original_candidate_hashes'],b['candidate_spec_hashes']); self.assertEqual(set(c['refrozen_candidates']),{'V2-C010','V2-C011','V2-C012'}); self.assertEqual(c['economic_outcomes_opened'],0); self.assertEqual(c['attempts_consumed'],0)
 def test_29_data_requirements_v1_preserved_v2_binds_active_hashes(self):
  self.assertEqual(git_blob_sha_file('data/PRIMARY_WAVE_02_DATA_REQUIREMENTS_V1.json'),'8c49c1b49d6c7552263ee9f96585efd3b63a834c'); d=load('data/PRIMARY_WAVE_02_DATA_REQUIREMENTS_V2.json'); c=load('discovery/PRIMARY_WAVE_02_PRE_OUTCOME_COMPLETION_V1.json'); self.assertEqual(d['candidate_spec_hashes'],c['active_candidate_hashes']); self.assertFalse(d['requirements_semantics_changed']); self.assertEqual(d['central_actual_data_manifest_authority'],'data/DATA_MANIFEST.json')
 def test_30_state_zero_economics_protected_boundary_and_m6_pending(self):
     state = load("CURRENT_STATE.json")
     protected = load("V2_PROTECTED_FORWARD_START.json")
     historical = state["pre_m6_integrity_correction_02"]
     self.assertEqual(state["active_primary_wave_id"], "PRIMARY_WAVE_02")
     self.assertEqual(state["active_primary_wave_authority"], "discovery/PRIMARY_WAVE_02_PRE_OUTCOME_COMPLETION_V1.json")
     self.assertEqual(state["active_data_requirements_authority"], "data/PRIMARY_WAVE_02_DATA_REQUIREMENTS_V2.json")
     self.assertEqual(state["old_wave_01_deferral_authority"], "discovery/WAVE_01_DEFERRAL_V1.json")
     self.assertEqual(state["research_contract_correction_authority"], "RESEARCH_CONTRACT_V2_PRE_M6_CORRECTION_V1.md")
     self.assertEqual(historical["authoritative_ledger_entries"], 20)
     self.assertEqual(historical["v2_attempts_used"], 0)
     self.assertEqual(historical["v2_evaluated_identities"], 0)
     self.assertEqual(historical["economic_outcomes_opened"], 0)
     self.assertEqual(state["v2_protected_forward_start"], "2026-09-17T12:02:58Z")
     self.assertEqual(protected["V2_PROTECTED_FORWARD_START"], "2026-09-17T12:02:58Z")
     self.assertFalse(state["protected_evidence_opened"])
     self.assertFalse(protected["protected_evidence_opened"])
     self.assertEqual(state["m6"]["status"], "PENDING")
if __name__=='__main__': unittest.main(verbosity=2)
