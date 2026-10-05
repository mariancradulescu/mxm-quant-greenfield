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
 for e in d['evidence']:assert e['serial_distributed_bit_exact'] and e['all_raw_row_digests_match']
 for k in ['null_Monte_Carlo_trials','power_Monte_Carlo_trials','real_response_openings','future_Y_reads','broker_contacts','new_acquisition','candidate_frozen_count','orders']:assert d[k]==0
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
out={'schema':'TRIAD_V7_DISTRIBUTED_PREARM_RESULT_V1','status':'PASS_READY_FOR_SEPARATE_NULL_ARM' if passed else 'PREOUTCOME_BLOCKED_V7_DISTRIBUTED_EXECUTION_ROUTE_UNCERTIFIED_UNTESTED_NOT_NULL','pass':passed,'source_head':os.environ['GITHUB_SHA'],'workflow_run_id':os.environ['GITHUB_RUN_ID'],'plan_sha256':route.w.sha(P/'PREARM_PLAN_V1.json'),'twenty_runner_slots_observed_peak':peak,'complete_17_null_case_proofs':True,'complete_power_stress_case_proofs':[0,13,15,16],'runtime_case_projections':rows,'projected_17_case_null_campaign_wall_seconds':wall,'future_power_projection':'NOT_CERTIFIED; representative three-cell complete power fixtures only, no full63-cell campaign throughput claim','full_reference_hashes_verified':True,'Actions_write_probe_checkpoint':'f0d1345e758e3a152f1047a6cc8a1fdb035b5dce','null_Monte_Carlo_trials':0,'power_Monte_Carlo_trials':0,'real_response_openings':0,'future_Y_reads':0,'broker_contacts':0,'new_acquisition':0,'candidate_frozen_count':0,'orders':0,'ARM_present':False,'no_partial_engineering_counts_as_scientific_evidence':True}
for f in files:(P/f.name).write_bytes(f.read_bytes())
(P/'PREARM_RESULT_V1.json').write_bytes(route.w.canonical(out))
print(json.dumps({'pass':passed,'projected_hours':wall/3600,'runner_slot_peak':peak}))
