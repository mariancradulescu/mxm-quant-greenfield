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

CERT='typed-successor/END_TO_END_OPERATIONAL_ACCEPTANCE.json'
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
         and os.environ.get('GITHUB_EVENT_NAME')=='workflow_run'
         and os.environ.get('GITHUB_RUN_ATTEMPT')=='1',
         'V3_CERTIFIER_WORKLOAD')
    need(not any(os.environ.get(k) for k in (
         'SUCCESSOR_APP_PRIVATE_KEY','MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM',
         'CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')),
         'V3_CERTIFIER_KEYLESS')
    event=json.loads(open(os.environ['GITHUB_EVENT_PATH'],encoding='utf-8').read())
    observed=event['workflow_run']
    need(observed['path']==WORKFLOW and observed['status']=='completed'
         and observed['conclusion']=='success',
         'V3_CERTIFIER_EVENT_NOT_TERMINAL_SUCCESS')
    route=GetOnly()
    # Validate source authority from checked-out protected R3 SHA (not a
    # mutable candidate PR ref). GitHub-native authentication is read-only.
    anchors(route)
    run_id=int(observed['id']);source=os.environ['LAB_SOURCE_SHA']
    gate=eligible_certificate(route,run_id,source)
    oid=gate['evidence_oid']
    from .runtime import EVIDENCE_BRANCH
    need(EVIDENCE_BRANCH==BRANCH,'V3_CERTIFIER_EVIDENCE_NAMESPACE')
    committed=atomic_publish(route,oid,{CERT:encoded(gate)},
             'Accept real R3 native E2E proof only after entire run success')
    need(file_at(route,CERT,committed)==encoded(gate),
         'V3_CERTIFIER_REMOTE_BYTE_READBACK')
    # The certificate was bound to its immutable proof ancestor. Validate the
    # newly committed descendant relation and all underlying proofs again.
    protected={name:route.json('branches/'+name)['protected']
               for name in ('main',EXEC)}
    verify_operational_acceptance(route,gate,source,protected)
    print(json.dumps({'schema':'mxm.e2e.native-certificate-issuance.v3',
                      'status':'END_TO_END_OPERATIONAL_ACCEPTED',
                      'certificate_commit':committed,
                      'proof_parent':oid,'run_id':run_id,
                      'real_orders':0,'economic_outcomes':0},sort_keys=True))

if __name__=='__main__':main()
