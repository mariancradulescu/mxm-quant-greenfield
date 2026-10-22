"""Bounded handoff negative cases, no dispatch, token, or economic work."""
import unittest
from datetime import datetime,timezone
from .handoff_recovery import inspect_dispatch,WORKFLOW,BRANCH,GRACE_SECONDS

OID='a'*40
def intent():
    return {'schema':'mxm.native-dispatch-intent.v3','issued_at_unix':1000,
            'retry_budget':1,'automatic_post_retry':True}
def run(oid=OID):
    return {'path':WORKFLOW,'head_branch':BRANCH,'display_title':'MXM P0 '+oid,
            'created_at':'1970-01-01T00:18:00Z'}

class HandoffRecoveryTests(unittest.TestCase):
    def test_live_run_never_reissued(self):
        self.assertEqual(inspect_dispatch(intent(),OID,[run()],4000),'RUN_OBSERVED_NO_REISSUE')
    def test_ambiguous_duplicates_hold(self):
        self.assertEqual(inspect_dispatch(intent(),OID,[run(),run()],4000),'AMBIGUOUS_DUPLICATE_RUNS_HOLD')
    def test_short_grace_does_not_retry(self):
        self.assertEqual(inspect_dispatch(intent(),OID,[],1000+GRACE_SECONDS-1),'PENDING_DELIVERY_NO_REISSUE')
    def test_lost_ack_can_reissue_only_after_durable_cas_marker(self):
        self.assertEqual(inspect_dispatch(intent(),OID,[],1000+GRACE_SECONDS),
                         'REISSUE_AFTER_ATOMIC_STALE_PARENT_INVALIDATION')
    def test_no_unbounded_retry_or_partial_run_inventory(self):
        invalid=intent();invalid['retry_budget']=2
        with self.assertRaises(Exception):inspect_dispatch(invalid,OID,[],3000)
        newest={'path':'.github/workflows/unrelated.yml','head_branch':'main',
                'created_at':'1970-01-01T01:00:00Z','display_title':'other'}
        self.assertEqual(inspect_dispatch(intent(),OID,[newest]*100,4000),
                         'INCOMPLETE_RUN_INVENTORY_HOLD')
    def test_unrelated_run_does_not_count_as_issued(self):
        self.assertEqual(inspect_dispatch(intent(),OID,[run('b'*40)],4000),
                         'REISSUE_AFTER_ATOMIC_STALE_PARENT_INVALIDATION')

if __name__=='__main__':unittest.main()
