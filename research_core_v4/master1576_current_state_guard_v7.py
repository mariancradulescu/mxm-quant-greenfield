"""Current compact-baseline mixed external/governance boundary."""
import json
from pathlib import Path
from research_core_v4 import compact_semantic_closure_v2 as c
STATES=[c.S+'V4_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json']
GUARD='research_core_v4/master1576_current_state_guard_v7.py'
BUDGET={'total':84,'used':21,'remaining':63,'refunds':0,'economic_outcomes_opened':29}
def validate_root(root):
 root=Path(root);a=json.loads((root/c.AUTH).read_bytes())
 for x in a['artifact_bindings']+a['immutable_bindings']:
  c.require(c.sha((root/x['ref']).read_bytes())==x['sha256'],'BINDING_DRIFT:'+x['ref'])
 for i,p in enumerate(STATES):
  d=json.loads((root/p).read_bytes());c.require(d['current_operational_status']==d['next_action']==c.NEXT,'STATE_ACTION_DRIFT')
  c.require(d['current_state_guard_ref']==GUARD,'GUARD_DRIFT');c.require(d['current_authority']==c.AUTH and d['current_authority_sha256']==c.sha((root/c.AUTH).read_bytes()),'AUTHORITY_DRIFT')
  q=d['strict_v2_compact_baseline_closure'];c.require(q['baseline_sha256']==c.BASE_HASH and q['certificate_count']==11,'NESTED_DRIFT')
  c.require(q['selected_source'] is None and q['search_budget_use']==0,'SELECTION_DRIFT')
  c.require(not q['protected_forward_opened'] and not q['confirmation_opened'],'CLOSED_BOUNDARY_DRIFT')
  c.require('strict_v2_shared_baseline_campaign' not in d,'STALE_CURRENT_STAGE')
  if i==0:
   c.require(d['status']==d['current_next_action_type']==d['stop_boundary']==c.NEXT,'V4_STATUS_DRIFT')
  elif i==1:c.require(d['status']=='ECONOMIC_RESULT_PRODUCED' and d['search_budget']==BUDGET,'HISTORY_DRIFT')
  else:c.require(d['status']=='EXECUTED_EXACT_V1_STOP_PENDING_INDEPENDENT_AUDIT' and d['current_operation']==c.NEXT and d['search_budget_after']==BUDGET,'HISTORY_DRIFT')
 return {'status':'PASS_COMPACT_BASELINE_BOUNDARY','authority_sha256':c.sha((root/c.AUTH).read_bytes())}
