"""Durable one-shot segment intent BEFORE OWNER-key worker or broker requests.

A failed/ambiguous worker leaves the intent pending. Normal continuation cannot
claim it again, even from a new push. Previous encrypted checkpoints are intact.
"""
import json,os,re
from .common import *

def claim_state(state,run_id,admission_sha,parent,source):
    need(state['pending'] is None,'PENDING_SEGMENT_REQUIRES_RECOVERY')
    need(not (state['safe_stop'] and state.get('admission_sha256')==admission_sha),'PROGRAMME_ALREADY_STOPPED')
    return {**state,'pending':{'run_id':run_id,'admission_sha256':admission_sha,'parent_checkpoint_oid':parent,'source_sha':source,
      'outcome_state':'NOT_KNOWN_UNTIL_AUTHENTIC_COMPLETION','automatic_retry':False}}

def main():
    from .runtime import ROOT,anchors,read_state,validate_state,admission,EVIDENCE_BRANCH,file_at
    from .custody import atomic_publish
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    need(os.environ['GITHUB_JOB']=='segment-intent' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM') and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'INTENT_NO_KEYS')
    route=GetOnly();anchors(route);parent=route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha'];s=read_state(route,parent);validate_state(s)
    ref=os.environ.get('LAB_ADMISSION_REF');path=os.environ.get('LAB_ADMISSION_PATH');expected=os.environ.get('LAB_PARENT_OID')
    if not ref:
        trigger=json.loads(file_at(route,'research_programs/admissions/EXECUTE_LABORATORY.json',os.environ['GITHUB_SHA']));ref=trigger['admission_ref'];path=trigger['admission_path'];expected=trigger['expected_evidence_parent']
        need(trigger['authority']==s['authority'],'TRIGGER_AUTHORITY')
    need(parent==expected and re.fullmatch(r'[a-f0-9]{40}',ref),'INTENT_STALE_PARENT')
    a=admission(route,ref,path);run=int(os.environ['GITHUB_RUN_ID']);new=claim_state(s,run,digest(a),parent,os.environ['LAB_SOURCE_SHA'])
    intent={'schema':'mxm.laboratory-durable-intent.v1','run_id':run,'admission_ref':ref,'admission_path':path,'admission_sha256':digest(a),'source_sha':os.environ['LAB_SOURCE_SHA'],
      'parent_checkpoint_oid':parent,'programme_definitions_prospective':True,'maximum_new_identity_reservation':sum(m['budget']['new_V2_identities'] for m in a['programmes']),
      'pending':new['pending'],'orders':0}
    oid=atomic_publish(route,parent,{'program-state.json':encoded(new),'intents/'+str(run)+'.json':encoded(intent)},'Reserve one-shot general laboratory segment before any OWNER-key worker or broker request')
    need(read_state(route,oid)==new,'INTENT_REMOTE_READBACK');anchors(route)
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('claim_oid='+oid+'\nadmission_ref='+ref+'\nadmission_path='+path+'\n')
    print(json.dumps({'state':'DURABLE_SEGMENT_INTENT_BEFORE_EXECUTION','evidence_oid':oid,'run_id':run,'automatic_retry':False,'active_authority_write':False}))
if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'state':'INTENT_SAFE_STOP_NO_EXECUTION','safe_code':str(e) if re.fullmatch(r'LAB_[A-Z0-9_]+',str(e)) else type(e).__name__}));raise SystemExit(1) from None
