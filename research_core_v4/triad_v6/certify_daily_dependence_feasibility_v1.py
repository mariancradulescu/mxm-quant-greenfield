"""Exact deterministic semantic witnesses. No RNG, bootstrap, MC or Y reader."""
from pathlib import Path
from fractions import Fraction as F
import hashlib, json
P=Path(__file__).resolve().parent; R=P.parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def main():
 plan=read(P/'DUAL_LAYER_DEPENDENCE_FEASIBILITY_GATE_PLAN_V1.json')
 for path,digest in plan['input_bindings'].items(): assert sha(R/path)==digest,path
 assert sha(Path(__file__))==plan['checker_sha256']
 assert sha(P/'DAILY_DEPENDENCE_NULL_COMPATIBILITY_PROOF_V1.md')==plan['proof_sha256']
 design=read(R/'research_core_v4/triad_v2/TRIAD_V2_ESTIMAND_NUISANCE_DESIGN_V1.json')
 envelope=read(R/'research_core_v4/triad_v2/EXACT_DEPENDENCE_ENVELOPE_RAW_AUDIT_V1.json')
 assert 'E[epsilon|' in design['scientific_estimand']['model_null']
 assert 'pasttraining' in design['scientific_estimand']['model_null']
 assert 'past,retention' in design['scientific_estimand']['identification']
 assert envelope['generic_AR025_unit'].startswith('daily12leaf score vector;')
 assert envelope['generic_AR050_unit'].startswith('daily12leaf score vector;')
 clocks=design['causal_clock']['decision_UTC_hours'];horizons=design['horizons_minutes']
 purge=design['nuisance_learning']['embargo_minutes_after_maturity']
 latest_admissible=max(clocks)*60+max(horizons)+5+purge
 assert latest_admissible==1385 and latest_admissible<1440
 assert design['nuisance_learning']['update_cadence'].startswith('Each UTCday00:00')
 summary=read(P/'ACTUAL_NUMERICAL_SUPPORT_SUMMARY_V1.json')
 leaves=[{'cohort':x['cohort'],'horizon_minutes':x['horizon_minutes']} for x in summary['leaf_support']]
 assert leaves==[{'cohort':c,'horizon_minutes':h} for c in design['universe']['cohorts'] for h in horizons]
 assert len(leaves)==12 and summary['complete_12_leaf_support_pass'] and summary['all_actual_safety_certificates_pass']
 # Exact algebraic baseline-cancellation witness, including an AR baseline.
 X=[[F(1),F(i),F(i*i)] for i in range(5)];r=list(map(F,[1,-4,6,-4,1]))
 assert all(sum(r[i]*X[i][j] for i in range(5))==0 for j in range(3))
 cases=[]
 for rho in [F(1,4),F(1,2)]:
  previous=[F(i+1) for i in range(12)]
  conditional=[rho*v for v in previous]
  assert any(v!=0 for v in conditional)
  # A unit stationary diagonal covariance gives Gamma1=rho I, not zero.
  gamma1=[[str(rho if i==j else F(0)) for j in range(12)] for i in range(12)]
  beta=[rho*F(j+1) for j in range(3)]
  Y=[sum(X[i][j]*beta[j] for j in range(3)) for i in range(5)]
  assert sum(r[i]*Y[i] for i in range(5))==0
  fourth=F(3)+F(6)*(1-rho*rho)/(1+rho*rho)
  assert fourth!=F(9)
  cases.append({'case':'DAILY_AR025' if rho==F(1,4) else 'DAILY_AR050','rho_exact':str(rho),'required_score_AR_conditional_mean_given_prior_score':[str(v) for v in conditional],'inherited_null_conditional_mean':'0 in every leaf','unit_variance_stationary_AR_lag1_covariance':gamma1,'conditional_null_compatible':False,'AR_baseline_score_numerator_exact':'0','AR_multiplier_times_independent_centered_score_lag1_covariance_exact':'0','t5_innovation_fourth_moment':'9','stationary_linear_AR_fourth_moment_exact':str(fourth),'t5_marginal_preserved_by_linear_AR':False})
 result={'schema':'TRIAD_V6_DUAL_LAYER_DEPENDENCE_FEASIBILITY_RAW_V1','plan_sha256':sha(P/'DUAL_LAYER_DEPENDENCE_FEASIBILITY_GATE_PLAN_V1.json'),'checker_sha256':sha(Path(__file__)),'proof_sha256':plan['proof_sha256'],'input_bindings':plan['input_bindings'],'method':'EXACT_RATIONAL_ALGEBRA_AND_FROZEN_SOURCE_CALENDAR_TRACE_NO_RNG','deterministic_witness_assertions_pass':True,'architecture_compatibility_gate_pass':False,'required_daily_AR_unit':'daily joint 12-leaf score vector','latest_previous_day_maturity_buffer_purge_minute':latest_admissible,'next_update_minute':1440,'prior_day_retained_scores_in_next_day_past_training_information':True,'original_calendar_retained':True,'complete_12_leaf_inclusion':leaves,'V6_numerical_support_PASS_preserved':True,'cases':cases,'classification_pending_raw_persistence':True,'null_Monte_Carlo_trials':0,'power_Monte_Carlo_trials':0,'synthetic_calibration_draws':0,'bootstrap_draws_executed':0,'real_response_openings':0,'future_Y_reads':0,'future_real_signed_response_computations':0,'broker_contacts':0,'historical_requests':0,'new_acquisition':0,'candidate_frozen_count':0,'orders':0}
 with (P/'DUAL_LAYER_DEPENDENCE_FEASIBILITY_RAW_V1.json').open('x') as f:f.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'deterministic_witness_assertions_pass':True,'architecture_compatibility_gate_pass':False,'cases':cases},sort_keys=True))
if __name__=='__main__':main()
