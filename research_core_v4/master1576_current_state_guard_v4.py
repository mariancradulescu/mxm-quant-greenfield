"""Versioned operational guard; historical preservation outside selection compartment."""
import hashlib
import json
from pathlib import Path
from research_core_v4 import strict_selection_functional_v1 as f
from research_core_v4.master1576_current_state_guard_v3 import walk_current, STATES, BUDGET
BASE='e93fa59675baf834c9e7275c8f88b27bde789ae3'
AUTH=f.S+'STRICT_PREOUTCOME_V2_SELECTION_FUNCTIONAL_AUTHORITY_V1.json'
def read(root,p):return json.loads((Path(root)/p).read_bytes())
def sha(root,p):return hashlib.sha256((Path(root)/p).read_bytes()).hexdigest()
def validate(states,h):
    f.require(len(states)==3,'STATE_COUNT');a,b,c=states
    f.require(all(v==f.NEXT for v in [a['current_next_action_type'],a['next_action'],a['stop_boundary'],b['next_action'],c['next_action'],c['current_operation']]),'ACTION_DRIFT')
    f.require(a['status']==f.NEXT,'TOP_STATUS_DRIFT')
    for i,d in enumerate(states):
        f.require(d['current_operational_status']==f.NEXT,'STATUS_DRIFT')
        f.require(d['current_state_guard_ref']=='research_core_v4/master1576_current_state_guard_v4.py','GUARD_DRIFT')
        f.require(d['canonical_status_semantics']['current_operational_status']=='CURRENT_STRICT_V2_FUNCTIONAL_DISCRIMINATOR_OPERATION','SEMANTICS_DRIFT')
        if i:f.require(d['status']==['ECONOMIC_RESULT_PRODUCED','EXECUTED_EXACT_V1_STOP_PENDING_INDEPENDENT_AUDIT'][i-1] and d['canonical_status_semantics']['status']=='IMMUTABLE_ADAPTIVE_POLICY_V1_DIAGNOSTIC_RECORD','DIAGNOSTIC_HISTORY_DRIFT')
        for k in ['strict_preoutcome_reselection_v2','project_wide_information_source_reselection','post_screen_breadth_to_depth','next_information_source_selection','next_prospective_wave']:f.require(k not in d,'STALE_CURRENT_STAGE')
        q=d['strict_v2_selection_functional'];f.require(q['status']==q['next_action']==f.NEXT,'NESTED_ACTION_DRIFT')
        f.require(q['selected_source'] is None and q['selected_mechanism'] is None,'SELECTION_DRIFT')
        f.require(q['triad_v7_parked'] and q['search_budget_use']==0 and not any(q[k] for k in ['discriminator_executed','protected_forward_opened','confirmation_opened']),'BOUNDARY_DRIFT')
        for fields,v in walk_current(d):
            if fields[-1]=='current_authority':f.require(v==AUTH,'AUTHORITY_DRIFT')
            if fields[-1]=='current_authority_sha256':f.require(v==h,'AUTHORITY_HASH_DRIFT')
            if isinstance(v,str):
                u=v.upper();f.require(not(('PENDING' in u or 'READY_FOR_SEPARATE' in u) and 'SHALLOW' in u and ('PREARM' in u or 'ARM' in u)),'STALE_ARM')
        for k in ['search_budget','search_budget_after']:
            if k in d:f.require(d[k]==BUDGET,'BUDGET_DRIFT')
        for k in ['protected_forward_opened','confirmation_opened']:
            if k in d:f.require(d[k] is False,'CLOSED_BOUNDARY_DRIFT')
    return {'status':'PASS_FUNCTIONAL_DISCRIMINATOR_CURRENT_STATE','next_action':f.NEXT,'current_authority':AUTH,'current_authority_sha256':h}
def validate_root(root):
    a=read(root,AUTH)
    for p in a['bindings']+a['immutable_bindings']:f.require(sha(root,p['ref'])==p['sha256'],'BINDING_DRIFT:'+p['ref'])
    f.require(a['selection_logic_read_allowlist']==sorted(f.ALLOWLIST),'ALLOWLIST_DRIFT')
    f.require(a['search_budget']==BUDGET and not any(a['boundary'].values()),'BOUNDARY_DRIFT')
    seen=[];outputs=f.build_root(root,seen);f.require(set(seen)==f.ALLOWLIST and len(seen)==3,'SELECTION_READ_DRIFT')
    for p,d in outputs.items():f.require((Path(root)/p).read_bytes()==f.canonical(d),'DERIVATION_DRIFT:'+p)
    return validate([read(root,p) for p in STATES],sha(root,AUTH))
