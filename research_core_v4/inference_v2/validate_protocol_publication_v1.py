"""Read-only exact-HEAD governance, historical-byte and synthetic arithmetic check.
No market loader, simulation or statistical workflow dispatch.
"""
import hashlib,json,math,pathlib,subprocess,sys
R=pathlib.Path(__file__).resolve().parents[2];START='da3180ee67b2c93c6b9d57785e9bb85e19e89088';S='research_core_v4/state/';I='research_core_v4/inference_v2/'
def git(*a):return subprocess.check_output(['git','-C',str(R),*a])
def read(p):return json.loads((R/p).read_bytes())
def sha(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
head=git('rev-parse','HEAD').decode().strip()
if len(sys.argv)>1:assert head==sys.argv[1]
assert not git('diff','--name-only'), 'tracked bytes differ from exact HEAD'
old=json.loads(git('show',START+':'+S+'V4_STATE.json'));state=read(S+'V4_STATE.json')
allowed={'status','next_action','stop_boundary','next_information_source_selection_status','current_next_action_type','discovery_authority_hardening_ref','discovery_authority_hardening_sha256','discovery_protocol_correction_gate','discovery_protocol_correction_history','historical_next_information_source_selection_V5','next_information_source_selection','next_information_source_selection_sha256'}
assert {k:v for k,v in old.items() if k not in allowed}=={k:v for k,v in state.items() if k not in allowed}, 'historical state mutated'
for path in git('ls-tree','-r','--name-only',START).decode().splitlines():
 if path!=S+'V4_STATE.json':assert git('show',START+':'+path)==(R/path).read_bytes(), 'historical byte mutation: '+path
assert state['depth_information_requirement']==old['depth_information_requirement']
assert state['status']=='DISCOVERY_PROTOCOL_V2_FROZEN_NEXT_ACTION_PLAN_ONLY_STOP_NO_EXECUTION'
assert state['discovery_protocol_correction_history']==[old['discovery_protocol_correction_gate']]
depth=read(S+'BROKER_DEPTH_SIZE_INFORMATION_REQUIREMENT_V1.json');assert not depth['acquisition_authorized'] and not depth['real_response_authorized'] and not depth['machine_owned']['current_host_auth_ready']
protocol=read(S+'V4_DISCOVERY_PROTOCOL_V2.json');sup=read(S+'V4_DISCOVERY_PROTOCOL_V2_SUPERSESSION_AUTHORITY_V1.json');sel=read(S+'NEXT_INFORMATION_SOURCE_SELECTION_V6.json');gate=state['discovery_protocol_correction_gate']
for obj in [protocol,sup]:
 for p,h in obj['bindings'].items():assert sha(p)==h,(p,'binding')
assert sha(sup['protocol_ref'])==sup['protocol_sha256']==gate['protocol_sha256']==sel['protocol_sha256']
assert sha(gate['ref'])==gate['sha256']==sel['supersession_sha256']
assert sha(state['next_information_source_selection'])==state['next_information_source_selection_sha256']
assert sel['selected_next_action_type']==state['current_next_action_type']==gate['next_action_type']=='CORRECTED_EXISTING_DATA_DISCOVERY_ON_BROADER_ACCEPTED_EVIDENCE'
assert sel['allowed_action_types']==['CORRECTED_EXISTING_DATA_DISCOVERY_ON_BROADER_ACCEPTED_EVIDENCE','FROZEN_DEPTH_SIZE_CAPABILITY_PROBE']
assert not any(sel[k] for k in ['execution_authorized','acquisition_authorized','real_response_authorized','confirmation_opened','protected_forward_opened'])
assert sel['candidate_frozen_count']==0 and sel['Runtime_V2']=='READ_ONLY'
assert not gate['new_acquisition_authorized'] and not gate['new_real_response_authorized']
assert state['historical_next_information_source_selection_V5']==old['next_information_source_selection']
plan=read(I+'JBW_MAXT_CERTIFICATION_PLAN_V1.json');raw=read(I+'JBW_MAXT_RAW_SYNTHETIC_RESULT_V1.json');interpret=read(I+'JBW_MAXT_CERTIFICATION_INTERPRETATION_V1.json')
assert sha(I+'JBW_MAXT_CERTIFICATION_PLAN_V1.json')==raw['plan_sha256']==interpret['plan_sha256']=='a334f95e5d8c3e11317a1cad72e03d0953ab2c19e97d146d95592a5d2921be52'
assert sha(plan['implementation_ref'])==raw['implementation_sha256']==plan['implementation_sha256']=='e948a3e36e546168f185d52c8a31a5caf0da7fe0f0c160eb3da3a492c56979d0'
assert sha(I+'JBW_MAXT_RAW_SYNTHETIC_RESULT_V1.json')==interpret['raw_result_sha256']=='50da89d5f82a36f8ec2dd066081c2cdeb65755bf229bb43290895256014922b5'
assert raw['invariants']['pass'] and not raw['market_inputs_used'] and not raw['market_response_opened']
for obj in [raw,interpret]:
 for k in ['broker_contacts','historical_requests','orders']:assert obj[k]==0
assert raw['seeds']=={'seed_null':2026100512,'seed_power':2026100513,'seed_common_multiplier_bank':2026100514}
assert plan['invariant_seed']==2026100515
def verify_metric(m,z,n):
 assert m['trials']==n and m['rate']==m['rejections']/n
 p=m['rate'];den=1+z*z/n;center=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
 assert max(abs(m['wilson'][0]-(center-half)),abs(m['wilson'][1]-(center+half)))<1e-12
count=0;worst=0
for case in plan['null_cases']:
 assert set(raw['null'][case]['configurations'])==set(plan['null_configurations'])
 for cfg in plan['null_configurations']:
  x=raw['null'][case]['configurations'][cfg]
  for metric in ['any_false_significance','any_false_complete_lead']:
   verify_metric(x[metric],3.5,9216);assert x[metric]['wilson'][1]<=.05;worst=max(worst,x[metric]['wilson'][1])
  assert x['any_false_complete_lead']['rejections']<=x['any_false_significance']['rejections'];count+=1
assert count==44 and interpret['all44_strong_FWER_gates_pass']
curves=0
for case in plan['null_cases']:
 for alt,spec in plan['power_alternatives'].items():
  series=raw['power'][case][alt];assert set(series)==set(map(str,plan['power_effects_daily_score_SD']))
  for e in plan['power_effects_daily_score_SD']:
   x=series[str(e)]
   for metric in ['any_target_lead','all_target_leads','old_universal_complete']:verify_metric(x[metric],1.96,2048)
   assert set(x['per_target_leaf'])==set(spec)
   for m in x['per_target_leaf'].values():verify_metric(m,1.96,2048)
  good=[e for e in plan['power_effects_daily_score_SD'] if series[str(e)]['any_target_lead']['wilson'][0]>=.8]
  assert interpret['minimum_grid_effects_daily_score_SD'][case][alt]['any_target_grid_MDE']==(min(good) if good else None)
  curves+=1
assert curves==44 and interpret['power_characterization_complete']
assert raw['null']['contiguous_gaps']['all_leaf_support_trials']==0 and protocol['inference']['unknown_geometry_status']=='CALIBRATION_REQUIRED_NOT_AUTHORIZED'
for cp in [protocol['authority']['plan_frozen_head'],protocol['authority']['raw_result_head'],protocol['authority']['interpretation_head'],sel['protocol_freeze_head']]:git('merge-base','--is-ancestor',cp,head)
assert git('show',protocol['authority']['plan_frozen_head']+':'+plan['implementation_ref'])==(R/plan['implementation_ref']).read_bytes()
assert git('show',sel['protocol_freeze_head']+':'+S+'V4_DISCOVERY_PROTOCOL_V2.json')==(R/(S+'V4_DISCOVERY_PROTOCOL_V2.json')).read_bytes()
from research_core_v4.post_publication_integrity_v1 import check_state
check_state(state)
print(json.dumps({'status':'PASS_EXACT_HEAD_HISTORICAL_BYTES_BINDINGS_FROZEN_GATES_AND_NO_EXECUTION_AUTHORITY','head':head,'all44_error_gates':True,'power_curves':curves,'worst_simultaneous_upper':worst,'gap_support_limitation_retained':True,'independent_statistical_job_claimed':False,'market_or_broker_operations':0},sort_keys=True))
