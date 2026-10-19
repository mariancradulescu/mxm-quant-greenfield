"""No-outcome tests of quote provenance and cache-window separation."""
import ast,copy,math,unittest
from collections import Counter,defaultdict
from pathlib import Path
class CachedSupport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree=ast.parse(Path(__file__).with_name('frontier_cached_support.py').read_text())
        funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('quote_reason','project','native_worker_proof')]
        def need(v,c):
            if not v:raise ValueError(c)
        e={'math':math,'Counter':Counter,'defaultdict':defaultdict,'need':need};exec(compile(ast.Module(body=funcs,type_ignores=[]),'<cached-support>','exec'),e);cls.e=e
    def quote(self):return {'symbol_id':1,'boundary_ms':10000,'sides':{n:{'state':'AUTHENTIC_CAUSAL_QUOTE','source_has_more':False,'timestamp_ms':9000,'age_ms':1000,'price':p} for n,p in [('bid',1.),('ask',1.1)]}}
    def test_native_proof_binds_original_attempt_and_does_not_accept_retry(self):
        j={'id':118148506560,'name':'pregate','run_id':39278529554,'head_sha':'abc','status':'completed','conclusion':'success','run_attempt':1}
        proof=self.e['native_worker_proof'];self.assertTrue(proof([j],39278529554,'abc'))
        for changed in ({'run_attempt':2},{'conclusion':'failure'},{'head_sha':'other'},{'id':0},{'run_id':0}):self.assertFalse(proof([{**j,**changed}],39278529554,'abc'))
        self.assertFalse(proof([],39278529554,'abc'));self.assertFalse(proof([j,j],39278529554,'abc'))
    def test_authentic_quote_is_not_fill(self):self.assertEqual(self.e['quote_reason'](self.quote()),'AUTHENTIC_CAUSAL_BILATERAL_SUPPORT_NOT_FILL')
    def test_future_and_timestamp_mismatch_fail(self):
        q=self.quote();q['sides']['bid'].update(timestamp_ms=11000,age_ms=-1000);self.assertEqual(self.e['quote_reason'](q),'FUTURE_OR_NEGATIVE_AGE')
        q=self.quote();q['sides']['bid']['age_ms']=500;self.assertEqual(self.e['quote_reason'](q),'AGE_TIMESTAMP_MISMATCH')
    def test_unknown_pagination_and_nan_fail(self):
        q=self.quote();del q['sides']['ask']['source_has_more'];self.assertEqual(self.e['quote_reason'](q),'PAGINATION_UNRESOLVED')
        q=self.quote();q['sides']['ask']['price']=math.nan;self.assertEqual(self.e['quote_reason'](q),'SIDE_FIELDS_UNRESOLVED')
    def test_window_and_conflict_do_not_create_economic_results(self):
        q=self.quote();c={'raw_quote_receipts':[q],'catalog':{'full':{}},'all_identity_status':[],'summary':{}}
        m=[{'symbol_id':1,'symbol':'A','broker_native_context':'C'}];before=copy.deepcopy(c)
        r=self.e['project'](c,m,20000,30000,100000);self.assertEqual(r['valid_bilateral_boundaries'],1);self.assertEqual(r['valid_bilateral_boundaries_in_M5_period'],0);self.assertEqual(c,before)
        bad=copy.deepcopy(q);bad['sides']['bid']['price']=.9;c['raw_quote_receipts'].append(bad);r=self.e['project'](c,m,0,30000,100000)
        self.assertEqual(r['valid_bilateral_boundaries'],0);self.assertEqual(r['conflicting_boundaries'],1);self.assertEqual(r['economic_outcomes'],0)
if __name__=='__main__':unittest.main()
