"""Artificial independent comparisons; no source decryption."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from .source_exposure_capacity_profile import profile
from .intrinsic_reference import snapshots
from .source_exposure_capacity import workflow,ROOT,PATH

def event(t,s,p):return {'t':t,'side':s,'raw':p}
class SourceExposureTests(unittest.TestCase):
    def run_source(self,rows,mutate=None):
        raw=b''.join((json.dumps(e)+'\n').encode() for e in rows)
        m={'quote_events':len(rows),'source_run_id':1,
           'members':{'capture.mxmenc':{'sha256':'a'}},'private_sha256':'b',
           'code_source':'c','source_head':'d'}
        r={'rows':len(rows),'run':1,'cipher_sha256':'a','private_sha256':'b',
           'source_code':'c','source_trigger':'d','first_ms':0,'end_ms':900000,
           'derived_sha256':hashlib.sha256(raw).hexdigest()}
        if mutate:mutate(r,m)
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'events';f.write_bytes(raw)
            result=profile(f,r,m)
            groups=list(snapshots(f))
            self.assertEqual(result['observed_groups'],len(groups))
            self.assertEqual(result['unavailable_observation_groups'],sum(v is None for _,v in groups))
            return result
    def test_broker_side_stale_and_locked_break_observation_stretches(self):
        rows=[event(0,'bid',100),event(0,'ask',102),event(3000,'bid',101),
              event(5500,'ask',103),event(6500,'bid',101),event(6500,'ask',104),
              event(12000,'bid',101),event(13000,'ask',105),
              event(14000,'ask',101),event(14500,'ask',105),
              event(15000,'bid',100),event(15000,'ask',103)]
        p=self.run_source(rows)
        self.assertEqual(p['unavailable_observation_groups'],2)
        self.assertEqual(p['healthy_observation_groups'],7)
        self.assertEqual(p['observed_qualified_stretches'],3)
        self.assertEqual(p['observed_stretches_at_least_5min'],0)
        self.assertFalse(p['between_observation_liquidity_proven'])
    def test_valid_book_does_not_fabricate_quotes_across_silent_gap(self):
        rows=[event(0,'bid',100),event(0,'ask',102),
              event(5000,'bid',101),event(5000,'ask',103),
              event(11000,'bid',102),event(11000,'ask',104)]
        p=self.run_source(rows)
        self.assertEqual(p['unavailable_observation_groups'],0)
        self.assertEqual(p['observed_qualified_stretches'],2)
        self.assertEqual(p['max_groups_in_one_stretch'],2)
        self.assertFalse(p['broker_fills_proven'])
    def test_five_minute_boundary_still_not_historical_execution_proof(self):
        rows=[]
        for t in range(0,303000,3000):
            rows.extend((event(t,'bid',100+t//3000),event(t,'ask',102+t//3000)))
        p=self.run_source(rows)
        self.assertEqual(p['observed_stretches_at_least_5min'],1)
        self.assertEqual(p['longest_qualified_observation_span_bucket'],'AT_LEAST_5_MINUTES')
        self.assertEqual(p['observed_qualified_stretches'],1)
        self.assertFalse(p['historical_execution_costs_proven'])
    def test_bad_hash_counts_or_order_never_used(self):
        rows=[event(0,'bid',100),event(0,'ask',102)]
        for mutate in (lambda r,m:r.update(derived_sha256='0'*64),
                       lambda r,m:r.update(source_code='WRONG'),
                       lambda r,m:m.update(quote_events=100)):
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                self.run_source(rows,mutate)
        with self.assertRaises(ValueError):
            self.run_source([event(2000,'bid',100),event(0,'ask',102)])
    def test_finite_read_only_workflow(self):
        w=workflow();self.assertEqual(json.loads((ROOT/PATH).read_bytes()),w)
        self.assertEqual(w['on']['push']['paths'],[PATH])
        self.assertNotIn('workflow_dispatch',w['on'])
        self.assertNotIn('pull_request',w['on'])
        j=w['jobs']['source-exposure-capacity']
        self.assertEqual(j['permissions'],{'contents':'read','actions':'read'})
        self.assertEqual(sum('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM' in
                             s.get('env',{}) for s in j['steps']),1)
        body='\n'.join(s.get('run','') for s in j['steps'])
        for forbidden in ('intrinsic_development result','intrinsic_recovery result',
                          'dotnet run','gh workflow run','R3_CTRADER_ACCESS_TOKEN',
                          'SUCCESSOR_APP_PRIVATE_KEY','ExecuteMarketOrder'):
            self.assertNotIn(forbidden,body)
if __name__=='__main__':unittest.main()
