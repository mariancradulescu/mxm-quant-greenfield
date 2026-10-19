import unittest
from .recovery_v2 import predecessor,workflow

def fixture():
    run={'id':1,'path':'.github/workflows/mxm-integrated-p0.yml','head_branch':'mxm-remediation-p0-p4-20261015-v1','run_attempt':1,'status':'completed'}
    jobs=[{'name':n,'status':'completed','conclusion':'success'} for n in ('preflight','segment-intent','execution-fence','investigation','durable-archive')]
    return {'pending':None},run,jobs

class RecoveryGuardTests(unittest.TestCase):
    def test_completed_native_successor(self):self.assertEqual(predecessor(*fixture()),'CONTINUE_DURABLE_SUCCESSOR')
    def test_active_native_run_waits_without_dispatch(self):
        s,r,j=fixture();r['status']='in_progress';self.assertEqual(predecessor(s,r,j),'WAIT_ACTIVE_NATIVE_RUN')
    def test_skipped_worker_never_authorizes_continuation(self):
        s,r,j=fixture();j[3]['conclusion']='skipped'
        with self.assertRaises(Exception):predecessor(s,r,j)
    def test_failed_publisher_requires_remote_reconciliation(self):
        s,r,j=fixture();j[-1]['conclusion']='failure';self.assertEqual(predecessor(s,r,j),'RECONCILE_EXACT_REMOTE_PUBLICATION')
    def test_skipped_publisher_does_not_look_like_publication(self):
        s,r,j=fixture();j[-1]['conclusion']='skipped'
        with self.assertRaises(Exception):predecessor(s,r,j)
    def test_post_fence_crash_is_held(self):
        s,r,j=fixture();s['pending']={'phase':'EXECUTION_FENCED'};self.assertEqual(predecessor(s,r,j),'HOLD_AMBIGUOUS_EXPOSURE')
    def test_wrong_workflow_is_not_an_issuer(self):
        s,r,j=fixture();r['path']='other.yml'
        with self.assertRaises(Exception):predecessor(s,r,j)
    def test_canonical_queue_does_not_displace_pending_continuation(self):
        text=workflow('a'*40);self.assertIn('queue: max',text);self.assertIn('ref: '+'a'*40,text);self.assertNotIn('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM:',text)

if __name__=='__main__':unittest.main()
