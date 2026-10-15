import os,unittest
from unittest.mock import patch
from . import runtime as r
class Safety(unittest.TestCase):
    def test_uncertain_reserve(self):
        st={'requests':{'M5':5,'BID_ASK':7},'uncertain_wire':[{'k':'M5'},{'k':'bid'}]}
        self.assertEqual(r.remaining(st,{'caps':{'M5':10,'BID_ASK':10}}),{'M5':4,'BID_ASK':2})
    @patch.dict(os.environ,{'GITHUB_SHA':'head','GITHUB_RUN_ID':'1'})
    def test_duplicate_claim_never_dispatches(self):
        with patch.object(r.io,'api',side_effect=RuntimeError('EXISTS')) as api:
            with self.assertRaises(RuntimeError):r.dispatch({'branch':'b'},1321,1)
            self.assertEqual(api.call_count,1)
            self.assertEqual(api.call_args.args[:2],('git/refs','POST'))
    @patch.dict(os.environ,{'GITHUB_SHA':'head','GITHUB_RUN_ID':'1'})
    def test_lost_dispatch_ack_never_reposts(self):
        def api(path,method='GET',data=None):
            if method=='POST' and 'dispatches' in path:raise TimeoutError()
            return {'object':{'sha':'head'}}
        with patch.object(r.io,'api',side_effect=api) as calls:
            with self.assertRaises(TimeoutError):r.dispatch({'branch':'b'},1321,1)
            self.assertEqual(sum('dispatches' in x.args[0] for x in calls.call_args_list),1)
    @patch.dict(os.environ,{'GITHUB_SHA':'head','GITHUB_RUN_ID':'1'})
    def test_success_requires_actual_unique_run(self):
        def api(path,method='GET',data=None):
            if path.startswith('actions/runs?'):return {'workflow_runs':[{'head_sha':'head','display_title':'MXM autonomous g1321 s1','id':2}]}
            return {'object':{'sha':'head'}}
        with patch.object(r.io,'api',side_effect=api):
            self.assertEqual(r.dispatch({'branch':'b'},1321,1)['successor_run'],2)
if __name__=='__main__':unittest.main()
