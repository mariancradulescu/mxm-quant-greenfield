"""Versioned successor: categorical project-wide reselection, no market route."""
import hashlib
import json
from pathlib import Path
from research_core_v4.master1576_current_state_guard_v1 import walk_current, require, STATES, DIAGNOSTIC_TOP_STATUS
S='research_core_v4/state/'
BASE='d64a77e7a09ba13ec6f23de1970e62a90676ac81'
AUTH=S+'PROJECT_WIDE_INFORMATION_SOURCE_RESELECTION_AUTHORITY_V1.json'
MATRIX=S+'PROJECT_WIDE_INFORMATION_SOURCE_RESELECTION_MATRIX_V1.json'
NEXT='PROJECT_WIDE_INFORMATION_SOURCE_RESELECTION_UNRESOLVED_PENDING_INDEPENDENT_GOVERNANCE'
BUDGET={'total':84,'used':21,'remaining':63,'refunds':0,'economic_outcomes_opened':29}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(root,path):return json.loads((Path(root)/path).read_bytes())
def validate(states,auth_hash):
    require(len(states)==3,'STATE_COUNT_DRIFT')
    a,b,c=states
    require(all(x==NEXT for x in [a['current_next_action_type'],a['next_action'],a['stop_boundary'],b['next_action'],c['next_action'],c['current_operation']]),'CURRENT_ACTION_DRIFT')
    require(a['status']==NEXT,'V4_TOP_STATUS_DRIFT')
    for path,d in zip(STATES,states):
        require(d['current_operational_status']==NEXT,'CURRENT_STATUS_DRIFT')
        require(d['current_state_guard_ref']=='research_core_v4/master1576_current_state_guard_v2.py','GUARD_POINTER_DRIFT')
        require(d['canonical_status_semantics']['current_operational_status']=='CURRENT_PROJECT_WIDE_RESELECTION_OPERATION','STATUS_SEMANTICS_DRIFT')
        if path in DIAGNOSTIC_TOP_STATUS:require(d['status']==DIAGNOSTIC_TOP_STATUS[path] and d['canonical_status_semantics']['status']=='IMMUTABLE_ADAPTIVE_POLICY_V1_DIAGNOSTIC_RECORD','DIAGNOSTIC_STATUS_DRIFT')
        require('post_screen_breadth_to_depth' not in d and 'next_prospective_wave' not in d,'STALE_CURRENT_STAGE_POINTER')
        current=d['project_wide_information_source_reselection']
        require(current['status']==current['next_action']==NEXT,'RESELECTION_POINTER_DRIFT')
        require(current['selected_source'] is None and current['selected_mechanism'] is None,'UNAUTHORIZED_SELECTION')
        require(current['triad_v7_parked'] and current['search_budget_use']==0 and not any(current[k] for k in ['duration_selected','protected_forward_opened','confirmation_opened']),'BOUNDARY_DRIFT')
        for fields,value in walk_current(d):
            if fields[-1]=='current_authority':require(value==AUTH,'CURRENT_AUTHORITY_DRIFT')
            if fields[-1]=='current_authority_sha256':require(value==auth_hash,'CURRENT_AUTHORITY_HASH_DRIFT')
            if isinstance(value,str):
                upper=value.upper()
                require(not(('PENDING' in upper or 'READY_FOR_SEPARATE' in upper) and 'SHALLOW' in upper and ('PREARM' in upper or 'ARM' in upper)),'STALE_SHALLOW_ARM_STATE')
                if fields[-1] in {'current_action_type','current_V6_remains_frozen_action_type_plan'}:require(False,'STALE_V6_CURRENT_POINTER')
        if 'search_budget' in d:require(d['search_budget']==BUDGET,'BUDGET_DRIFT')
        if 'search_budget_after' in d:require(d['search_budget_after']==BUDGET,'BUDGET_DRIFT')
        for k in ['protected_forward_opened','confirmation_opened']:
            if k in d:require(d[k] is False,'CLOSED_BOUNDARY_DRIFT')
    return {'status':'PASS_PROJECT_WIDE_RESELECTION_CURRENT_STATE','next_action':NEXT,'authority_sha256':auth_hash}
def validate_root(root):
    root=Path(root);a=read(root,AUTH);m=read(root,MATRIX)
    require(a['status']==a['next_action']==a['stop_boundary']==NEXT,'AUTHORITY_STATUS_DRIFT')
    require(a['selected_source'] is None and a['selected_mechanism'] is None and not a['complete_information_design_created'],'SELECTION_DRIFT')
    require(a['matrix']=={'ref':MATRIX,'sha256':sha(root/MATRIX)},'MATRIX_BINDING_DRIFT')
    for b in a['immutable_bindings']:require(sha(root/b['ref'])==b['sha256'],'IMMUTABLE_BINDING_DRIFT:'+b['ref'])
    require(a['search_budget']==BUDGET and a['triad_v7_parked'] and not a['triad_v8_created'],'BUDGET_OR_TRIAD_DRIFT')
    require(not any(a['boundary'].values()),'EXECUTION_BOUNDARY_DRIFT')
    catalog=read(root,S+'INFORMATION_SOURCE_CATALOG_V1.json')
    require([x['information_source'] for x in m['sources']]==[x['id'] for x in catalog['sources']],'CATALOG_COVERAGE_DRIFT')
    require(len(m['sources'])==12 and not m['forbidden_selection_inputs_used'] and not m['catalog_priority_used_as_selection'],'SELECTION_INPUT_DRIFT')
    for x in m['sources']:
        require(len(x['comparison_dimensions'])==11 and x['blocking_design_uncertainty'],'INCOMPLETE_COMPARISON')
        require(not x['broader_family_global_null'] and x['decision']=='NOT_SELECTED_NOT_GLOBAL_NULL','GLOBAL_NULL_DRIFT')
        for b in x['latest_relevant_authorities']:require(sha(root/b['ref'])==b['sha256'],'LATEST_AUTHORITY_DRIFT')
    return validate([read(root,p) for p in STATES],sha(root/AUTH))
if __name__=='__main__':print(json.dumps(validate_root(Path(__file__).resolve().parents[1]),sort_keys=True))
