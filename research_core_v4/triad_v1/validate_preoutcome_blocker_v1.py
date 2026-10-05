"""Read-only exact-HEAD audit of preserved history, binding and stop boundary.
No response/calibration simulation or broker imports. Rechecks saved arithmetic.
"""
import pathlib,subprocess,json,hashlib,base64,io,sys
import numpy as np
R=pathlib.Path(__file__).resolve().parents[2];START='d118b4f836abb8f7a76c85149d95a696d446f828';B='research_core_v4/triad_v1/';S='research_core_v4/state/'
def git(*a):return subprocess.check_output(['git','-C',str(R),*a])
def read(p):return json.loads((R/p).read_bytes())
def h(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
head=git('rev-parse','HEAD').decode().strip()
if len(sys.argv)>1:assert head==sys.argv[1]
assert not git('diff','--name-only'), 'tracked file differs from exacthead'
for p in git('ls-tree','-r','--name-only',START).decode().splitlines():
 if p!=S+'V4_STATE.json':assert git('show',START+':'+p)==(R/p).read_bytes(),'historical mutation: '+p
old=json.loads(git('show',START+':'+S+'V4_STATE.json'));now=read(S+'V4_STATE.json');allowed={'status','next_action','stop_boundary','triad_relational_state_wave'}
assert {k:v for k,v in old.items() if k not in allowed}=={k:v for k,v in now.items() if k not in allowed}
b=read(S+'TRIAD_RELATIONAL_STATE_V1_PREOUTCOME_BLOCKER_V1.json')
for p,want in b['bindings'].items():assert h(p)==want
assert h(now['triad_relational_state_wave']['blocker_ref'])==now['triad_relational_state_wave']['blocker_sha256']
assert now['status']=='TRIAD_V1_PREOUTCOME_BLOCKED_INCREMENTAL_ESTIMAND_NOT_IDENTIFIED'
assert not b['READY_NOT_EXECUTED'] and not b['broader_source_family_closed'];w=now['triad_relational_state_wave'];assert not w['real_response_authorized'] and w['maximum_response_openings']==0
l=read(B+'ACCEPTED_FX_ARCHIVE_RECOVERY_LEDGER_V1.json');assert l['all75_recovered'] and l['verified_recovered_series']==75
assert all(x['expected_sha256']==x['observed_sha256'] for x in l['archives']);assert all(x['series_sha256']==x['observed_series_sha256'] for x in l['series'])
i=read(B+'CANONICAL_FX_RELATION_COHORT_INVENTORY_V1.json');assert i['accepted_FX_identities']==75 and i['unique_currency_count']==21 and i['complete_canonical_triads']==107 and i['structurally_incomplete_currency_triples']==1223
assert not i['future_response_or_alpha_used'] and not i['prices_opened']
ids={x['symbol_id']:x for x in i['identities']};relations=i['complete_relations'];assert len({x['relation_id'] for x in relations})==107
for rr in relations:
 currency_exposure={}
 for term in rr['closure_terms']:
  edge=ids[term['symbol_id']];coef=term['coefficient'];currency_exposure[edge['base']]=currency_exposure.get(edge['base'],0)+coef;currency_exposure[edge['quote']]=currency_exposure.get(edge['quote'],0)-coef
 assert all(v==0 for v in currency_exposure.values()),'invalid currency algebra'
 assert rr['closure_terms'][0]['symbol_id']==rr['target_symbol_id'] and rr['closure_terms'][0]['coefficient']==rr['target_canonical_sign']
s=read(B+'EXACT_SUPPORT_PREFIX_RAW_RESULT_V1.json');assert s['development_price_rows_converted']==0 and s['future_signed_response_computations']==0 and s['real_response_openings']==0
assert len(s['prefix_fits'])==107 and all(x['pass'] and x['design_rank']==10 for x in s['prefix_fits'])
assert s['all_support_preconditions_pass'] and len(s['leaf_support'])==12
for x in s['leaf_support']:assert x['pass'] and x['valid_days']==148 and x['supported_blocks']==15 and x['fixed70day_third_counts']==[48,50,50]
payload=base64.b64decode(s['actual_mask_npz_base64']);assert hashlib.sha256(payload).hexdigest()==s['actual_mask_npz_sha256']
mask=np.load(io.BytesIO(payload));assert mask['relation_clock_horizon'].shape==(210,8,107,4)
assert np.array_equal(mask['cohort_clock_horizon'].sum(axis=1)>=4,mask['cohort_daily_horizon'])
f=read(B+'EXACT_DESIGN_SUPPORT_IMPLEMENTATION_FREEZE_V1.json')
for p,want in f['bindings'].items():assert h(p)==want
plan=read(B+'INCREMENTAL_NULL_SEMANTICS_CERTIFICATION_PLAN_V1.json');raw=read(B+'INCREMENTAL_NULL_SEMANTICS_RAW_RESULT_V1.json')
assert h(B+'INCREMENTAL_NULL_SEMANTICS_CERTIFICATION_PLAN_V1.json')==raw['plan_sha256'];assert h(plan['implementation_ref'])==raw['implementation_sha256']==plan['implementation_sha256'];assert raw['MC_trials_executed']==0 and raw['seeds_used'] is None
assert len(raw['rows'])==48 and not raw['all_preflight_gates_pass']
failed=0
for x in raw['rows']:
 expected=0. if x['regime'].startswith('STABLE') else x['baseline_direction']*x['horizon_minutes']/60
 assert x['conditional_incremental_information']==0 and abs(x['mean_frozen_score']-expected)<1e-10
 assert x['semantic_null_invariance_pass']==(abs(x['mean_frozen_score'])<=plan['numerical_zero_tolerance']);failed+=not x['semantic_null_invariance_pass']
assert failed==24 and b['failed_gate']['failed_checks']==24
assert b['global_null_FWER_results'] is None and b['partial_null_FWER_results'] is None and b['power_curves'] is None
for key in ['real_response_openings','future_real_signed_response_computations','broker_contacts','historical_requests','new_data_acquisition','candidate_frozen_count','orders']:assert b['task_counters'][key]==0
assert b['task_counters']['Runtime_V2']=='READ_ONLY' and not any(b['task_counters'][k] for k in ['protected_forward_opened','confirmation_opened','live_trading_started'])
for cp in b['checkpoints'].values():git('merge-base','--is-ancestor',cp,head)
assert git('show',b['checkpoints']['semantic_certification_plan']+':'+plan['implementation_ref'])==(R/plan['implementation_ref']).read_bytes()
from research_core_v4.post_publication_integrity_v1 import check_state
check_state(now)
print(json.dumps({'status':'PASS_PERSISTED_BLOCKER_NO_RESPONSE_AUTHORITY_HISTORICAL_BYTES_UNCHANGED','head':head,'accepted_FX_hash_verified':75,'canonical_relations':107,'semantic_failed_checks':24,'stochastic_FWER_or_power_certification_claimed':False,'market_or_broker_operations':0},sort_keys=True))
