"""Material stage-1 governance boundary; previous guards remain immutable history."""
import json
from pathlib import Path
from research_core_v4 import shared_baseline_campaign_v1 as b
STATES=[b.S+'V4_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json']
BUDGET={'total':84,'used':21,'remaining':63,'refunds':0,'economic_outcomes_opened':29}
GUARD='research_core_v4/master1576_current_state_guard_v6.py'
def read(root,path):return json.loads((Path(root)/path).read_bytes())
def sha(root,path):return b.digest((Path(root)/path).read_bytes())
def walk_current(d, path=()):
    if isinstance(d,dict):
        for k,v in d.items():
            if not k.startswith('historical_'):yield from walk_current(v,path+(k,))
    elif isinstance(d,list):
        for i,v in enumerate(d):yield from walk_current(v,path+(str(i),))
    else:yield path,d
def validate(states,h):
    b.require(len(states)==3,'STATE_COUNT');v,c,a=states
    b.require(all(x==b.NEXT for x in [v['current_next_action_type'],v['next_action'],v['stop_boundary'],c['next_action'],a['next_action'],a['current_operation']]),'ACTION_DRIFT')
    b.require(v['status']==b.NEXT,'TOP_STATUS_DRIFT')
    for i,d in enumerate(states):
        b.require(d['current_operational_status']==b.NEXT and d['current_state_guard_ref']==GUARD,'STATUS_OR_GUARD_DRIFT')
        b.require(d['canonical_status_semantics']['current_operational_status']=='CURRENT_SHARED_BASELINE_GOVERNANCE_BOUNDARY','SEMANTICS_DRIFT')
        if i:b.require(d['status']==['ECONOMIC_RESULT_PRODUCED','EXECUTED_EXACT_V1_STOP_PENDING_INDEPENDENT_AUDIT'][i-1] and d['canonical_status_semantics']['status']=='IMMUTABLE_ADAPTIVE_POLICY_V1_DIAGNOSTIC_RECORD','DIAGNOSTIC_DRIFT')
        else:b.require(d['canonical_status_semantics']['status']=='CURRENT_SHARED_BASELINE_GOVERNANCE_BOUNDARY','TOP_SEMANTICS_DRIFT')
        b.require('strict_v2_semantic_certification' not in d,'STALE_STAGE')
        q=d['strict_v2_shared_baseline_campaign'];b.require(q['status']==q['next_action']==b.NEXT,'NESTED_ACTION_DRIFT')
        b.require(q['selected_source'] is None and q['selected_mechanism'] is None and q['remaining_possible_contenders']==11,'SELECTION_DRIFT')
        b.require(q['boundary_kind']=='NONDEFENSIBLE_FREE_DESIGN_CHOICE_STAGE_1_STOP' and q['triad_v7_parked'],'BOUNDARY_KIND_DRIFT')
        b.require(q['search_budget_use']==0 and not any(q[k] for k in ['stage_2_executed','stage_3_executed','protected_forward_opened','confirmation_opened']),'BOUNDARY_DRIFT')
        for fields,value in walk_current(d):
            if fields[-1]=='current_authority':b.require(value==b.AUTH,'AUTHORITY_DRIFT')
            if fields[-1]=='current_authority_sha256':b.require(value==h,'AUTHORITY_HASH_DRIFT')
            if isinstance(value,str):
                u=value.upper();b.require(not(('PENDING' in u or 'READY_FOR_SEPARATE' in u) and 'SHALLOW' in u and ('PREARM' in u or 'ARM' in u)),'STALE_ARM')
        for k in ['search_budget','search_budget_after']:
            if k in d:b.require(d[k]==BUDGET,'BUDGET_DRIFT')
        for k in ['protected_forward_opened','confirmation_opened']:
            if k in d:b.require(d[k] is False,'CLOSED_BOUNDARY_DRIFT')
    return {'status':'PASS_SHARED_BASELINE_GOVERNANCE_BOUNDARY','current_authority':b.AUTH,'current_authority_sha256':h,'next_action':b.NEXT}
def validate_root(root):
    a=read(root,b.AUTH)
    for x in a['artifact_bindings']+a['immutable_bindings']:b.require(sha(root,x['ref'])==x['sha256'],'BINDING_DRIFT:'+x['ref'])
    b.require(a['baseline_builder_read_allowlist']==sorted(b.ALLOWED),'ALLOWLIST_DRIFT')
    b.require(a['search_budget']==BUDGET and not any(a['boundary'].values()),'BOUNDARY_DRIFT')
    b.require((Path(root)/b.PROTOCOL).read_bytes()==b.canonical(b.protocol()),'PROTOCOL_DRIFT')
    seen=[];result=b.build_root(root,seen)
    b.require(seen==[b.CERT,b.INPUT],'READ_DRIFT')
    b.require((Path(root)/b.SPEC).read_bytes()==b.canonical(result),'DERIVATION_DRIFT')
    b.require(a['stages']['stage_1']['protocol_sha256']==sha(root,b.PROTOCOL) and a['stages']['stage_1']['output_sha256']==sha(root,b.SPEC),'STAGE_BINDING_DRIFT')
    b.require(a['stages']['stage_1']['protocol_frozen_before_output'] and a['stages']['stage_1']['execution_trace']==['PROTOCOL_FROZEN','TWO_INPUT_COMPARTMENT_OPENED','NONUNIQUENESS_PROVED','OUTPUT_FROZEN'],'FREEZE_ORDER_DRIFT')
    return validate([read(root,p) for p in STATES],sha(root,b.AUTH))
