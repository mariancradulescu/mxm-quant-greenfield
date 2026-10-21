"""Post-run native certificate issuer; NEVER executed from an in-flight job.

The source is an immutable protected R3 SHA. The triggered integrated run has
finished before this independent keyless job constructs its certificate.
Certification only succeeds if the operational verifier independently reads
every real proof and branch-control protection. No bypass of P0-14.
"""
import json,os
from .common import need,encoded
from .operational_acceptance import (verify_operational_acceptance,
                                      BRANCH,EXEC,CODE)
from .attest_v3 import proof_paths

from .certificate_registry import (certificate_path,validate_record,existing_record,
    verify_registered_certificate,CERTIFIER_BRANCH,EXECUTION_SOURCE,RECOVERY_RUN,
    RECOVERY_PROOF,LEGACY_CERT,SCHEMA)
WORKFLOW='.github/workflows/mxm-integrated-p0.yml'

def eligible_certificate(route,run_id,source):
    from .runtime import file_at
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json
    from .operational_acceptance import _artifact_state
    need(type(run_id) is int and run_id>0,'V3_CERTIFIER_RUN_ID')
    run=route.json('actions/runs/'+str(run_id))
    need(run['id']==run_id and run['status']=='completed' and
         run['conclusion']=='success' and run['path']==WORKFLOW and
         run['head_branch']==EXEC and run['run_attempt']==1,
         'V3_CERTIFIER_NATIVE_RUN_NOT_COMPLETED')
    oid=route.json('git/ref/heads/'+BRANCH)['object']['sha']
    state=_artifact_state(route,oid)
    need(state['last_run_id']==run_id and state['source_sha']==source
         and run.get('head_sha')==state.get('last_trigger_sha')
         and state['sequence']>=21 and state['safe_stop'] is True
         and state['pending'] is None,
         'V3_CERTIFIER_MISSING_LAST_NATIVE_CHECKPOINT')
    issuer_paths=proof_paths(run_id)
    gate={'schema':'mxm.e2e.native-acceptance.v3',
          'status':'END_TO_END_OPERATIONAL_ACCEPTED',
          'source_sha':source,'evidence_branch':BRANCH,'evidence_oid':oid,
          'sequence':state['sequence'],'run_id':run_id,
          'checkpoint_cipher_sha256':state['ciphertext_sha256'],
          'native_receipt_path':'typed-successor/segments/'+str(state['sequence'])+'/receipt.json',
          'issuer_path':issuer_paths['issuer'],
          'cold_proof_path':issuer_paths['cold'],
          'negative_proof_path':issuer_paths['negative'],
          'authentic_adapter_path':issuer_paths['adapter']}
    protected={name:route.json('branches/'+name)['protected']
               for name in ('main',EXEC)}
    verify_operational_acceptance(route,gate,source,protected)
    return gate

def main():
    from .runtime import anchors,file_at
    from .custody import atomic_publish
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    need(os.environ.get('GITHUB_REPOSITORY')=='mariancradulescu/mxm-quant-greenfield'
         and os.environ.get('GITHUB_REF_NAME')=='main'
         and os.environ.get('GITHUB_JOB')=='certify-v3'
         and os.environ.get('GITHUB_EVENT_NAME') in ('workflow_run','workflow_dispatch')
         and os.environ.get('GITHUB_RUN_ATTEMPT')=='1',
         'V3_CERTIFIER_WORKLOAD')
    need(not any(os.environ.get(k) for k in (
         'SUCCESSOR_APP_PRIVATE_KEY','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM',
         'CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')),
         'V3_CERTIFIER_KEYLESS')
    event=json.loads(open(os.environ['GITHUB_EVENT_PATH'],encoding='utf-8').read())
    route=GetOnly()
    from .custody import effective_controls_reader
    controls=effective_controls_reader(route)
    restrictions=[r for r in controls.json('rules/branches/'+CERTIFIER_BRANCH) if r.get('type')=='update']
    print('MXM_CERTIFIER_SOURCE_CONTROL '+json.dumps({'source_sha':os.environ['LAB_SOURCE_SHA'],
        'run_id':int(os.environ['GITHUB_RUN_ID']),
        'policies':[controls.json('rulesets/'+str(r['ruleset_id'])) for r in restrictions]},sort_keys=True),flush=True)
    # Validate source authority from checked-out protected R3 SHA (not a
    # mutable candidate PR ref). GitHub-native authentication is read-only.
    anchors(route,source_branch=CERTIFIER_BRANCH)
    if os.environ['GITHUB_EVENT_NAME']=='workflow_dispatch':
        run_id=RECOVERY_RUN
        observed=route.json('actions/runs/'+str(run_id))
    else:observed=event['workflow_run'];run_id=int(observed['id'])
    need(observed['path']==WORKFLOW and observed['status']=='completed' and observed['conclusion']=='success',
         'V3_CERTIFIER_EVENT_NOT_TERMINAL_SUCCESS')
    source=EXECUTION_SOURCE;path=certificate_path(source,run_id)
    # A repeated certification is a verified read-only no-op. It never emits a
    # second identity, rewrites R6 or invokes the completed investigation.
    head=route.json('git/ref/heads/'+BRANCH)['object']['sha']
    import urllib.error
    try:old=file_at(route,path,head)
    except urllib.error.HTTPError as error:
        if error.code!=404:raise
    else:
        verify_registered_certificate(route,head,source,run_id)
        print(json.dumps({'state':'CERTIFICATE_ALREADY_NATIVE_VERIFIED_NO_WRITE','path':path,'target_run_id':run_id}))
        return
    if os.environ['GITHUB_EVENT_NAME']=='workflow_dispatch':
        need(head==RECOVERY_PROOF,'CERTIFIER_RECOVERY_EXPECTED_HEAD')
    gate=eligible_certificate(route,run_id,source)
    oid=gate['evidence_oid']
    issuer_run=int(os.environ['GITHUB_RUN_ID'])
    inventory=route.json('actions/runs/'+str(issuer_run)+'/attempts/1/jobs?per_page=100')
    need(inventory.get('total_count')==len(inventory.get('jobs',[]))==1,'CERTIFIER_ISSUER_INVENTORY')
    job=inventory['jobs'][0]
    need(job['name']=='certify-v3' and job['run_id']==issuer_run,'CERTIFIER_ISSUER_JOB')
    record=validate_record({'schema':SCHEMA,'path':path,'gate':gate,
        'issuer':{'source_sha':os.environ['LAB_SOURCE_SHA'],'trigger_sha':os.environ['GITHUB_SHA'],
                  'run_id':issuer_run,'job_id':job['id']}},source,run_id)
    legacy=file_at(route,LEGACY_CERT,oid)
    from .runtime import EVIDENCE_BRANCH
    need(EVIDENCE_BRANCH==BRANCH,'V3_CERTIFIER_EVIDENCE_NAMESPACE')
    need(not existing_record(route,oid,path,record),'CERTIFICATE_CONCURRENT_ALREADY_EXISTS')
    committed=atomic_publish(route,oid,{path:encoded(record)},
             'Accept real R3 native E2E proof only after entire run success')
    need(file_at(route,path,committed)==encoded(record) and file_at(route,LEGACY_CERT,committed)==legacy,
         'V3_CERTIFIER_REMOTE_BYTE_READBACK')
    # The certificate was bound to its immutable proof ancestor. Validate the
    # newly committed descendant relation and all underlying proofs again.
    protected={name:route.json('branches/'+name)['protected']
               for name in ('main',EXEC)}
    verify_operational_acceptance(route,gate,source,protected)
    print('MXM_CERTIFICATE_ISSUED '+json.dumps({'schema':'mxm.e2e.native-certificate-issuance.v4',
                      'status':'END_TO_END_OPERATIONAL_ACCEPTED',
                      'certificate_commit':committed,
                      'proof_parent':oid,'target_run_id':run_id,'path':path,
                      'sha256':__import__('hashlib').sha256(encoded(record)).hexdigest(),
                      'real_orders':0,'economic_outcomes':0},sort_keys=True))

if __name__=='__main__':main()
