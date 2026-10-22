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

def inspect_dispatch(record,dispatch_oid,runs,now_unix,*,preclaim_failed_run_ids=()):
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
    if len(found)==1:
        run=found[0]
        if (run.get('id') in preclaim_failed_run_ids and run.get('status')=='completed'
            and run.get('conclusion') in ('failure','cancelled','timed_out')
            and now_unix-record['issued_at_unix']>=GRACE_SECONDS):
            return 'REISSUE_AFTER_ATOMIC_STALE_PARENT_INVALIDATION'
        return 'RUN_OBSERVED_NO_REISSUE'
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

def dispatch_inventory(route,issued_at_unix,now_unix):
    """Bounded, workflow-specific and fully paginated; incomplete is a HOLD."""
    from urllib.parse import urlencode
    start=datetime.fromtimestamp(issued_at_unix,timezone.utc).isoformat()
    end=datetime.fromtimestamp(now_unix,timezone.utc).isoformat()
    rows=[];seen=set()
    for page in range(1,11):
        query=urlencode({'branch':BRANCH,'event':'workflow_dispatch','created':start+'..'+end,
                         'per_page':100,'page':page})
        data=route.json('actions/workflows/mxm-integrated-p0.yml/runs?'+query)
        batch=data['workflow_runs']
        need(type(batch) is list and data.get('total_count',1001)<=1000,'DISPATCH_INVENTORY_LIMIT_HOLD')
        for run in batch:
            need(run['id'] not in seen,'DISPATCH_INVENTORY_UNSTABLE_HOLD')
            seen.add(run['id']);rows.append(run)
        if len(batch)<100:
            need(len(rows)==data['total_count'],'DISPATCH_INVENTORY_INCOMPLETE_HOLD')
            return rows
    need(False,'DISPATCH_INVENTORY_LIMIT_HOLD')
