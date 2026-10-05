"""Exact committed payload validation; never invokes stochastic worker."""
from pathlib import Path
import hashlib,json,subprocess,sys
R=Path.cwd();P=R/'research_core_v4/triad_v7/engineering'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
start=json.loads((P/'STARTING_INTEGRITY_V1.json').read_text());head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
for name,h in start['preserved_file_hashes'].items():assert sha(R/name)==h,name
for plan_name in ['ENGINEERING_TEST_PLAN_V1.json','FULL_SCORE_BENCHMARK_PLAN_V1.json']:
 plan=json.loads((P/plan_name).read_text())
 for name,h in plan['bindings'].items():assert sha(R/name)==h,name
raw=json.loads((P/'MECHANICAL_ENGINEERING_RAW_V1.json').read_text());bench=json.loads((P/'FULL_SCORE_BENCHMARK_RAW_V1.json').read_text());authority=json.loads((P/'EXECUTION_ENGINEERING_BLOCKER_AUTHORITY_V1.json').read_text())
for data in [raw,bench,authority]:
 for key in ['null_Monte_Carlo_trials','power_Monte_Carlo_trials','real_response_openings','future_Y_reads','broker_contacts','new_acquisition','candidate_frozen_count','orders']:assert data[key]==0,key
assert raw['plan_sha256']==sha(P/'ENGINEERING_TEST_PLAN_V1.json') and bench['plan_sha256']==sha(P/'FULL_SCORE_BENCHMARK_PLAN_V1.json')
assert len(raw['fixtures'])==68 and len(raw['sharding'])==21
assert all(x['daily_leaveout_valid_bit_exact'] for x in bench['results'])
assert authority['status']=='PREOUTCOME_BLOCKED_V7_EXECUTION_ENGINE_OR_POWER_CONTRACT_UNCERTIFIED_UNTESTED_NOT_NULL'
assert not authority['statistical_execution_authorized'] and not authority['complete_campaign_engine_certified']
for name,h in authority['bindings'].items():assert sha(R/name)==h,name
assert not (P.parent/'EXECUTION_ARM_V1.json').exists()
oldstate=json.loads(subprocess.check_output(['git','show',start['starting_live_head']+':research_core_v4/state/V4_STATE.json'],text=True));state=json.loads((R/'research_core_v4/state/V4_STATE.json').read_text())
allowed={'status','current_authority','next_action','stop_boundary','triad_v7_scientific_preexecution_authority'}
assert {k:v for k,v in state.items() if k not in allowed}=={k:v for k,v in oldstate.items() if k not in allowed}
assert state['triad_v7_scientific_preexecution_authority']==oldstate['current_authority']
assert state['current_authority']['sha256']==sha(P/'EXECUTION_ENGINEERING_BLOCKER_AUTHORITY_V1.json')
paths=subprocess.check_output(['git','ls-tree','-r','--name-only',head],text=True).splitlines()
assert not any('triad_v8/' in p for p in paths)
changed=subprocess.check_output(['git','diff','--name-only',start['starting_live_head'],head],text=True).splitlines()
assert all(p.startswith('research_core_v4/triad_v7/engineering/') or p=='research_core_v4/state/V4_STATE.json' for p in changed)
out={'schema':'TRIAD_V7_EXECUTION_ENGINEERING_EXACT_HEAD_VALIDATION_V1','starting_head':start['starting_live_head'],'validated_payload_head':head,'status':'PASS_EXACT_DURABLE_BLOCKER_AND_PRESERVATION_NOT_ENGINE_CERTIFICATION','preserved_historical_science_files':len(start['preserved_file_hashes']),'historical_state_fields_unchanged':True,'V6_numerical_PASS_unchanged':True,'V7_scientific_preexecution_PASS_unchanged':True,'no_V8':True,'no_statistical_ARM':True,'null_Monte_Carlo_trials':0,'power_Monte_Carlo_trials':0,'real_response_openings':0,'future_Y_reads':0,'broker_contacts':0,'new_acquisition':0,'candidate_frozen_count':0,'orders':0,'payload_hashes':{p:sha(R/p) for p in paths if p.startswith('research_core_v4/triad_v7/engineering/') or p=='research_core_v4/state/V4_STATE.json'},'final_containing_commit_policy':'Only this validation record and its validator source may be added after validated_payload_head; final live branch and hashes checked separately.'}
Path(sys.argv[1]).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='payload_hashes'}))
