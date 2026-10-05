"""Exact-head integrity/readiness checks only; no simulation or trial execution."""
from pathlib import Path
import ast, base64, hashlib, io, json, subprocess, sys
import numpy as np
def main(root):
 R=Path(root).resolve();P=R/'research_core_v4/triad_v7';start='dc0cbbecd0ae18147acbdbc8add108c8c830bc77'
 def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
 def read(p):return json.loads(p.read_text())
 def git(*a):return subprocess.check_output(['git',*a],cwd=R,text=True).strip()
 head=git('rev-parse','HEAD');m=read(P/'TRIAL_MANIFEST_V1.json');a=read(P/'PREEXECUTION_AUTHORITY_V1.json');state=read(R/'research_core_v4/state/V4_STATE.json');checks={}
 for f,s in a['bindings'].items():assert sha(R/f)==s,f
 for f,s in m['bindings'].items():assert sha(R/f)==s,f
 assert a['manifest_sha256']==state['current_authority']['manifest_sha256']==sha(P/'TRIAL_MANIFEST_V1.json')
 assert state['current_authority']['sha256']==sha(P/'PREEXECUTION_AUTHORITY_V1.json')
 assert state['current_authority']['supersession_sha256']==sha(P/'DAILY_SCORE_AR_SUPERSESSION_AUTHORITY_V1.json')
 checks['all_manifest_worker_bridge_proof_and_authority_bindings_exact']=True
 changed=git('diff','--name-status',start,head).splitlines()
 for row in changed:
  kind,f=row.split('\t');assert (kind=='A' and f.startswith('research_core_v4/triad_v7/')) or (kind=='M' and f=='research_core_v4/state/V4_STATE.json'),row
 old=json.loads(subprocess.check_output(['git','show',start+':research_core_v4/state/V4_STATE.json'],cwd=R))
 allowed={'status','current_next_action_type','next_action','stop_boundary','current_authority'}
 assert all(state[k]==v for k,v in old.items() if k not in allowed)
 assert set(state)-set(old)=={'triad_v6_statistical_architecture_authority'}
 assert state['triad_v6_statistical_architecture_authority']==old['current_authority']
 assert a['V6_numerical_authority_sha256']==sha(R/'research_core_v4/triad_v6/NUMERICAL_PRODUCTION_AUTHORITY_V1.json')=='52775bdde358280ca56b37527454ad8cc11e8bc7d1316aca987a8a8585d30701'
 checks['V1_V6_all_artifacts_and_every_old_history_field_unchanged']=True
 d=read(R/'research_core_v4/triad_v2/TRIAD_V2_ESTIMAND_NUISANCE_DESIGN_V1.json')
 expected=[{'index':4*c+h,'cohort':cohort,'horizon_minutes':hor} for c,cohort in enumerate(d['universe']['cohorts']) for h,hor in enumerate(d['horizons_minutes'])]
 assert m['leaves']==expected and len(expected)==12 and len(m['null_cases'])==17
 assert not m['daily_score_AR_primary_null_cases']
 assert read(P/'DAILY_SCORE_AR_SUPERSESSION_AUTHORITY_V1.json')['status']=='SUPERSEDED_FOR_TRIAD_V7_MECHANISM_SPECIFIC_NULL_CERTIFICATION'
 assert [x['id'] for x in m['null_cases']]==list(range(17)) and {x['state_phi'] for x in m['null_cases']}=={0.,.8,.97}
 assert len(m['partial_nulls'])==4 and len(m['power_alternatives'])==7 and len(m['power_cells'])==63
 assert m['power_case_ids']==[0,13,15,16]
 assert m['size_confidence']['events']==204 and m['power_confidence']['events']==3780
 checks['complete_cases_partial_nulls_power_cells_and_simultaneous_family_bound']=True
 sys.path.insert(0,str(P));import stochastic_worker_v1 as w
 # w is loaded from the authoritative clean tree, not a transient work checkout.
 assert Path(w.__file__).resolve()==P/'stochastic_worker_v1.py'
 g=w.load_geometry();s=read(R/'research_core_v4/triad_v2/EXACT_SUPPORT_RAW_RESULT_V1.json');blob=base64.b64decode(s['actual_masks_npz_base64'])
 assert hashlib.sha256(blob).hexdigest()==s['actual_masks_npz_sha256']=='e319b504bc397f0d12152df681e8f00d28e8c2cf304be9a508a43c84ff1c9107'
 masks=np.load(io.BytesIO(blob),allow_pickle=False)
 assert np.array_equal(g['causal'],masks['causal_relation_membership'][90:])
 assert np.array_equal(g['complete'],masks['full_clock_horizon'][90:])
 assert hashlib.sha256(g['bank'].astype('<i4').tobytes()).hexdigest()==m['multiplier_bank_int32_sha256']
 summary=read(R/'research_core_v4/triad_v6/ACTUAL_NUMERICAL_SUPPORT_SUMMARY_V1.json')
 assert all(x['numerically_unavailable']==0 and x['numerically_usable']==1184 for x in summary['whole_cohort_clock_support'])
 for leaf in summary['leaf_support']:
  ci=d['universe']['cohorts'].index(leaf['cohort']);hi=d['horizons_minutes'].index(leaf['horizon_minutes'])
  assert int(g['complete'][:,:,ci,hi].sum())==leaf['valid_complete_clocks']
 checks['original_actual_npz_timestamp_masks_bank_and_V6_numerical_support_match']=True
 for file,plan in [('MECHANICAL_PREEXECUTION_RAW_V1.json','MECHANICAL_PREEXECUTION_PLAN_V1.json'),('MECHANICAL_EXECUTION_ROUTE_RAW_V1.json','MECHANICAL_EXECUTION_ROUTE_PLAN_V1.json')]:
  raw=read(P/file);assert raw['all_pass'] and all(raw['checks'].values())
  assert raw['manifest_sha256']==sha(P/'TRIAL_MANIFEST_V1.json') and raw['plan_sha256']==sha(P/plan)
  assert all(raw[k]==0 for k in ['null_Monte_Carlo_trials','power_Monte_Carlo_trials','real_response_openings','future_Y_reads','broker_contacts','new_acquisition','candidate_frozen_count','orders'])
 checks['all_mechanical_raw_gates_pass_zero_statistical_trial_counters']=True
 import control_plane_v1 as cp
 assert Path(cp.__file__).resolve()==P/'control_plane_v1.py';cp.preflight()
 assert not (P/'EXECUTION_ARM_V1.json').exists()
 try:cp.execution_arm(m,a,'null');raise AssertionError('Unarmed execution allowed')
 except FileNotFoundError:pass
 assert not any(a[k] for k in ['statistical_execution_authorized','real_response_authorized','future_real_signed_response_authorized','confirmation_authorized','protected_forward_authorized','broker_contact_authorized','acquisition_authorized','candidate_promotion_authorized','trading_authorized'])
 for f in P.glob('*.py'):ast.parse(f.read_text())
 checks['control_preflight_and_ARM_absence_block_all_trial_execution']=True
 result={'schema':'TRIAD_V7_EXACT_HEAD_PREEXECUTION_VALIDATION_V1','starting_head':start,'validated_authority_head':head,'validated_authority_tree_sha':git('rev-parse','HEAD^{tree}'),'checks':checks,'all_pass':True,'statistical_certification_pass':False,'null_Monte_Carlo_trials':0,'power_Monte_Carlo_trials':0,'real_response_openings':0,'future_Y_reads':0,'broker_contacts':0,'new_acquisition':0,'candidate_frozen_count':0,'orders':0,'oracle_or_actual_support_interpreter_reexecuted':False,'mechanical_tests_reexecuted':False,'payload_hashes':{str(f.relative_to(R)):sha(f) for f in P.iterdir() if f.is_file()},'validator_sha256':sha(Path(__file__)),'validator_ref':'research_core_v4/triad_v7/validate_preexecution_head_v1.py','final_head_resolution':'Containing commit: only this record and its bound validator may differ from validated_authority_head. Verify final live ref, exact delta and all payload hashes after publication.'}
 print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__':main(sys.argv[1])
