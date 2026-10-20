"""Bounded keyless uncertain-ACK recovery for *already admitted* work.

An old dispatch after the new durable CAS intent is stale: both worker
preflight and claim require the exact evidence parent. No economy, secrets or
new programme may be introduced by this observer.
"""
from datetime import datetime,timezone
from .common import need

WORKFLOW='.github/workflows/mxm-integrated-p0.yml'
BRANCH='mxm-remediation-p0-p4-20261015-v1'
GRACE_SECONDS=900

def inspect_dispatch(record,dispatch_oid,runs,now_unix):
    need(record.get('schema')=='mxm.native-dispatch-intent.v3' and
         type(record.get('issued_at_unix')) is int and
         type(now_unix) is int and now_unix>=record['issued_at_unix'] and
         record.get('retry_budget')==1 and
         record.get('automatic_post_retry') is True,
         'DISPATCH_RECOVERY_INTENT_SCHEMA')
    need(type(dispatch_oid) is str and len(dispatch_oid)==40,
         'DISPATCH_RECOVERY_OID')
    target='MXM P0 '+dispatch_oid
    found=[x for x in runs if x.get('path')==WORKFLOW and
           x.get('head_branch')==BRANCH and x.get('display_title')==target]
    if len(found)>1:return 'AMBIGUOUS_DUPLICATE_RUNS_HOLD'
    if len(found)==1:return 'RUN_OBSERVED_NO_REISSUE'
    if now_unix-record['issued_at_unix']<GRACE_SECONDS:return 'PENDING_DELIVERY_NO_REISSUE'
    # A bounded page too recent to cover issuance cannot prove absence.
    if len(runs)>=100:
        try:
            oldest=min(int(datetime.fromisoformat(x['created_at'].replace('Z','+00:00')).timestamp()) for x in runs)
        except (KeyError,TypeError,ValueError):
            return 'INCOMPLETE_RUN_INVENTORY_HOLD'
        if oldest>record['issued_at_unix']:
            return 'INCOMPLETE_RUN_INVENTORY_HOLD'
    return 'REISSUE_AFTER_ATOMIC_STALE_PARENT_INVALIDATION'
