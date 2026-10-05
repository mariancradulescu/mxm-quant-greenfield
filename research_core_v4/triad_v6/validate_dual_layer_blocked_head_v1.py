"""Validate only persisted deterministic evidence and blocked control authority."""
from pathlib import Path
from fractions import Fraction as F
import ast, hashlib, json, subprocess, sys
def main(root):
 R=Path(root).resolve();P=R/'research_core_v4/triad_v6'
 def read(f):return json.loads(f.read_text())
 def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
 def git(*a):return subprocess.check_output(['git',*a],cwd=R,text=True).strip()
 start='efa5648c4a46e566ac5a9e927c6aaf824d6bd416';head=git('rev-parse','HEAD')
 plan=read(P/'DUAL_LAYER_DEPENDENCE_FEASIBILITY_GATE_PLAN_V1.json');raw=read(P/'DUAL_LAYER_DEPENDENCE_FEASIBILITY_RAW_V1.json');block=read(P/'DUAL_LAYER_PREEXECUTION_BLOCKER_V1.json');control=read(P/'DUAL_LAYER_BLOCKED_CONTROL_PLANE_V1.json');state=read(R/'research_core_v4/state/V4_STATE.json')
 checks={}
 for f,s in block['input_bindings'].items():assert sha(R/f)==s,f
 assert raw['plan_sha256']==sha(P/'DUAL_LAYER_DEPENDENCE_FEASIBILITY_GATE_PLAN_V1.json')
 assert raw['checker_sha256']==plan['checker_sha256']==sha(P/'certify_daily_dependence_feasibility_v1.py')
 assert raw['proof_sha256']==plan['proof_sha256']==sha(P/'DAILY_DEPENDENCE_NULL_COMPATIBILITY_PROOF_V1.md')
 assert control['blocker_sha256']==sha(P/'DUAL_LAYER_PREEXECUTION_BLOCKER_V1.json')
 assert state['current_authority']['sha256']==sha(P/'DUAL_LAYER_BLOCKED_CONTROL_PLANE_V1.json')
 assert state['current_authority']['blocker_sha256']==control['blocker_sha256']
 checks['all_exact_head_input_source_proof_blocker_and_state_bindings']=True
 # Every artifact existing at the audited starting head except current state is immutable.
 changed=git('diff','--name-status',start,head).splitlines()
 for line in changed:
  kind,f=line.split('\t');assert f.startswith('research_core_v4/triad_v6/') or f=='research_core_v4/state/V4_STATE.json'
  assert kind=='A' or (kind=='M' and f=='research_core_v4/state/V4_STATE.json')
 old=json.loads(subprocess.check_output(['git','show',start+':research_core_v4/state/V4_STATE.json'],cwd=R))
 allowed={'status','current_next_action_type','next_action','stop_boundary','current_authority'}
 assert all(state[k]==v for k,v in old.items() if k not in allowed)
 assert set(state)-set(old)=={'triad_v6_numerical_support_authority'}
 assert state['triad_v6_numerical_support_authority']==old['current_authority']
 assert block['numerical_authority_sha256']=='52775bdde358280ca56b37527454ad8cc11e8bc7d1316aca987a8a8585d30701'
 checks['all_V1_V5_existing_V6_and_previous_numerical_PASS_unchanged']=True
 design=read(R/'research_core_v4/triad_v2/TRIAD_V2_ESTIMAND_NUISANCE_DESIGN_V1.json')
 expected=[{'cohort':c,'horizon_minutes':h} for c in design['universe']['cohorts'] for h in design['horizons_minutes']]
 assert raw['complete_12_leaf_inclusion']==expected and len(expected)==12
 assert raw['latest_previous_day_maturity_buffer_purge_minute']==max(design['causal_clock']['decision_UTC_hours'])*60+max(design['horizons_minutes'])+5+design['nuisance_learning']['embargo_minutes_after_maturity']<1440
 assert raw['deterministic_witness_assertions_pass'] and not raw['architecture_compatibility_gate_pass']
 for case,rho in zip(raw['cases'],[F(1,4),F(1,2)]):
  assert case['rho_exact']==str(rho)
  assert list(map(F,case['required_score_AR_conditional_mean_given_prior_score']))==[rho*(i+1) for i in range(12)]
  assert all(F(case['unit_variance_stationary_AR_lag1_covariance'][i][j])==(rho if i==j else 0) for i in range(12) for j in range(12))
  assert F(case['stationary_linear_AR_fourth_moment_exact'])==3+6*(1-rho*rho)/(1+rho*rho)
  assert not case['conditional_null_compatible'] and not case['t5_marginal_preserved_by_linear_AR']
 checks['exact_rational_AR025_AR050_witnesses_and_all12_leaves_verified']=True
 source=(P/'certify_daily_dependence_feasibility_v1.py').read_text();tree=ast.parse(source)
 imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}|{a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
 assert imports<={'pathlib','fractions','hashlib','json'}
 assert not any(isinstance(n,ast.Name) and n.id in {'eval','exec','compile','__import__'} for n in ast.walk(tree))
 checks['checker_no_RNG_network_process_or_stochastic_worker_imports']=True
 classification='PREOUTCOME_BLOCKED_DUAL_LAYER_DEPENDENCE_ARCHITECTURE_UNCERTIFIED_UNTESTED_NOT_NULL'
 assert block['classification']==control['classification']==state['status']==classification
 assert not any(control[k] for k in ['stochastic_execution_authorized','null_execution_authorized','power_execution_authorized','real_response_authorized','future_real_signed_response_authorized','retry_authorized','automatic_retry'])
 assert control['execution_count_limit']==0 and not block['valid_trial_manifest_frozen'] and not block['stochastic_worker_certified']
 for k in ['null_Monte_Carlo_trials','power_Monte_Carlo_trials','synthetic_calibration_draws','bootstrap_draws_executed','real_response_openings','future_Y_reads','future_real_signed_response_computations','broker_contacts','historical_requests','new_acquisition','candidate_frozen_count','orders']:assert raw[k]==0,k
 checks['zero_statistical_execution_real_response_acquisition_and_orders']=True
 result={'schema':'TRIAD_V6_DUAL_LAYER_BLOCKED_EXACT_HEAD_VALIDATION_V1','starting_head':start,'validated_authority_head':head,'validated_authority_tree_sha':git('rev-parse','HEAD^{tree}'),'all_validation_checks_pass':True,'architecture_compatibility_gate_pass':False,'classification':classification,'checks':checks,'checker_not_reexecuted':True,'oracle_not_reexecuted':True,'actual_support_interpreter_not_reexecuted':True,'no_null_or_power_draws':True,'source_bindings':{str(p.relative_to(R)):sha(p) for p in P.iterdir() if p.is_file()},'validator_sha256':sha(Path(__file__)),'validator_ref':'research_core_v4/triad_v6/validate_dual_layer_blocked_head_v1.py','final_head_resolution':'Commit containing this record: only this validation record and its bound validator may differ from validated_authority_head. Final live ref, exact delta and all payload hashes must be checked after publication.'}
 print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__':main(sys.argv[1])
