"""Independent R3 operational certificate verifier.

A favorable JSON status is never authority. Verify remotely persisted,
content-hashed cold/negative/authentic proofs, real *completed* native jobs,
the encrypted checkpoint lineage and actual source/control-plane protections.
The emitter runs in a separate keyless job; verification may occur only after
the native workflow is terminal. Fail-closed if any producer is missing.
"""
import re
from .common import need,digest,bytes_digest,encoded
from .attest_v3 import (proof_paths,native_jobs,validate_public_state,
                        validate_cold_artifact,validate_negative_artifact,native_checkout_provenance)
from .evidence_v3 import COLD_SCHEMA,NEGATIVE_SCHEMA,ADAPTER_SCHEMA
BRANCH='mxm-o04-integrated-laboratory-evidence'
EXEC='mxm-remediation-p0-p4-20261015-v1'
from .runtime import SOURCE_BRANCH as CODE
WORKFLOW='.github/workflows/mxm-integrated-p0.yml'
FIELDS={'schema','status','source_sha','evidence_branch','evidence_oid','sequence',
        'run_id','checkpoint_cipher_sha256','native_receipt_path','issuer_path',
        'cold_proof_path','negative_proof_path','authentic_adapter_path'}

def verify_effective_controls(route):
    """Read applied rules, including bypass actors; a branch flag is insufficient.

    The only permitted evidence writer is the already authorized successor App,
    not a newly introduced credential or another workflow's shared GITHUB_TOKEN.
    """
    from .custody import effective_controls_reader
    route=effective_controls_reader(route)
    from research_core_v4.p0_successor_a_20261017.issuer import APP_ID
    snapshots={}
    for branch in ('main',EXEC,CODE,BRANCH):
        rules=route.json('rules/branches/'+branch)
        need(type(rules) is list,'V3_EFFECTIVE_RULE_INVENTORY')
        kinds={r['type'] for r in rules}
        need({'deletion','non_fast_forward'}<=kinds,'V3_EFFECTIVE_HISTORY_PROTECTION')
        if branch in ('main',EXEC):
            need({'pull_request','required_status_checks'}<=kinds and
                 any(r['type']=='required_status_checks' and
                     r.get('parameters',{}).get('required_status_checks') for r in rules),
                 'V3_EFFECTIVE_REVIEW_AND_CI_REQUIRED')
        else:
            restrictions=[r for r in rules if r['type']=='update']
            need(restrictions,'V3_EFFECTIVE_UPDATE_RESTRICTION_REQUIRED')
            expected=[] if branch==CODE else [{'actor_id':APP_ID,'actor_type':'Integration','bypass_mode':'always'}]
            for restriction in restrictions:
                policy=route.json('rulesets/'+str(restriction['ruleset_id']))
                need(policy.get('enforcement')=='active' and policy.get('bypass_actors')==expected,
                     'V3_EFFECTIVE_SOURCE_OR_WRITER_AUTHORITY')
        snapshots[branch]=rules
    return snapshots

def _artifact(route,oid,path):
    from .runtime import file_at
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json
    need(type(path) is str and
         re.fullmatch(r'typed-successor/(segments/[0-9]+/receipt|verification/[A-Z0-9_-]+)\.json',path),
         'V3_EVIDENCE_PATH')
    return strict_json(file_at(route,path,oid))

def verify_operational_acceptance(route,gate,source,protected):
    need(type(gate) is dict and set(gate)==FIELDS and
         gate.get('schema')=='mxm.e2e.native-acceptance.v3' and
         gate.get('status')=='END_TO_END_OPERATIONAL_ACCEPTED' and
         gate.get('source_sha')==source and
         gate.get('evidence_branch')==BRANCH,
         'V3_CERTIFICATE_SCHEMA')
    need(protected=={'main':True,EXEC:True} and
         route.json('branches/'+CODE)['protected'] is True and
         route.json('branches/'+BRANCH)['protected'] is True,
         'V3_CONTROL_PLANE_PROTECTION')
    verify_effective_controls(route)
    oid=gate['evidence_oid'];run_id=gate['run_id']
    need(type(oid) is str and re.fullmatch('[a-f0-9]{40}',oid) and
         type(run_id) is int and run_id>0,
         'V3_EVIDENCE_OID_AND_RUN_ID')
    # The certificate itself (and later prospectively admitted segments)
    # append commits to the evidence branch. The sealed technical proof must
    # be an immutable ancestor, not necessarily the current HEAD.
    head=route.json('git/ref/heads/'+BRANCH)['object']['sha']
    if head!=oid:
        relation=route.json('compare/'+oid+'...'+head)
        need(relation.get('status')=='ahead' and
             relation.get('ahead_by',0)>0 and
             relation.get('behind_by')==0 and
             relation.get('base_commit',{}).get('sha')==oid,
             'V3_CERTIFICATE_NOT_IN_PROTECTED_ANCESTRY')
    state=_artifact_state(route,oid)
    validate_public_state(state,run_id,source)
    need(type(gate['sequence']) is int and state['sequence']==gate['sequence']
         and state['ciphertext_sha256']==gate['checkpoint_cipher_sha256'],
         'V3_PUBLIC_STATE_CHANGED')
    jobs=native_jobs(route,run_id,('preflight','segment-intent',
        'execution-fence','investigation','durable-archive','cold-readback',
        'fault-probes','attest-v3'),require_completed_run=True,expected_head_sha=state.get('last_trigger_sha'))
    source_material=native_checkout_provenance(route,run_id,source,state['last_trigger_sha'],jobs)
    expected=proof_paths(run_id)
    need(all(gate[k]==expected[v] for k,v in (
        ('issuer_path','issuer'),('cold_proof_path','cold'),
        ('negative_proof_path','negative'),
        ('authentic_adapter_path','adapter'))) and
        gate['native_receipt_path']==
        'typed-successor/segments/'+str(state['sequence'])+'/receipt.json',
        'V3_CERTIFICATE_PATH_BINDING')
    issuer=_artifact(route,oid,expected['issuer'])
    need(issuer.get('schema')=='mxm.e2e.native-proof-issuer.v3' and
         issuer.get('run_id')==run_id and
         issuer.get('source_sha')==source and
         issuer.get('sequence')==state['sequence'] and
         issuer.get('ciphertext_sha256')==state['ciphertext_sha256'] and
         issuer.get('economic_release') is False and issuer.get('orders')==0
         and issuer.get('job_ids')==
         {k:jobs[k] for k in jobs if k!='attest-v3'},
         'V3_NATIVE_ISSUER_ORIGIN')
    from .runtime import file_at
    need(issuer.get('checkpoint_oid') and
         encoded(state)==file_at(route,'typed-successor/program-state.json',
                                 issuer['checkpoint_oid']),
         'V3_ISSUER_CHECKPOINT_LINEAGE')
    cold=_artifact(route,oid,expected['cold'])
    negative=_artifact(route,oid,expected['negative'])
    adapter=_artifact(route,oid,expected['adapter'])
    need(issuer['cold_sha256']==digest(cold) and
         issuer['negative_sha256']==digest(negative) and
         issuer['adapter_sha256']==digest(adapter),
         'V3_NATIVE_EVIDENCE_DIGEST_DRIFT')
    validate_cold_artifact(cold,adapter,state,run_id,source,
                           issuer['checkpoint_oid'])
    validate_negative_artifact(route,negative,run_id,source,state)
    need(cold['multi_program_A_B_A_verified'] is True and
         len(cold['programme_checkpoints'])>=2 and
         cold['budgets_and_quarantine_verified'] is True and
         cold['all_admitted_programmes_complete'] is True and
         cold['authentic_nonoutcome_results'] and
         cold['orders']==cold['new_outcomes']==0,
         'V3_REAL_MULTI_PROGRAMME_AND_AUTHENTIC_INTEGRATION_NOT_PROVEN')
    rec=_artifact(route,oid,gate['native_receipt_path'])
    need(rec.get('schema')=='mxm.integrated-segment-receipt.v2' and
         rec.get('trigger_sha')==state.get('last_trigger_sha') and
         rec.get('run_id')==run_id and
         rec.get('source_sha')==source and
         rec.get('sequence')==state['sequence'] and
         rec.get('ciphertext_sha256')==state['ciphertext_sha256'] and
         rec.get('accounting_after')==state['accounting'] and
         rec.get('pending') is None and rec.get('safe_stop') is True
         and rec.get('orders')==rec.get('new_outcomes')==
         rec.get('new_economic_identities_opened')==
         rec.get('new_identity_reservations')==
         rec.get('broker_requests')==0 and
         rec.get('native_wire_counts')=={} and
         rec.get('economic_release') is False,
         'V3_NATIVE_RECEIPT_OR_OUTCOME_MISMATCH')
    need(state['accounting']['lanes']['V2']['outcome_charged']==21 and
         state['accounting']['lanes']['V2']['reservation_holds']==1 and
         state['accounting']['refunds']==0,
         'V3_ORIGINAL_TRIAL_ACCOUNTING_CHANGED')
    return {'status':'END_TO_END_OPERATIONAL_ACCEPTED',
            'source_sha':source,'run_id':run_id,'checkpoint_oid':oid,
            'ciphertext_sha256':state['ciphertext_sha256'],
            'native_checkout_provenance':source_material}

def _artifact_state(route,oid):
    from .runtime import file_at
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json
    return strict_json(file_at(route,'typed-successor/program-state.json',oid))
