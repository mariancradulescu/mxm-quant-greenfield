"""Sealed observer for the unchanged integrated engine; no economic bootstrap."""
import json,os
from .common import need,bytes_digest
from .protocol import require_jobs,can_recover_before_exposure,ORIGINAL_PUBLIC

ENGINE='eab050084982916ad0c67798b38b947bac66b2b2'
ENGINE_MODULE='c85a62a4f13f6787f11de7a2f35ad4d812569beaee8fbb7e34c8e5efe6e76f05'
BRANCH='mxm-o04-successor-code-p0-recovery-observer-v3'
PATH='.github/workflows/mxm-integrated-p0-recovery.yml'

def workflow(source):
    return '''name: MXM integrated P0 ordinary recovery
on:
  push:
    branches: [main]
    paths: [.github/workflows/mxm-integrated-p0-recovery.yml]
  schedule:
    - cron: '11,26,41,56 * * * *'
  workflow_run:
    workflows: [MXM integrated P0 technical recovery]
    types: [completed]
  workflow_dispatch:
permissions: {}
concurrency:
  group: mxm-integrated-laboratory
  cancel-in-progress: false
  queue: max
jobs:
  ordinary-recovery:
    if: github.repository == 'mariancradulescu/mxm-quant-greenfield' && github.run_attempt == 1
    runs-on: ubuntu-24.04
    timeout-minutes: 6
    permissions: {contents: write, actions: write}
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with: {ref: '''+source+''', persist-credentials: false}
      - run: |
          python3 -m pip install --only-binary=:all: --require-hashes -r research_core_v4/remediation_p0_p4_20261015/requirements.lock
      - name: Verify sealed recovery guard and exact predecessor job outcomes
        run: python3 -m unittest research_core_v4.laboratory.test_recovery_v2 -v
      - name: Recover only a terminal native issuer with exact durable evidence
        run: python3 -m research_core_v4.laboratory.recovery_v2
        env:
          GH_TOKEN: ${{ github.token }}
          LAB_SOURCE_SHA: '''+ENGINE+'''
          LAB_OBSERVER_SOURCE_SHA: '''+source+'''
          LAB_INTEGRATED_PROTOCOL: v2
'''

def predecessor(s,run,jobs):
    need(run['path']=='.github/workflows/mxm-integrated-p0.yml' and run['head_branch']=='mxm-remediation-p0-p4-20261015-v1' and run['run_attempt']==1,'OBSERVER_PREDECESSOR_IDENTITY')
    if run['status']!='completed':return 'WAIT_ACTIVE_NATIVE_RUN'
    if s['pending']:
        return 'RECOVER_PRE_EXPOSURE' if can_recover_before_exposure(s,jobs) else 'HOLD_AMBIGUOUS_EXPOSURE'
    require_jobs(jobs,['preflight','segment-intent','execution-fence','investigation'])
    publisher=[j for j in jobs if j['name']=='durable-archive'];need(len(publisher)==1 and publisher[0]['status']=='completed','OBSERVER_PUBLISHER_IDENTITY')
    if publisher[0]['conclusion']=='success':return 'CONTINUE_DURABLE_SUCCESSOR'
    if publisher[0]['conclusion']=='failure':return 'RECONCILE_EXACT_REMOTE_PUBLICATION'
    need(False,'OBSERVER_SKIPPED_PUBLISHER_NOT_AUTHORITY')

def main():
    from . import frontier_pregate as b
    from . import integrated as engine
    from .runtime import module_digest,file_at
    from .custody import restore_ciphertext
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json
    need(os.environ['GITHUB_REPOSITORY']=='mariancradulescu/mxm-quant-greenfield' and os.environ['GITHUB_REF_NAME']=='main' and os.environ['GITHUB_JOB']=='ordinary-recovery' and os.environ['GITHUB_RUN_ATTEMPT']=='1','SEALED_OBSERVER_WORKLOAD')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')),'SEALED_OBSERVER_KEYLESS')
    route=GetOnly();source=os.environ['LAB_OBSERVER_SOURCE_SHA'];b.SOURCE_BRANCH=BRANCH;os.environ['PREGATE_SOURCE_SHA']=source;b.anchors(route)
    need(os.environ['LAB_SOURCE_SHA']==ENGINE and module_digest()==ENGINE_MODULE and route.json('git/ref/heads/mxm-o04-successor-code-integrated-p0-r2')['object']['sha']==ENGINE,'SEALED_OBSERVER_ENGINE_BINDING')
    need(file_at(route,PATH,os.environ['GITHUB_SHA'])==workflow(source).encode(),'SEALED_OBSERVER_WORKFLOW_CHANGED')
    oid=engine.current(route);s,initial=engine.state_at(route,oid)
    if initial:print(json.dumps({'state':'NO_SUCCESSOR_NO_BOOTSTRAP'}));return
    if s['pending'] is None and s['safe_stop'] and s['sequence']>16 and not s.get('recovery_continuation'):print(json.dumps({'state':'ADMITTED_PROGRAMME_COMPLETE_NO_DISPATCH'}));return
    prior=s['pending']['run_id'] if s['pending'] else s.get('last_run_id')
    if s['pending'] is None and s.get('recovery_continuation'):
        prior=s['recovery_continuation']['run_id']
        proof=strict_json(file_at(route,'typed-successor/recoveries/'+str(prior)+'.json',oid));need(proof['no_economic_exposure'] is True,'SEALED_OBSERVER_RECOVERED_ADMISSION')
        run=route.json('actions/runs/'+str(prior));jobs=route.json('actions/runs/'+str(prior)+'/attempts/1/jobs?per_page=100')['jobs']
        need(predecessor({**s,'pending':{'run_id':prior,'phase':'PRE_EXPOSURE'}},run,jobs)=='RECOVER_PRE_EXPOSURE','SEALED_OBSERVER_FAILED_ISSUER')
        action='RECOVERED_PRE_EXPOSURE_CONTINUATION'
    elif s['pending'] is None and s['sequence']==16:
        # A recovered original has a specific durable proof, not C033 as issuer.
        proof=strict_json(file_at(route,'typed-successor/recoveries/39318418345.json',oid));need(proof['no_economic_exposure'] is True,'SEALED_OBSERVER_RECOVERY_PROOF');prior=39318418345
        action='RECOVERED_PRE_EXPOSURE_CONTINUATION'
    else:
        run=route.json('actions/runs/'+str(prior));need(run['id']==prior,'SEALED_OBSERVER_PRIOR_RUN')
        jobs=route.json('actions/runs/'+str(prior)+'/attempts/1/jobs?per_page=100')['jobs'];action=predecessor(s,run,jobs)
        if action in ('WAIT_ACTIVE_NATIVE_RUN','HOLD_AMBIGUOUS_EXPOSURE'):print(json.dumps({'state':action,'dispatches':0}));return
        if action=='RECONCILE_EXACT_REMOTE_PUBLICATION':
            receipt=strict_json(file_at(route,'typed-successor/segments/'+str(s['sequence'])+'/receipt.json',oid))
            need(receipt['run_id']==prior and receipt['source_sha']==ENGINE and receipt['trigger_sha']==run['head_sha'] and receipt['ciphertext_sha256']==s['ciphertext_sha256'] and receipt['accounting_after']==s['accounting'],'SEALED_OBSERVER_RECEIPT_BINDING')
            blob=restore_ciphertext(strict_json(file_at(route,s['ciphertext_path'],oid)),lambda p:file_at(route,p,oid));need(bytes_digest(blob)==s['ciphertext_sha256'] and bytes_digest(file_at(route,'program-state.json',oid))==ORIGINAL_PUBLIC,'SEALED_OBSERVER_REMOTE_PUBLICATION')
    def guard(client):
        b.anchors(client);need(engine.current(client)==oid,'SEALED_OBSERVER_PARENT_MOVED')
    engine.anchors=guard
    print(json.dumps({'state':'SEALED_OBSERVER_PREDECESSOR_VERIFIED','action':action,'prior_run_id':prior,'evidence_oid':oid}))
    engine.observer()

if __name__=='__main__':main()
