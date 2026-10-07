"""Current exact semantic closure guard; historical counters remain untouched."""
import json
from pathlib import Path
from research_core_v4 import exact_candidate_certification_v3 as c
STATES=[c.S+'V4_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json']
GUARD='research_core_v4/master1576_current_state_guard_v8.py'
def validate_root(root):
 root=Path(root);raw=(root/c.AUTH).read_bytes();a=json.loads(raw)
 for x in a['artifact_bindings']+a['immutable_bindings']:
  c.require(c.sha((root/x['ref']).read_bytes())==x['sha256'],'BINDING_DRIFT:'+x['ref'])
 for i,p in enumerate(STATES):
  d=json.loads((root/p).read_bytes());c.require(d['current_operational_status']==d['next_action']==c.NEXT,'STATE_ACTION_DRIFT')
  c.require(d['current_authority']==c.AUTH and d['current_authority_sha256']==c.sha(raw),'AUTHORITY_DRIFT')
  c.require(d['current_state_guard_ref']==GUARD,'GUARD_DRIFT')
  q=d['strict_v2_exact_candidate_closure'];c.require(q['baseline_sha256']==c.BASE_HASH and q['certificate_count']==11,'NESTED_DRIFT')
  c.require(q['selected_source'] is None and q['search_budget_use']==q['new_economic_outcomes']==0,'COUNTER_DRIFT')
  c.require(not q['protected_forward_opened'] and not q['confirmation_opened'],'FORWARD_DRIFT')
  c.require('strict_v2_compact_baseline_closure' not in d,'STALE_STAGE')
  if i==0:c.require(d['status']==d['current_next_action_type']==d['stop_boundary']==c.NEXT,'V4_STATE_DRIFT')
 return {'status':'PASS_EXACT_CANDIDATE_CLOSURE','authority_sha256':c.sha(raw)}
