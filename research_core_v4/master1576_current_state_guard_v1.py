"""Fail-closed current-state guard; historical namespaces retain their records."""
import hashlib
import json
from pathlib import Path
import re
from research_core_v4 import master1576_post_screen_v1 as p
STATES=[p.S+'V4_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json']
STATUS='BREADTH_COMPLETE_ACCEPTED_INFORMATION_DESIGN_AND_DURATION_UNRESOLVED'
AUTH_HASH='63b0952501d894cf74924091ebaecd5c9a1eca1444e4baf02f14fd3de1463a4a'
REPAIR=p.S+'MASTER1576_V2_POST_SCREEN_CANONICAL_CURRENT_STATE_REPAIR_AUTHORITY_V1.json'
STOP='MASTER1576_V2_POST_SCREEN_CANONICAL_CURRENT_STATE_REPAIRED_PENDING_INDEPENDENT_AUDIT_BEFORE_PROJECT_WIDE_INFORMATION_SOURCE_RESELECTION_OR_ANY_FURTHER_BREADTH_TO_DEPTH_REMEDIATION'
DIAGNOSTIC_TOP_STATUS={STATES[1]:'ECONOMIC_RESULT_PRODUCED',STATES[2]:'EXECUTED_EXACT_V1_STOP_PENDING_INDEPENDENT_AUDIT'}
def require(ok,code):
    if not ok:raise ValueError(code)
def walk_current(value,path=()):
    if isinstance(value,dict):
        for key,x in value.items():
            if key.startswith('historical_'):continue
            yield from walk_current(x,path+(key,))
    elif isinstance(value,list):
        for i,x in enumerate(value):yield from walk_current(x,path+(str(i),))
    else:yield path,value

def validate(states):
    require(len(states)==3,'STATE_COUNT_DRIFT')
    a,b,c=states
    current=[a['current_next_action_type'],a['next_action'],a['stop_boundary'],b['next_action'],c['next_action'],c['current_operation']]
    require(all(x==p.NEXT for x in current),'CURRENT_ACTION_DRIFT')
    require(a['status']==STATUS,'V4_TOP_STATUS_DRIFT')
    for path,d in zip(STATES,states):
        require(d['current_operational_status']==d['post_screen_breadth_to_depth']['status']==STATUS,'CURRENT_STATUS_DRIFT')
        if path in DIAGNOSTIC_TOP_STATUS:
            require(d['status']==DIAGNOSTIC_TOP_STATUS[path] and d['canonical_status_semantics']['status']=='IMMUTABLE_ADAPTIVE_POLICY_V1_DIAGNOSTIC_RECORD' and d['canonical_status_semantics']['current_operational_status']=='CURRENT_POST_SCREEN_OPERATION','DIAGNOSTIC_STATUS_SEMANTICS_DRIFT')
        for fields,value in walk_current(d):
            if fields[-1]=='current_authority':require(value==p.ACCEPT,'CURRENT_AUTHORITY_DRIFT')
            if fields[-1]=='current_authority_sha256':require(value==AUTH_HASH,'CURRENT_AUTHORITY_HASH_DRIFT')
            if fields[-1] in {'next_action','current_next_action_type','current_operation','stop_boundary'} and (len(fields)==1 or fields[0] in {'post_screen_breadth_to_depth','shallow_m5_v2_current_operation','shallow_m5_v2_operational_rebind'}):
                require(value==p.NEXT,'NESTED_CURRENT_ACTION_DRIFT')
            if isinstance(value,str):
                upper=value.upper()
                pending='PENDING' in upper or 'READY_FOR_SEPARATE' in upper
                stale=pending and (('SHALLOW' in upper and ('PREARM' in upper or 'ARM' in upper)) or re.search(r'PENDING.*(?:SEPARATE_)?REAL_.*ARM',upper))
                require(not stale,'SUPERSEDED_SHALLOW_ARM_STATE:'+'.'.join(fields))
        require(d['post_screen_breadth_to_depth']['bindings']['acceptance']=={'ref':p.ACCEPT,'sha256':AUTH_HASH},'ACCEPTANCE_BINDING_DRIFT')
        for key in ['shallow_m5_v2_current_operation','shallow_m5_v2_operational_rebind']:
            if key in d:require(d[key]['status']=='BREADTH_CAPTURE_AND_STRUCTURAL_SCREEN_COMPLETE_ACCEPTED_DURATION_UNRESOLVED','CURRENT_CAPTURE_STATUS_DRIFT')
    return {'status':'PASS_CANONICAL_CURRENT_STATE_ALIGNED','current_operational_status':STATUS,'current_next_action':p.NEXT,'current_authority':p.ACCEPT,'current_authority_sha256':AUTH_HASH}
def validate_root(root):
    root=Path(root);states=[json.loads((root/f).read_bytes()) for f in STATES]
    require(hashlib.sha256((root/p.ACCEPT).read_bytes()).hexdigest()==AUTH_HASH,'ACCEPTANCE_BYTES_DRIFT')
    repair=json.loads((root/REPAIR).read_bytes());digest=hashlib.sha256((root/REPAIR).read_bytes()).hexdigest()
    for d in states:require(d['canonical_current_state_repair_ref']==REPAIR and d['canonical_current_state_repair_sha256']==digest,'REPAIR_BINDING_DRIFT')
    for b in list(repair['preserved_bindings'].values())+list(repair['validation_bindings'].values()):require(hashlib.sha256((root/b['ref']).read_bytes()).hexdigest()==b['sha256'],'IMMUTABLE_ARTIFACT_DRIFT')
    return validate(states)
if __name__=='__main__':print(json.dumps(validate_root(Path(__file__).resolve().parents[1]),sort_keys=True))
