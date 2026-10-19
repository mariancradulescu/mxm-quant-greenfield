"""Keyless dispatcher. A completed archived scientific verdict selects a task."""
import json,os,re,urllib.request
from .core import need
from .runtime import registry,read_state,check_state,EVIDENCE_BRANCH,anchors,WF
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
REPO='mariancradulescu/mxm-quant-greenfield'

def main():
    need(os.environ['GITHUB_JOB']=='scientific-handoff' and os.environ['GITHUB_RUN_ATTEMPT']=='1'
      and not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM') and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'DISPATCH_NO_KEYS')
    route=GetOnly();anchors(route);oid=os.environ['V6_EVIDENCE_OID'];task=os.environ['V6_NEXT_TASK'];r=registry()
    need(route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha']==oid,'HANDOFF_STALE')
    state=read_state(route,oid);check_state(state,r)
    need(task==state['next_task'] and task in r['tasks'] and state['safe_stop'] is False,'HANDOFF_NOT_ELIGIBLE')
    jobs=route.json('actions/runs/'+os.environ['GITHUB_RUN_ID']+'/jobs?per_page=100')['jobs']
    need(all(any(j['name']==name and j['conclusion']=='success' for j in jobs) for name in ('investigation','durable-archive')),'HANDOFF_NATIVE_SUCCESS')
    body={'ref':'mxm-remediation-p0-p4-20261015-v1','inputs':{'task':task,'parent_oid':oid}}
    req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/actions/workflows/mxm-scientific-program-v6.yml/dispatches',
      data=json.dumps(body).encode(),method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
    # A lost/unknown acknowledgement never causes a second POST.
    with urllib.request.urlopen(req,timeout=30) as response:need(response.status==204,'HANDOFF_ACK_AMBIGUOUS')
    print(json.dumps({'state':'REGISTERED_NEXT_SCIENCE_DISPATCHED','task':task,'parent_evidence_oid':oid,'bootstrap':False,'orders':0}))
if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'state':'HANDOFF_SAFE_STOP_NO_RETRY','safe_code':str(e) if re.fullmatch(r'V6_[A-Z0-9_]+',str(e)) else type(e).__name__}));raise SystemExit(1) from None
