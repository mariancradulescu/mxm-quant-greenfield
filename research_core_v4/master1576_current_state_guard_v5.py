"""Versioned current-state guard; immutable history is verified outside certification logic."""
import hashlib
import json
from pathlib import Path
from research_core_v4 import strict_semantic_certification_v1 as s
from research_core_v4.master1576_current_state_guard_v3 import walk_current,STATES,BUDGET
BASE='81e30b891ddf56ac35008ae758143627d062b812'
AUTH=s.S+'STRICT_PREOUTCOME_V2_SEMANTIC_CERTIFICATION_EXECUTION_AUTHORITY_V1.json'
def read(root,p):return json.loads((Path(root)/p).read_bytes())
def sha(root,p):return hashlib.sha256((Path(root)/p).read_bytes()).hexdigest()
def validate(states,h):
    s.require(len(states)==3,'STATE_COUNT');a,b,c=states
    s.require(all(x==s.NEXT for x in [a['current_next_action_type'],a['next_action'],a['stop_boundary'],b['next_action'],c['next_action'],c['current_operation']]),'ACTION_DRIFT')
    s.require(a['status']==s.NEXT,'TOP_STATUS_DRIFT')
    for i,d in enumerate(states):
        s.require(d['current_operational_status']==s.NEXT,'STATUS_DRIFT')
        s.require(d['current_state_guard_ref']=='research_core_v4/master1576_current_state_guard_v5.py','GUARD_DRIFT')
        s.require(d['canonical_status_semantics']['current_operational_status']=='CURRENT_STRICT_V2_SEMANTIC_CERTIFICATION_OPERATION','SEMANTICS_DRIFT')
        if i:s.require(d['status']==['ECONOMIC_RESULT_PRODUCED','EXECUTED_EXACT_V1_STOP_PENDING_INDEPENDENT_AUDIT'][i-1] and d['canonical_status_semantics']['status']=='IMMUTABLE_ADAPTIVE_POLICY_V1_DIAGNOSTIC_RECORD','DIAGNOSTIC_HISTORY_DRIFT')
        for k in ['strict_v2_selection_functional','strict_preoutcome_reselection_v2','project_wide_information_source_reselection','post_screen_breadth_to_depth','next_information_source_selection','next_prospective_wave']:s.require(k not in d,'STALE_CURRENT_STAGE')
        q=d['strict_v2_semantic_certification'];s.require(q['status']==q['next_action']==s.NEXT,'NESTED_ACTION_DRIFT')
        s.require(q['certificate_count']==11 and q['selected_source'] is None and q['selected_mechanism'] is None,'CERTIFICATE_OR_SELECTION_DRIFT')
        s.require(q['triad_v7_parked'] and q['search_budget_use']==0 and not any(q[k] for k in ['next_plan_executed','protected_forward_opened','confirmation_opened']),'BOUNDARY_DRIFT')
        for fields,v in walk_current(d):
            if fields[-1]=='current_authority':s.require(v==AUTH,'AUTHORITY_DRIFT')
            if fields[-1]=='current_authority_sha256':s.require(v==h,'AUTHORITY_HASH_DRIFT')
            if isinstance(v,str):
                u=v.upper();s.require(not(('PENDING' in u or 'READY_FOR_SEPARATE' in u) and 'SHALLOW' in u and ('PREARM' in u or 'ARM' in u)),'STALE_ARM')
        for k in ['search_budget','search_budget_after']:
            if k in d:s.require(d[k]==BUDGET,'BUDGET_DRIFT')
        for k in ['protected_forward_opened','confirmation_opened']:
            if k in d:s.require(d[k] is False,'CLOSED_BOUNDARY_DRIFT')
    return {'status':'PASS_SEMANTIC_CERTIFICATION_CURRENT_STATE','next_action':s.NEXT,'current_authority':AUTH,'current_authority_sha256':h}
def validate_root(root):
    a=read(root,AUTH)
    for x in a['artifact_bindings']+a['immutable_bindings']:s.require(sha(root,x['ref'])==x['sha256'],'BINDING_DRIFT:'+x['ref'])
    s.require(a['certificate_builder_read_allowlist']==sorted(s.ALLOWED) and a['functional_reapplication_read_allowlist']==sorted(s.REAPPLICATION_READS),'ALLOWLIST_DRIFT')
    s.require(a['search_budget']==BUDGET and not any(a['boundary'].values()),'BOUNDARY_DRIFT')
    seen=[];base,certs=s.derive_certificates(root,seen);s.require(set(seen)==s.ALLOWED and len(seen)==5,'BUILDER_READ_DRIFT')
    s.require((Path(root)/s.BASELINE).read_bytes()==s.canonical(base),'BASELINE_DERIVATION_DRIFT')
    for p,c in certs.items():s.require((Path(root)/p).read_bytes()==s.canonical(c),'CERTIFICATE_DERIVATION_DRIFT')
    reapplied=s.reapply_root(root);s.require((Path(root)/s.REAPPLIED).read_bytes()==s.canonical(reapplied),'REAPPLICATION_DRIFT')
    s.require((Path(root)/s.NEXT_PLAN).read_bytes()==s.canonical(s.next_plan(base,reapplied)),'NEXT_PLAN_DRIFT')
    return validate([read(root,p) for p in STATES],sha(root,AUTH))
