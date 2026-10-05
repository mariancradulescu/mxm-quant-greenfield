"""Read-only exact-head validation after failed preARM; no scientific execution."""
from pathlib import Path
import hashlib,json,subprocess,sys
R=Path.cwd();P=R/'research_core_v4/triad_v7/distributed';start='abe85d6dbf19436a88a539f03599af940ed67774'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
head=git('rev-parse','HEAD');record=json.loads((P/'HISTORICAL_SCIENCE_PRESERVATION_V1.json').read_text());authority=json.loads((P/'DISTRIBUTED_PREARM_BLOCKER_AUTHORITY_V1.json').read_text());raw=json.loads((P/'PREARM_ACTIONS_FAILURE_RAW_V1.json').read_text())
for p,h in record['preserved_file_hashes'].items():assert sha(R/p)==h,p
for p,h in authority['bindings'].items():assert sha(R/p)==h,p
plan=json.loads((P/'PREARM_PLAN_V1.json').read_text())
for p,h in plan['bindings'].items():assert sha(R/p)==h,p
assert authority['status']=='PREOUTCOME_BLOCKED_V7_DISTRIBUTED_EXECUTION_ROUTE_UNCERTIFIED_UNTESTED_NOT_NULL'
assert not authority['actual_null_certification_launched'] and authority['ARM_sha256'] is None
assert raw['failed_case_id']==9 and raw['failed_job_id']==111928471123 and raw['workflow_run']['id']==37358974210
assert sum(j['conclusion']=='failure' for j in raw['jobs'])==1 and sum(j['conclusion']=='cancelled' for j in raw['jobs'])==19
for k in ['null_Monte_Carlo_trials','power_Monte_Carlo_trials','real_response_openings','future_Y_reads','broker_contacts','new_acquisition','candidate_frozen_count','orders']:assert authority[k]==raw[k]==0,k
assert not (P.parent/'EXECUTION_ARM_V1.json').exists()
probe=git('show','f0d1345e758e3a152f1047a6cc8a1fdb035b5dce:research_core_v4/triad_v7/distributed/ACTIONS_WRITE_PROBE_CHECKPOINT_V1.json');assert json.loads(probe)['workflow_run_id']=='37358046361'
changedprobe=git('diff','--name-only','2ec261f08d28059aeba6beda6aeb1bddfbb83e4a','f0d1345e758e3a152f1047a6cc8a1fdb035b5dce').splitlines();assert changedprobe==['research_core_v4/triad_v7/distributed/ACTIONS_WRITE_PROBE_CHECKPOINT_V1.json']
old=json.loads(git('show',start+':research_core_v4/state/V4_STATE.json'));state=json.loads((R/'research_core_v4/state/V4_STATE.json').read_text());allowed={'current_authority','status','next_action','stop_boundary','triad_v7_execution_engineering_blocker_authority'}
assert {k:v for k,v in old.items() if k not in allowed}=={k:v for k,v in state.items() if k not in allowed}
assert state['triad_v7_execution_engineering_blocker_authority']==old['current_authority'] and state['current_authority']['sha256']==sha(P/'DISTRIBUTED_PREARM_BLOCKER_AUTHORITY_V1.json')
paths=git('ls-tree','-r','--name-only',head).splitlines();assert not any('triad_v8/' in p for p in paths)
changed=git('diff','--name-only',start,head).splitlines();assert all(p.startswith('research_core_v4/triad_v7/distributed/') or p.startswith('.github/workflows/triad-v7-distributed-') or p=='research_core_v4/state/V4_STATE.json' for p in changed)
chain=git('rev-list','--reverse',start+'..'+head).splitlines()
out={'schema':'TRIAD_V7_DISTRIBUTED_PREARM_EXACT_HEAD_VALIDATION_V1','starting_live_head':start,'validated_payload_head':head,'checkpoint_chain_through_payload':chain,'status':'PASS_DURABLE_PREARM_BLOCKER_AND_PRESERVATION_ONLY_NOT_ROUTE_CERTIFICATION','preserved_historical_science_files':len(record['preserved_file_hashes']),'canonical_historical_state_unchanged':True,'Actions_write_capability_proved':True,'full_distributed_route_certified':False,'ARM_present':False,'actual_null_certification_launched':False,'authority_sha256':sha(P/'DISTRIBUTED_PREARM_BLOCKER_AUTHORITY_V1.json'),'payload_hashes':{p:sha(R/p) for p in changed},**{k:0 for k in ['null_Monte_Carlo_trials','power_Monte_Carlo_trials','real_response_openings','future_Y_reads','broker_contacts','new_acquisition','candidate_frozen_count','orders']},'final_containing_commit_policy':'Only validation record and this validation source may be added after validated payload; final live/head/delta/hashes checked separately.'}
Path(sys.argv[1]).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='payload_hashes'}))
