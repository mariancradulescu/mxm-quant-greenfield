"""Native completed-job admission for the keyless recovery path.

A task commit precedes token revocation. Thus a Git checkpoint alone cannot
prove that the previous issuer successfully revoked its token. The sealed
workflow emits success/output only after confirmed revocation. Require that
native issuer job outcome before allowing another automatic continuation.
"""

def admit(state,run,jobs,source,branch,workflow):
    if not state['done']:return 'NO_FIRST_ISSUER_RECEIPT_STOP'
    prior=state['done'][-1]['run_id']
    if (run.get('id')!=prior or run.get('head_sha')!=source or run.get('head_branch')!=branch or
        run.get('path')!=workflow or run.get('run_attempt')!=1):return 'PREVIOUS_WORKLOAD_IDENTITY_STOP'
    issuers=[j for j in jobs if j.get('name')=='delegated-issuer']
    if len(issuers)!=1 or issuers[0].get('run_id')!=prior:return 'PREVIOUS_ISSUER_IDENTITY_STOP'
    job=issuers[0]
    if job.get('status')!='completed':return 'PREVIOUS_ISSUER_NOT_TERMINAL_WAIT'
    if job.get('conclusion')!='success':return 'PREVIOUS_ISSUER_FAILED_STOP'
    return 'ADMITTED'
