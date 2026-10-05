"""Read-only authority validation against immutable starting state."""
import pathlib,json,subprocess,hashlib,sys
R=pathlib.Path(__file__).resolve().parents[2];START='da3180ee67b2c93c6b9d57785e9bb85e19e89088'
def git(*a):return subprocess.check_output(['git','-C',str(R),*a])
def read(p):return json.loads((R/p).read_bytes())
head=git('rev-parse','HEAD').decode().strip()
if len(sys.argv)>1:assert head==sys.argv[1]
old=json.loads(git('show',START+':research_core_v4/state/V4_STATE.json'));new=read('research_core_v4/state/V4_STATE.json');allowed={'status','next_action','stop_boundary','next_information_source_selection_status','current_next_action_type','discovery_authority_hardening_ref','discovery_authority_hardening_sha256'}
assert {k:v for k,v in new.items() if k not in allowed}=={k:v for k,v in old.items() if k not in allowed},'unexpected mutation'
assert new['status']=='DISCOVERY_PROTOCOL_INFERENCE_BLOCKED' and new['current_next_action_type'] is None
assert new['next_information_source_selection_status']=='HISTORICAL_V5_PENDING_VALIDATED_POST_PROTOCOL_RERANK_NOT_ACTION_AUTHORITY'
q=new['discovery_authority_hardening_ref'];assert hashlib.sha256((R/q).read_bytes()).hexdigest()==new['discovery_authority_hardening_sha256']
a=read('research_core_v4/state/DISCOVERY_PROTOCOL_CORRECTION_BLOCKED_GOVERNANCE_V1.json')
for p,h in a['evidence_sha256'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
for p,h in a['preserved_historical_sha256'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
assert new['depth_information_requirement']==old['depth_information_requirement'];d=read('research_core_v4/state/BROKER_DEPTH_SIZE_INFORMATION_REQUIREMENT_V1.json');assert not d['acquisition_authorized'] and not d['real_response_authorized'] and not d['machine_owned']['current_host_auth_ready']
from research_core_v4.post_publication_integrity_v1 import check_state
check_state(new)
print(json.dumps({'status':'PASS_TOP_LEVEL_INFERENCE_BLOCKED_NO_AUTHORITY_ESCALATION','head':head,'depth_plan_unchanged':True,'failed_candidates_unchanged':True,'broker_contacts':0,'real_market_responses':0},sort_keys=True))
