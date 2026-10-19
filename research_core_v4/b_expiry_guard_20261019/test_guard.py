import copy
import json
from pathlib import Path
import unittest
from . import guard as g

class ExpiryGuard(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads((g.ROOT/'docs/p0-successor-b/20261018/NATIVE_BUNDLE_39147483523.json').read_bytes())
        self.run = {'id':g.RUN,'head_sha':g.SOURCE,'head_branch':g.BRANCH,'path':g.WORKFLOW,
                    'run_attempt':1,'event':'workflow_dispatch','repository':{'full_name':g.REPO},
                    'status':'waiting'}
        self.deadline = self.bundle['manifest']['expires_at']

    def decide(self, reviews=None, now=None):
        return g.decision(self.bundle,self.run,[] if reviews is None else reviews,
                          self.deadline if now is None else now)

    def test_valid_manifest_never_cancelled(self):
        self.assertEqual(self.decide(now=self.deadline-1),'VALID_WAITING_NO_ACTION')

    def test_expiry_boundary_and_long_session_gap(self):
        for now in (self.deadline,self.deadline+86400*365):
            self.assertEqual(self.decide(now=now),'CANCEL_EXPIRED_UNREVIEWED')

    def test_any_native_review_prevents_cancel(self):
        for state in ('approved','rejected','unknown'):
            reviews=[{'state':state,'environments':[{'id':g.ENVIRONMENT}]}]
            self.assertEqual(self.decide(reviews),'REVIEW_PRESENT_NO_ACTION')

    def test_ambiguous_or_malformed_history_stops(self):
        r={'state':'approved','environments':[{'id':g.ENVIRONMENT}]}
        for reviews in ([r,r],[{}],[{'environments':[{}]}],{},None):
            with self.subTest(reviews=reviews),self.assertRaises(ValueError):
                g.decision(self.bundle,self.run,reviews,self.deadline)

    def test_all_identity_mismatches_stop(self):
        for key,value in (('id',g.RUN+1),('head_sha','a'*40),('head_branch','main'),
                          ('path','other.yml'),('run_attempt',2),('event','push'),
                          ('repository',{'full_name':'someone/other'})):
            run=copy.deepcopy(self.run);run[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                g.decision(self.bundle,run,[],self.deadline)

    def test_manifest_or_root_tampering_stops(self):
        for section,key in (('manifest','expires_at'),('root','lease_seconds')):
            bundle=copy.deepcopy(self.bundle);bundle[section][key]+=1
            with self.assertRaises(ValueError):g.decision(bundle,self.run,[],self.deadline)

    def test_only_waiting_is_cancellable(self):
        for status in ('queued','in_progress','requested','pending'):
            self.run['status']=status
            self.assertEqual(self.decide(),'NOT_WAITING_NO_ACTION')
        self.run['status']='completed'
        self.assertEqual(self.decide(),'TERMINAL_NO_ACTION')

    def test_never_mutates_inputs(self):
        before=copy.deepcopy((self.bundle,self.run));self.decide()
        self.assertEqual((self.bundle,self.run),before)

if __name__ == '__main__':unittest.main()
