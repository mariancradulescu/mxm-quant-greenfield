"""Read-only durable V2 audit. No simulation, broker or market loader."""
from pathlib import Path
import json,hashlib,subprocess,sys
from stochastic_certification_driver_v1 import interpret
R=Path(__file__).resolve().parents[2];S='research_core_v4/state/';B='research_core_v4/triad_v2/';START='7e18a6a1176ce8d795b0aded0fb6ac760313de85'
def git(*x):return subprocess.check_output(['git','-C',str(R),*x])
def read(p):return json.loads((R/p).read_bytes())
def sha(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
head=git('rev-parse','HEAD').decode().strip()
if len(sys.argv)>1:assert head==sys.argv[1]
assert not git('diff','--name-only')
paths=git('ls-tree','-r','--name-only',START).decode().splitlines()
for p in paths:
 if p!=S+'V4_STATE.json':assert git('show',START+':'+p)==(R/p).read_bytes(),('historical mutation',p)
old=json.loads(git('show',START+':'+S+'V4_STATE.json'));state=read(S+'V4_STATE.json');allowed={'status','next_action','stop_boundary','triad_relational_state_v2_wave'}
assert {k:v for k,v in old.items() if k not in allowed}=={k:v for k,v in state.items() if k not in allowed}
assert sha(S+'TRIAD_RELATIONAL_STATE_V1_PREOUTCOME_BLOCKER_V1.json')=='4095666954df6f34aaf8b4d1057a7e66a5b7126f093a18cef02abf108a8b9f9c'
assert sha(S+'V4_DISCOVERY_PROTOCOL_V2.json')=='ce80c4a71fe2f49c3f9b6eba7797f47de6e2f49827bd97384e54b81e63f28be5'
assert sha(S+'V4_DISCOVERY_PROTOCOL_V2_SUPERSESSION_AUTHORITY_V1.json')=='b9f9bf43224e50f47a6f799a704b81934dbfabf0accf480c322e8d0b07145227'
wave=state['triad_relational_state_v2_wave'];f=read(wave['final_ref']);assert sha(wave['final_ref'])==wave['final_sha256']
for p,h in f['bindings'].items():assert sha(p)==h,(p,'binding')
for cp in f['checkpoints'].values():git('merge-base','--is-ancestor',cp,head)
plan=read(B+'EXACT_STOCHASTIC_CERTIFICATION_PLAN_V1.json')
for p,h in plan['bindings'].items():assert sha(B+p)==h,(p,'frozen implementation')
assert git('show',f['checkpoints']['stochastic_plan_freeze']+':'+B+'EXACT_STOCHASTIC_CERTIFICATION_PLAN_V1.json')==(R/(B+'EXACT_STOCHASTIC_CERTIFICATION_PLAN_V1.json')).read_bytes()
sem=read(B+'SEMANTIC_RAW_RESULT_V1.json');si=read(B+'SEMANTIC_INTERPRETATION_V1.json');assert si['all648_analytic_nulls_pass'] and si['all36_positive_controls_pass'] and si['all12_no_leakage_tests_pass']
support=read(B+'EXACT_SUPPORT_RAW_RESULT_V1.json');assert support['all_exact_timestamp_support_gates_pass'] and support['real_price_fields_parsed']==0
assert support['real_Y_or_relational_scores_computed']==0
for path in sorted((R/B).glob('RAW_NULL_CASE_*_V1.json')):
 raw=json.loads(path.read_text());assert raw['trials']==6144 and int(raw['seed'])==2026100522+1009*raw['case_id']
 ref=path.with_name(path.name.replace('RAW_NULL','INTERPRETED_NULL'));assert json.loads(ref.read_text())==interpret(raw,plan)
for path in sorted((R/B).glob('RAW_POWER_CASE_*_V1.json')):
 raw=json.loads(path.read_text());assert raw['trials']==2048 and int(raw['seed'])==2026100523+1009*raw['case_id']
 ref=path.with_name(path.name.replace('RAW_POWER','INTERPRETED_POWER'));assert json.loads(ref.read_text())==interpret(raw,plan)
for k in ['real_response_openings','future_real_signed_response_computations','broker_contacts','historical_requests','new_data_acquisition','candidate_frozen_count','orders']:assert f['task_counters'][k]==0
assert not any(f['task_counters'][k] for k in ['protected_forward_opened','confirmation_opened','live_trading_started']);assert f['task_counters']['Runtime_V2']=='READ_ONLY'
assert not f['broader_source_family_closed'] and f['V1_exact_law_preserved'] and not wave['real_response_authorized'] and wave['maximum_response_openings']==0
assert wave['current_action_type']==state['current_next_action_type']=='CORRECTED_EXISTING_DATA_DISCOVERY_ON_BROADER_ACCEPTED_EVIDENCE'
from research_core_v4.post_publication_integrity_v1 import check_state
check_state(state)
print(json.dumps({'status':'PASS_EXACT_HEAD_HISTORY_BINDINGS_SYNTHETIC_ARITHMETIC_AND_ZERO_MARKET_AUTHORITY','head':head,'classification':f['classification'],'independent_statistical_workflow_claimed':False,'real_or_broker_operations':0},sort_keys=True))
