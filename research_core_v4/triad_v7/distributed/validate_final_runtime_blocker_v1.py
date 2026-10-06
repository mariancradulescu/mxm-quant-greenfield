"""Final exact V7 runtime-blocker integrity validation.
Read-only validation of frozen science/evidence plus authorized governance update.
"""
from pathlib import Path
import hashlib,json,subprocess,sys
R=Path.cwd()
D=R/'research_core_v4/triad_v7/distributed'
BASE='ac44ced715e92911c4a40357915597fe1fde6058'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git(*args,bytes_=False):
    return subprocess.check_output(['git',*args],cwd=R,text=not bytes_)
def base_bytes(path):
    return git('show',BASE+':'+path,bytes_=True)

head=git('rev-parse','HEAD').strip()
prearm_path='research_core_v4/triad_v7/distributed/PREARM_RESULT_V1.json'
worker_path='research_core_v4/triad_v7/stochastic_worker_v1.py'
v6_path='research_core_v4/triad_v6/NUMERICAL_PRODUCTION_AUTHORITY_V1.json'
v7_pre_path='research_core_v4/triad_v7/PREEXECUTION_AUTHORITY_V1.json'
authority_path='research_core_v4/triad_v7/distributed/FINAL_V7_RUNTIME_BLOCKER_AUTHORITY_V1.json'
state_path='research_core_v4/state/V4_STATE.json'

# Preserve every distributed artifact that already existed at accepted PREARM HEAD.
old_paths=git('ls-tree','-r','--name-only',BASE,'research_core_v4/triad_v7/distributed').splitlines()
for p in old_paths:
    assert (R/p).exists(),('MISSING_PRESERVED_DISTRIBUTED_ARTIFACT',p)
    assert (R/p).read_bytes()==base_bytes(p),('DISTRIBUTED_ARTIFACT_DRIFT',p)

# Preserve frozen scientific/numerical authorities byte-for-byte from accepted HEAD.
for p in [worker_path,v6_path,v7_pre_path]:
    assert (R/p).read_bytes()==base_bytes(p),('FROZEN_AUTHORITY_DRIFT',p)

assert sha(R/worker_path)=='af0cd192adc19478686198082f190b69585dab4d29df9e6835d1f7cf6a3c6de6'
assert sha(R/v6_path)=='52775bdde358280ca56b37527454ad8cc11e8bc7d1316aca987a8a8585d30701'
assert sha(R/v7_pre_path)=='6a57a5a76a9b9d866358b33599d3495d24e0bfde82c701897180c9182b855a3d'
assert sha(R/prearm_path)==hashlib.sha256(base_bytes(prearm_path)).hexdigest()

prearm=json.loads((R/prearm_path).read_text())
assert prearm['workflow_run_id']=='37406575198'
assert prearm['pass'] is False
assert prearm['complete_17_null_case_proofs'] is True
assert prearm['supported_path_bit_parity_proved'] is True
assert prearm['hard_failure_counter']==0
assert prearm['twenty_runner_slots_observed_peak']==20
assert prearm['original_failed_fixture_replay']=={
 'atomic_unsupported':True,'case_id':9,'configuration_id':'G10_ONLY',
 'engineering_index':0,'fixture_id':9,'hard_failure':False,'reason':'CANDIDATE_FAIL_CLOSED'}
assert prearm['runtime_case_projections'][1]['projected_max_shard_wall_seconds']==14681.485864545008
assert prearm['runtime_case_projections'][13]['projected_max_shard_wall_seconds']==14586.625566950011
assert prearm['projected_17_case_null_campaign_wall_seconds']==171653.76410611515
assert prearm['null_Monte_Carlo_trials']==prearm['power_Monte_Carlo_trials']==0
for k in ['real_response_openings','future_Y_reads','broker_contacts','new_acquisition','candidate_frozen_count','orders']:
    assert prearm[k]==0,k
assert prearm['ARM_present'] is False

authority=json.loads((R/authority_path).read_text())
assert sha(R/authority_path)=='c519897953ad361d6949a76f14cb0e374705b1d296378179f58ac375daf34fd8'
assert authority['status']=='PREOUTCOME_BLOCKED_V7_EXECUTION_RUNTIME_INFEASIBLE_UNDER_FROZEN_MACHINE_SIDE_FEASIBILITY_GATES_UNTESTED_NOT_NULL'
assert authority['exact_v7_parked'] is True
assert authority['classification']=={
 'scientific_null':False,'statistical_null':False,'economic_null':False,
 'market_information_null':False,'operational_compute_blocker':True}
assert all(v==0 for v in authority['counters'].values())
assert not any(authority['authorization'].values())

state=json.loads((R/state_path).read_text())
base_state=json.loads(base_bytes(state_path))
allowed={'as_of_date','current_authority','current_next_action_type','status','stop_boundary',
         'triad_v7_distributed_prearm_blocker_authority','triad_v7_final_runtime_blocker_authority'}
assert {k:v for k,v in state.items() if k not in allowed}=={k:v for k,v in base_state.items() if k not in allowed}
assert state['triad_v7_distributed_prearm_blocker_authority']==base_state['current_authority']
assert state['current_authority']['sha256']==sha(R/authority_path)
assert state['current_authority']['exact_V7_parked'] is True
assert state['status']==authority['status']
assert state['current_next_action_type']=='INDEPENDENT_PROJECT_WIDE_INFORMATION_SOURCE_RESELECTION_GOVERNANCE'
assert state['triad_v7_final_runtime_blocker_authority']['prearm_workflow_run_id']==37406575198

assert not (R/'research_core_v4/triad_v7/EXECUTION_ARM_V1.json').exists()
all_paths=git('ls-tree','-r','--name-only','HEAD').splitlines()
assert not any('/triad_v8/' in p or p.startswith('research_core_v4/triad_v8/') for p in all_paths)

out={
 'schema':'TRIAD_V7_FINAL_RUNTIME_BLOCKER_EXACT_INTEGRITY_VALIDATION_V1',
 'accepted_prearm_head':BASE,
 'validated_payload_head':head,
 'status':'PASS_EXACT_V7_PARKED_RUNTIME_BLOCKER_INTEGRITY',
 'distributed_artifacts_preserved_exact_count':len(old_paths),
 'PREARM_RESULT_V1_unchanged':True,
 'stochastic_worker_v1_unchanged':True,
 'stochastic_worker_v1_sha256':sha(R/worker_path),
 'V6_numerical_authority_unchanged':True,
 'V6_numerical_authority_sha256':sha(R/v6_path),
 'V7_scientific_preexecution_authority_unchanged':True,
 'V7_scientific_preexecution_authority_sha256':sha(R/v7_pre_path),
 'final_runtime_blocker_authority_sha256':sha(R/authority_path),
 'V4_STATE_authorized_delta_only':True,
 'ARM_present':False,
 'null_Monte_Carlo_trials':0,
 'power_Monte_Carlo_trials':0,
 'real_response_openings':0,
 'future_Y_reads':0,
 'broker_contacts':0,
 'new_acquisition':0,
 'candidate_frozen_count':0,
 'orders':0,
 'V8_present':False,
 'exact_V7_parked':True,
 'broader_relational_family_closed':False,
 'next_action':'STOP_FOR_INDEPENDENT_PROJECT_WIDE_INFORMATION_SOURCE_RESELECTION_GOVERNANCE',
 'final_containing_commit_policy':'After this payload validation, only this validation record may be committed; final live HEAD and exact delta are independently verified.'
}
Path(sys.argv[1]).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(json.dumps(out,sort_keys=True))
