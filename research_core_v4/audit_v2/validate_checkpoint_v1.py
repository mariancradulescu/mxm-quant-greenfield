"""Read-only exact-head governance evidence validation. No simulation or market execution."""
import json,pathlib,hashlib,subprocess,sys
R=pathlib.Path(__file__).resolve().parents[2]
def git(*a):return subprocess.check_output(['git','-C',str(R),*a])
def read(p):return json.loads((R/p).read_bytes())
def digest(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
head=git('rev-parse','HEAD').decode().strip()
if len(sys.argv)>1:assert head==sys.argv[1],(head,sys.argv[1])
p='research_core_v4/state/DISCOVERY_PROTOCOL_CORRECTION_BLOCKED_GOVERNANCE_V1.json';a=read(p);start=a['starting_head']
for f,expected in a['evidence_sha256'].items():assert digest(f)==expected,(f,'evidence hash')
for f,expected in a['preserved_historical_sha256'].items():
 assert digest(f)==expected,(f,'current historical hash')
 assert hashlib.sha256(git('show',start+':'+f)).hexdigest()==expected,(f,'original historical hash')
state=read('research_core_v4/state/V4_STATE.json');before=json.loads(git('show',start+':research_core_v4/state/V4_STATE.json'));gate=state.pop('discovery_protocol_correction_gate');assert state==before,'Any unexpected historical V4 state mutation'
assert gate['sha256']==digest(p) and gate['next_action_type'] is None and not gate['supersession_authorized']
result=read('research_core_v4/audit_v2/SYNTHETIC_COMPARISON_RESULT_V1.json');plan='research_core_v4/audit_v2/SYNTHETIC_COMPARISON_PLAN_V1.json';assert result['plan_sha256']==digest(plan);assert result['implementation_sha256']==digest('research_core_v4/audit_v2/synthetic_comparison_v1.py')
assert result['selected_inference_candidate'] is None and not result['error_control_certified_for_declared_synthetic_envelope_only']
assert not any(x['error_gate_pass'] for x in result['candidate_assessment'].values())
assert a['corrected_protocol_ref'] is None and not a['supersession_authorized'] and a['next_action_type'] is None
assert all(a[k]==0 for k in ['broker_contacts_this_task','historical_requests_this_task','market_response_openings_this_task','orders_this_task','candidate_frozen_count'])
assert all(a[k] is False for k in ['protected_forward_opened','confirmation_opened','acquisition_authorized','real_response_authorized','live_trading_started','current_host_auth_ready'])
changed=git('diff','--name-only',start,head).decode().splitlines()
assert all(x.startswith('research_core_v4/audit_v2/') or x in [p,'research_core_v4/state/V4_STATE.json'] for x in changed),changed
print(json.dumps({'status':'PASS_EXACT_HEAD_BLOCKED_GOVERNANCE_AND_EVIDENCE_INTEGRITY','head':head,'starting_head':start,'changed_files':changed,'preserved_historical_files':len(a['preserved_historical_sha256']),'audit_binding_files':len(a['evidence_sha256']),'supported_protocol_freeze':False,'next_action_selected':False,'scientific_response_calls':0,'broker_contacts':0},sort_keys=True))
