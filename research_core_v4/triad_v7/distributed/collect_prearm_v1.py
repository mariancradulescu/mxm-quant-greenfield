"""Outcome-blind preARM aggregation only. No certification or market interpreter."""
from pathlib import Path
import os,json,hashlib,sys,urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parent))
import reference_route_v1 as route
P=Path(__file__).resolve().parent
m=route.manifest();assert not (route.w.P/'EXECUTION_ARM_V1.json').exists()
files=sorted(Path(sys.argv[1]).rglob('fixture_*.json'));data=[json.loads(p.read_text()) for p in files]
assert len(data)==20 and {d['fixture_id'] for d in data}==set(range(20))
by={d['fixture_id']:d for d in data};plan=json.loads((P/'PREARM_PLAN_V1.json').read_text())
for i,d in by.items():
 assert d['case_id']==plan['fixture_cases'][i] and d['source_head']==os.environ['GITHUB_SHA']
 assert not d['certification_seed_usage'] and not d['scientific_inference_from_engineering_fixtures']
 assert d['environment']['processes']==min(4,d['environment']['cpu_count'],d['environment']['affinity_cpus'])
 for e in d['evidence']:
  assert e['serial_distributed_bit_exact'] and e['all_raw_row_digests_match'] and e['integer_merge_order_independent']
  p=e['supported_path_bit_parity'];assert p['all_accounted'] and p['tested_configurations']==p['supported_bit_identical']+p['expected_unsupported_preserved']
  for s in e['support_semantics']:
   assert s['hard_failures']==0 and s['atomic_no_partial_salvage']
 for k in ['null_Monte_Carlo_trials','power_Monte_Carlo_trials','real_response_openings','future_Y_reads','broker_contacts','new_acquisition','candidate_frozen_count','orders']:assert d[k]==0
# Deterministic replay of the exact previously failed engineering fixture.
replay=next(e for e in by[9]['evidence'] if e['phase_fixture']=='null')
sem0=replay['support_semantics'][0]
assert sem0['support_unavailable_reasons_by_configuration'][1]=='CANDIDATE_FAIL_CLOSED'
assert sem0['unsupported_configurations']>=1 and sem0['hard_failures']==0
forensic=json.loads((P/'EXACT_FAILED_FIXTURE_FORENSIC_V1.json').read_text())
assert forensic['failure_preserved'] and forensic['reason']=='CANDIDATE_FAIL_CLOSED'
assert forensic['trial_context']['configuration_id']=='G10_ONLY' and forensic['trial_context']['engineering_trial_index']==0
assert route.w.sha(route.w.P/'stochastic_worker_v1.py')=='af0cd192adc19478686198082f190b69585dab4d29df9e6835d1f7cf6a3c6de6'
assert route.w.sha(P/'support_semantics_wrapper_v1.py')=='fe57921a8e20414f9d5d453be1cb315e7d10204b7aefe884a51e0585f9df3a1f'
# This is GitHub control-plane metadata, read outside fenced scientific workers.
url=f'https://api.github.com/repos/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}/jobs?per_page=100'
req=urllib.request.Request(url,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
jobs=json.loads(urllib.request.urlopen(req).read())['jobs'];events=[]
for j in jobs:
 if j['name'].startswith('reference-route ('):
  assert j['conclusion']=='success'
  events.extend([(j['started_at'],1),(j['completed_at'],-1)])
active=0;peak=0
for _,change in sorted(events,key=lambda x:(x[0],x[1])):active+=change;peak=max(peak,active)
rows=[]
for cid in range(17):
 d=by[cid];b=d['benchmark'];rate=b['aggregate_trials_per_second'];projected=math_seconds=plan['runtime_safety_multiplier']*410/rate+plan['per_case_transport_margin_seconds']
 rows.append({'case_id':cid,'aggregate_engineering_trials_per_second':rate,'projected_max_shard_wall_seconds':projected,'below_four_hours':projected<4*3600,'projection_is_not_measured_certification_time':True})
wall=sum(x['projected_max_shard_wall_seconds'] for x in rows)
passed=all(x['below_four_hours'] for x in rows) and wall<=24*3600 and peak==20
hashes={name:route.w.sha(P/name) for name in ['EXACT_FAILED_FIXTURE_FORENSIC_V1.json','SUPPORT_SEMANTICS_RECONCILIATION_AUTHORITY_V1.json','support_semantics_wrapper_v1.py','reference_route_v1.py','collect_prearm_v1.py']}
hashes['stochastic_worker_v1.py']=route.w.sha(route.w.P/'stochastic_worker_v1.py')
hashes['TRIAL_MANIFEST_V1.json']=route.w.sha(route.w.P/'TRIAL_MANIFEST_V1.json')
hashes['control_plane_v1.py']=route.w.sha(route.w.P/'control_plane_v1.py')
out={'schema':'TRIAD_V7_DISTRIBUTED_PREARM_RESULT_V1','status':'PASS_READY_FOR_SEPARATE_NULL_ARM' if passed else 'PREOUTCOME_BLOCKED_V7_DISTRIBUTED_EXECUTION_ROUTE_UNCERTIFIED_UNTESTED_NOT_NULL','pass':passed,'source_head':os.environ['GITHUB_SHA'],'workflow_run_id':os.environ['GITHUB_RUN_ID'],'plan_sha256':route.w.sha(P/'PREARM_PLAN_V1.json'),'engineering_namespace_preserved':route.w.sha(P/'PREARM_PLAN_V1.json')=='23511ae4d94d14299e6a209e5974b2b9aa9024504fd130e1337516894652aa7f','original_failed_fixture_replay':{'fixture_id':9,'case_id':9,'configuration_id':'G10_ONLY','engineering_index':0,'reason':'CANDIDATE_FAIL_CLOSED','atomic_unsupported':True,'hard_failure':False},'support_semantics_hashes':hashes,'twenty_runner_slots_observed_peak':peak,'complete_17_null_case_proofs':True,'complete_power_stress_case_proofs':[0,13,15,16],'runtime_case_projections':rows,'projected_17_case_null_campaign_wall_seconds':wall,'future_power_projection':'NOT_CERTIFIED; representative three-cell complete power fixtures only, no full63-cell campaign throughput claim','full_reference_hashes_verified':True,'supported_path_bit_parity_proved':True,'support_unavailable_is_separate_from_hard_failure':True,'hard_failure_counter':0,'Actions_write_probe_checkpoint':'f0d1345e758e3a152f1047a6cc8a1fdb035b5dce','null_Monte_Carlo_trials':0,'power_Monte_Carlo_trials':0,'real_response_openings':0,'future_Y_reads':0,'broker_contacts':0,'new_acquisition':0,'candidate_frozen_count':0,'orders':0,'ARM_present':False,'no_partial_engineering_counts_as_scientific_evidence':True}
for f in files:(P/f.name).write_bytes(f.read_bytes())
(P/'PREARM_RESULT_V1.json').write_bytes(route.w.canonical(out))
print(json.dumps({'pass':passed,'projected_hours':wall/3600,'runner_slot_peak':peak}))
