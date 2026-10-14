"""Finite progress-fenced autonomous campaigns. A failed job never dispatches."""
import os,json,datetime,urllib.error
from .runtime import gate,REPORT_TAG
from . import storage as io
from research_core_v4.critical_frontier_repair_20261014_v2.storage_v2 import ROOT_TAG
from research_core_v4.full_native_frontier_20261014_v1.runner_v1 import need,E
WF='mxm-native-coverage-continuation-20261014-v1.yml'
def main():
    head,a=gate();body=json.loads(io.api('releases/tags/'+ROOT_TAG)['body'])
    if body['remaining']==0 or body['state']=='FINAL_CLASSIFIED_WITH_EXPLICIT_LIMITS':print('BROAD_REQUIRED_DOMAIN_CLASSIFIED');return
    need(body['state']=='RUNNING_REPAIRED_NATIVE_WORK','EXPLICIT_STOP_NO_AUTO_RELAUNCH')
    current_run=io.api('actions/runs/'+os.environ['GITHUB_RUN_ID']);generation=int(body['generation'])
    need(body['run_id']==int(os.environ['GITHUB_RUN_ID']),'CONTINUATION_FROM_OWN_COMMITTED_PROGRESS_ONLY')
    need(body['new_requests']['BID_ASK']<450000 and body['new_requests']['M5']<12000,'FINITE_ORIGINAL_CAP_REACHED')
    need(datetime.datetime.now(datetime.timezone.utc).isoformat()<a['expires_utc'],'FINITE_AUTHORITY_EXPIRED')
    # Cursor or authenticated request progress is recorded in the predecessor journal.
    # A run with no new capture is not dispatched merely because a manifest advanced.
    pred=json.loads(io.api('releases/tags/'+REPORT_TAG)['body']).get('last_dispatched_requests',a['snapshot']['new_requests'])
    need(any(body['new_requests'][k]>pred[k] for k in ('BID_ASK','M5')),'NO_NATIVE_PROGRESS_NO_RELAUNCH')
    claim='mxm-final-native-continuation-from-'+str(generation)
    try:io.api('git/ref/tags/'+claim)
    except urllib.error.HTTPError as ex:
        if ex.code!=404:raise
    else:raise RuntimeError('GENERATION_ALREADY_DISPATCHED')
    io.api('git/refs','POST',{'ref':'refs/tags/'+claim,'sha':head})
    rel=io.api('releases/tags/'+REPORT_TAG);r=json.loads(rel['body']);r['last_dispatched_requests']=body['new_requests'];r['last_dispatched_generation']=generation
    io.api('releases/'+str(rel['id']),'PATCH',{'body':json.dumps(r,sort_keys=True)})
    # One dispatch POST. An uncertain response is a STOP, never an infinite retry.
    io.api('actions/workflows/'+WF+'/dispatches','POST',{'ref':E.w.old.BRANCH,'inputs':{'previous_generation':str(generation)}})
    print(json.dumps({'state':'NEXT_FINITE_NATIVE_CAMPAIGN_DISPATCH_ACCEPTED','from_generation':generation,'remaining':body['remaining'],'original_request_caps_preserved':True}),flush=True)
if __name__=='__main__':
    try:main()
    except Exception as ex:io.evidence(ex,'FINITE_CONTINUATION_STOP');raise SystemExit(1) from None
