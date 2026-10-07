"""Current-state successor; preservation checks are outside the selector compartment."""
import hashlib
import json
from pathlib import Path
from research_core_v4 import strict_reselection_v2 as b
S=b.S
BASE='d11869bee56bc046c53be8fe71307b4d06ff7362'
AUTH=S+'STRICT_PREOUTCOME_RESELECTION_V2_FIREWALL_PROTOCOL_V1.json'
CORRECTION=S+'PROJECT_WIDE_RESELECTION_V1_SEMANTIC_CORRECTION_AUTHORITY_V1.json'
STATES=[S+'V4_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json']
BUDGET={'total':84,'used':21,'remaining':63,'refunds':0,'economic_outcomes_opened':29}
def read(root,p):return json.loads((Path(root)/p).read_bytes())
def sha(root,p):return hashlib.sha256((Path(root)/p).read_bytes()).hexdigest()
def walk_current(d,path=()):
    if isinstance(d,dict):
        for k,v in d.items():
            if not k.startswith('historical_'):yield from walk_current(v,path+(k,))
    elif isinstance(d,list):
        for i,v in enumerate(d):yield from walk_current(v,path+(str(i),))
    else:yield path,d
def validate(states,h):
    b.require(len(states)==3,'STATE_COUNT_DRIFT');a,c,d=states
    b.require(all(x==b.NEXT for x in [a['current_next_action_type'],a['next_action'],a['stop_boundary'],c['next_action'],d['next_action'],d['current_operation']]),'CURRENT_ACTION_DRIFT')
    b.require(a['status']==b.NEXT,'TOP_STATUS_DRIFT')
    for i,x in enumerate(states):
        b.require(x['current_operational_status']==b.NEXT,'STATUS_DRIFT')
        b.require(x['current_state_guard_ref']=='research_core_v4/master1576_current_state_guard_v3.py','GUARD_POINTER_DRIFT')
        b.require(x['canonical_status_semantics']['current_operational_status']=='CURRENT_STRICT_PREOUTCOME_RESELECTION_V2_OPERATION','STATUS_SEMANTICS_DRIFT')
        if i:b.require(x['status']==['ECONOMIC_RESULT_PRODUCED','EXECUTED_EXACT_V1_STOP_PENDING_INDEPENDENT_AUDIT'][i-1] and x['canonical_status_semantics']['status']=='IMMUTABLE_ADAPTIVE_POLICY_V1_DIAGNOSTIC_RECORD','DIAGNOSTIC_HISTORY_DRIFT')
        for k in ['project_wide_information_source_reselection','post_screen_breadth_to_depth','next_information_source_selection','next_prospective_wave']:b.require(k not in x,'STALE_CURRENT_STAGE')
        q=x['strict_preoutcome_reselection_v2'];b.require(q['status']==q['next_action']==b.NEXT,'NESTED_ACTION_DRIFT')
        b.require(q['selected_source'] is None and q['selected_mechanism'] is None and q['triad_v7_parked'],'SELECTION_OR_TRIAD_DRIFT')
        b.require(q['search_budget_use']==0 and not q['protected_forward_opened'] and not q['confirmation_opened'],'BOUNDARY_DRIFT')
        for path,v in walk_current(x):
            if path[-1]=='current_authority':b.require(v==AUTH,'CURRENT_AUTHORITY_DRIFT')
            if path[-1]=='current_authority_sha256':b.require(v==h,'CURRENT_AUTHORITY_HASH_DRIFT')
            if path[-1] in {'current_action_type','current_V6_remains_frozen_action_type_plan'}:b.require(False,'STALE_V6_CURRENT_POINTER')
            if isinstance(v,str):
                u=v.upper();b.require(not(('PENDING' in u or 'READY_FOR_SEPARATE' in u) and 'SHALLOW' in u and ('PREARM' in u or 'ARM' in u)),'STALE_SHALLOW_ARM')
        for k in ['search_budget','search_budget_after']:
            if k in x:b.require(x[k]==BUDGET,'BUDGET_DRIFT')
        for k in ['confirmation_opened','protected_forward_opened']:
            if k in x:b.require(x[k] is False,'CLOSED_BOUNDARY_DRIFT')
    return {'status':'PASS_STRICT_V2_CANONICAL_CURRENT_STATE','next_action':b.NEXT,'current_authority':AUTH,'current_authority_sha256':h}
def validate_root(root):
    p=read(root,AUTH);cor=read(root,CORRECTION)
    for item in p['immutable_bindings']+p['input_source_bindings']+[p['semantic_correction'],p['normalized_inputs'],p['result'],p['builder']]:b.require(sha(root,item['ref'])==item['sha256'],'BINDING_DRIFT:'+item['ref'])
    b.require(cor['status']=='HISTORICALLY_INFORMED_PROJECT_CONSTRAINT_AUDIT_SELECTION_UNRESOLVED_NOT_STRICT_OUTCOME_BLIND','V1_SEMANTIC_CORRECTION_DRIFT')
    b.require(cor['selected_source'] is None and cor['selected_mechanism'] is None and not cor['new_response_opened'] and cor['search_budget_use']==0,'V1_FACT_DRIFT')
    b.require(p['selection_logic_read_allowlist']==[b.INPUT] and set(p['input_projection_read_allowlist'])==b.READS,'ALLOWLIST_DRIFT')
    b.require(p['search_budget']==BUDGET and not any(p['boundary'].values()),'EXECUTION_BOUNDARY_DRIFT')
    reads=[];computed=b.build_root(root,reads)
    b.require(reads==[b.INPUT],'SELECTION_READ_DRIFT')
    b.require(b.canonical(computed)==(Path(root)/b.RESULT).read_bytes(),'RESULT_DRIFT')
    return validate([read(root,f) for f in STATES],sha(root,AUTH))
