"""Native, fail-closed acceptance verifier. No JSON status can release research.

All referenced records must be in the same protected evidence lineage. Runtime
source must be sealed; jobs must have terminated successfully on GitHub. There
is deliberately no fall-through for missing technical or authentic proofs.
"""
import re
from .common import need,digest

BRANCH='mxm-o04-integrated-laboratory-evidence'
EXEC='mxm-remediation-p0-p4-20261015-v1'
CODE='mxm-o04-successor-code-integrated-p0-r3'
WORKFLOW='.github/workflows/mxm-integrated-p0.yml'
JOBS=('preflight','segment-intent','execution-fence','investigation','durable-archive','cold-readback')
FIELDS={'schema','status','source_sha','evidence_branch','evidence_oid','sequence',
        'run_id','checkpoint_cipher_sha256','native_receipt_path',
        'cold_proof_path','negative_proof_path','authentic_adapter_path'}

def _artifact(route,oid,path):
    from .runtime import file_at
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json
    need(type(path) is str and re.fullmatch(r'typed-successor/(segments/[0-9]+/receipt|verification/[A-Z0-9_-]+)\.json',path),
         'ACCEPTANCE_EVIDENCE_PATH')
    return strict_json(file_at(route,path,oid))

def verify_operational_acceptance(route,gate,source,protected):
    need(type(gate) is dict and set(gate)==FIELDS and
         gate['schema']=='mxm.e2e.native-acceptance.v3' and
         gate['status']=='END_TO_END_OPERATIONAL_ACCEPTED' and
         gate['source_sha']==source and gate['evidence_branch']==BRANCH,
         'NATIVE_CERTIFICATE_SCHEMA')
    need(protected=={'main':True,EXEC:True} and
         route.json('branches/'+CODE)['protected'] is True and
         route.json('branches/'+BRANCH)['protected'] is True,
         'ACCEPTANCE_CONTROL_PLANE_NOT_PROTECTED')
    oid=gate['evidence_oid']
    need(type(oid) is str and re.fullmatch('[a-f0-9]{40}',oid) and
         route.json('git/ref/heads/'+BRANCH)['object']['sha']==oid,
         'CERTIFICATE_NOT_CURRENT_PROTECTED_EVIDENCE')
    from .runtime import file_at
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json
    s=strict_json(file_at(route,'typed-successor/program-state.json',oid))
    need(s['source_sha']==source and type(gate['sequence']) is int and
         gate['sequence']>=21 and s['sequence']==gate['sequence'] and
         s['pending'] is None and s['safe_stop'] is True and
         s['orders']==0 and s['ciphertext_sha256']==gate['checkpoint_cipher_sha256'],
         'CERTIFICATE_CHECKPOINT_NOT_RECOVERABLE')
    run_id=gate['run_id']
    need(type(run_id) is int and run_id>0 and s['last_run_id']==run_id,
         'CERTIFICATE_RUN_ID')
    run=route.json('actions/runs/'+str(run_id))
    need(run['path']==WORKFLOW and run['head_branch']==EXEC and
         run['run_attempt']==1 and run['status']=='completed' and
         run['conclusion']=='success' and run['id']==run_id,
         'CERTIFICATE_WRONG_NATIVE_WORKFLOW')
    jobs=route.json('actions/runs/'+str(run_id)+'/attempts/1/jobs?per_page=100')['jobs']
    for name in JOBS:
        exact=[j for j in jobs if j.get('name')==name]
        need(len(exact)==1 and exact[0]['status']=='completed' and
             exact[0]['conclusion']=='success' and exact[0]['run_id']==run_id,
             'CERTIFICATE_MISSING_NATIVE_JOB_'+name.upper().replace('-','_'))
    need(gate['native_receipt_path']==f'typed-successor/segments/{s["sequence"]}/receipt.json',
         'CERTIFICATE_RECEIPT_WRONG_PATH')
    rec=_artifact(route,oid,gate['native_receipt_path'])
    need(rec['schema']=='mxm.integrated-segment-receipt.v2' and
         rec['run_id']==run_id and rec['source_sha']==source and
         rec['sequence']==s['sequence'] and
         rec['ciphertext_sha256']==s['ciphertext_sha256'] and
         rec['accounting_after']==s['accounting'] and rec['pending'] is None
         and rec['orders']==0 and rec['new_outcomes']==0 and
         rec['new_economic_identities_opened']==0 and
         rec['new_identity_reservations']==0 and rec['safe_stop'] is True,
         'CERTIFICATE_NATIVE_RECEIPT_MISMATCH')
    cold=_artifact(route,oid,gate['cold_proof_path'])
    need(cold['schema']=='mxm.integrated-cold-readback.v3' and
         cold['run_id']==run_id and cold['source_sha']==source and
         cold['sequence']==s['sequence'] and
         cold['ciphertext_sha256']==s['ciphertext_sha256'] and
         cold['accounting']==s['accounting'] and
         cold['original_unchanged'] is True and
         cold['multi_program_A_B_A_verified'] is True and
         cold['shared_catalogue_sha256'] and
         cold['budgets_and_quarantine_verified'] is True and
         cold['all_admitted_programmes_complete'] is True and
         cold['orders']==cold['new_outcomes']==0,
         'CERTIFICATE_COLD_PROOF_INCOMPLETE')
    negative=_artifact(route,oid,gate['negative_proof_path'])
    mandatory=('pre_fence_crash_recovered','ambiguous_ack_no_duplicate_push',
               'concurrent_writer_rejected','incomplete_checkpoint_rejected',
               'missing_credentials_refused','closed_programme_not_replayed',
               'partition_isolation')
    need(negative['schema']=='mxm.e2e.native-negatives.v3' and
         negative['source_sha']==source and negative['checkpoint_oid']==oid and
         negative['run_id']==run_id and
         all(negative.get(k) is True for k in mandatory) and
         negative['new_outcomes']==negative['orders']==0,
         'CERTIFICATE_NEGATIVE_PROOFS_INCOMPLETE')
    adapter=_artifact(route,oid,gate['authentic_adapter_path'])
    need(adapter['schema']=='mxm.e2e.authentic-adapter.v3' and
         adapter['source_sha']==source and adapter['checkpoint_oid']==oid and
         adapter['run_id']==run_id and
         adapter['preserved_pepperstone_corpus_verified'] is True and
         adapter['authentic_nonoutcome_native_path_verified'] is True and
         adapter['fixture_only'] is False and
         type(adapter['preserved_corpus_sha256']) is str and
         re.fullmatch('[a-f0-9]{64}',adapter['preserved_corpus_sha256']) and
         adapter['orders']==adapter['economic_outcomes']==0,
         'CERTIFICATE_AUTHENTIC_ADAPTER_NOT_PROVEN')
    need(s['accounting']['lanes']['V2']['outcome_charged']==21 and
         s['accounting']['lanes']['V2']['reservation_holds']==1 and
         s['accounting']['refunds']==0,
         'CERTIFICATE_ORIGINAL_TRIAL_ACCOUNTING_CHANGED')
    return {'status':'END_TO_END_OPERATIONAL_ACCEPTED',
            'source_sha':source,'run_id':run_id,'checkpoint_oid':oid,
            'ciphertext_sha256':s['ciphertext_sha256']}
