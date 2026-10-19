"""Keyless native continuation of an admitted programme, never a blind retry."""
import os,json,re,urllib.request
from .common import *
from .runtime import anchors,read_state,validate_state,EVIDENCE_BRANCH
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly

def main():
    need(os.environ['GITHUB_JOB']=='scientific-handoff' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM') and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'HANDOFF_NO_KEYS')
    route=GetOnly();anchors(route);oid=os.environ['LAB_PARENT_OID'];need(route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha']==oid,'HANDOFF_STALE')
    s=read_state(route,oid);validate_state(s);need(s['safe_stop'] is False and s['last_run_id']==int(os.environ['GITHUB_RUN_ID']),'HANDOFF_NOT_ADMITTED')
    jobs=route.json('actions/runs/'+os.environ['GITHUB_RUN_ID']+'/jobs?per_page=100')['jobs'];need(all(any(j['name']==n and j['conclusion']=='success' for j in jobs) for n in ('investigation','durable-archive')),'HANDOFF_NATIVE_COMPLETION')
    body={'ref':'mxm-remediation-p0-p4-20261015-v1','inputs':{'parent_oid':oid,'admission_ref':s['admission_ref'],'admission_path':s['admission_path']}}
    req=urllib.request.Request('https://api.github.com/repos/mariancradulescu/mxm-quant-greenfield/actions/workflows/mxm-integrated-laboratory.yml/dispatches',data=encoded(body),method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:need(response.status==204,'HANDOFF_ACK_AMBIGUOUS')
    print(json.dumps({'state':'GENERAL_PROGRAMME_CONTINUATION_DISPATCHED','parent_oid':oid,'owner_intervention':False,'bootstrap':False}))
if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'state':'HANDOFF_SAFE_STOP_NO_RETRY','safe_code':str(e) if re.fullmatch(r'LAB_[A-Z0-9_]+',str(e)) else type(e).__name__}));raise SystemExit(1) from None
