"""Current pre-support wave guard. No empirical support certification."""
import json
from pathlib import Path
from research_core_v4 import current_testability_frontier_v1 as c
STATES=[c.S+'V4_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json']
GUARD='research_core_v4/master1576_current_state_guard_v9.py'
def validate_root(root):
 root=Path(root);raw=(root/c.AUTH).read_bytes();a=json.loads(raw)
 for x in a['artifact_bindings']+a['immutable_bindings']:
  c.require(c.sha((root/x['ref']).read_bytes())==x['sha256'],'BINDING_DRIFT:'+x['ref'])
 for i,p in enumerate(STATES):
  d=json.loads((root/p).read_bytes());c.require(d['current_operational_status']==d['next_action']==c.NEXT,'ACTION_DRIFT');c.require(d['current_state_guard_ref']==GUARD,'GUARD_DRIFT')
  c.require(d['current_authority']==c.AUTH and d['current_authority_sha256']==c.sha(raw),'AUTHORITY_DRIFT')
  q=d['strict_v2_current_testability_wave'];c.require(q['candidate_count']==5 and q['parked_count']==6 and q['global_source_count']==12,'LEDGER_DRIFT')
  c.require(q['selected_source'] is None and not q['support_execution'] and not q['protected_forward_opened'] and not q['confirmation_opened'],'BOUNDARY_DRIFT')
  c.require('strict_v2_exact_candidate_closure' not in d,'STALE_OPERATION')
  if i==0:c.require(d['status']==d['current_next_action_type']==d['stop_boundary']==c.NEXT,'V4_ACTION_DRIFT')
 return {'status':'PASS_CURRENT_TESTABILITY_PRE_SUPPORT','support_execution':False}
