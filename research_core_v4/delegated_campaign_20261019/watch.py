"""Keyless default-branch recovery dispatcher. It can NEVER bootstrap.

The encrypted checkpoint is in the protected Git authority, so ordinary
recovery does not depend on Actions artifact retention or a ChatGPT session.
An unresolved intent, revocation, changed source or completed queue stops it.
"""
import base64
import json
import os
import time
import urllib.error
from .control import *
from research_core_v4.p0_successor_a_20261017.issuer import http

PREFIX='/repos/mariancradulescu/mxm-quant-greenfield/'

def main():
    need(os.environ.get('GITHUB_REPOSITORY')=='mariancradulescu/mxm-quant-greenfield' and
         os.environ.get('GITHUB_REF_NAME')=='main' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
         os.environ.get('GITHUB_JOB')=='ordinary-recovery','BC_WATCH_WORKLOAD')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY',
        'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM')),'BC_WATCH_NO_SECRETS')
    source=os.environ['BC_EXPECTED_SOURCE_SHA'];need(oid(source),'BC_WATCH_SOURCE_PIN')
    token=os.environ['GH_TOKEN']
    _,ref=http(PREFIX+'git/ref/heads/'+SOURCE,token)
    need(ref['object']['sha']==source,'BC_WATCH_SOURCE_CHANGED')
    try:_,entry=http(PREFIX+'contents/state.json?ref=mxm-o04-active-v1',token)
    except urllib.error.HTTPError as error:
        if error.code==404:
            print(json.dumps({'state':'NOT_BOOTSTRAPPED_NO_ACTION','bootstrap_dispatches':0}));return
        raise
    need(entry['size']<=1048576 and entry['encoding']=='base64','BC_WATCH_STATE_SIZE')
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json
    state=strict_json(base64.b64decode(entry['content']));action=scheduling(state,source,int(time.time()))
    if action!='CONTINUE':
        print(json.dumps({'state':action,'bootstrap_dispatches':0}));return
    _,runs=http(PREFIX+'actions/runs?branch='+SOURCE+'&per_page=100',token)
    active=[r for r in runs['workflow_runs'] if r['path']==WORKFLOW and r['status'] in
            ('queued','in_progress','waiting','pending','requested')]
    if active:
        print(json.dumps({'state':'EXISTING_WORKFLOW_NO_DUPLICATE_DISPATCH','bootstrap_dispatches':0}));return
    status,_=http(PREFIX+'actions/workflows/mxm-delegated-campaign.yml/dispatches',token,'POST',
        {'ref':SOURCE,'inputs':{'command':'continue'}})
    need(status==204,'BC_WATCH_ACK_UNKNOWN_NO_RETRY')
    print(json.dumps({'state':'ORDINARY_CONTINUATION_DISPATCHED','bootstrap_dispatches':0}))

if __name__=='__main__':
    try:main()
    except Exception as error:
        import re
        code=str(error) if re.fullmatch(r'BC_[A-Z0-9_]+',str(error)) else type(error).__name__
        print(json.dumps({'state':'BC_WATCH_STOP','safe_code':code}));raise SystemExit(1) from None
