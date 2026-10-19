"""Checks for no-outcome accounting and feature diagnosis only."""
import ast,copy,math,unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
class DiagnosticContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree=ast.parse(Path(__file__).with_name('reconcile_nonoutcome.py').read_text())
        funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('budget_projection','diagnose_c033')]
        def need(ok,code):
            if not ok:raise ValueError(code)
        env={'Counter':Counter,'need':need,'number':lambda v:type(v) in (int,float) and math.isfinite(v)}
        exec(compile(ast.Module(body=funcs,type_ignores=[]),'<diagnostic-under-test>','exec'),env)
        cls.env=env
    def fixture(self,volume):
        d=1736164800000;rows=[{'t':d-300000*j,'available_at':d-300000*j+300000,'open':100.,'high':102.,'low':98.,'close':101.5,'volume':volume} for j in range(13,0,-1)]
        saved={'programme':{'tasks':{'freeze_pressure':{'input':{'candidate':{'parameters':{'volume_pressure':{'symbols':{'A':9},'decision_times_ms':[d]}}}}}}},'progress':{'safe_stop':True,'results':{'original_quotes':{'classification':'NO_ELIGIBLE_EVENTS'},'causal_pressure':{'value':{'intents':[]}},'data_A':{'value':{'asset_id':'a'}}}}}
        cache=SimpleNamespace(assets={'a':{'instrument':'A','partition':'DEVELOPMENT','trust':'AUTHENTICATED_NATIVE_COLLECTION','normalized_sha256':'a'*64}},rows={'a':rows})
        return saved,cache
    def test_zero_volume_does_not_erase_individual_price_condition_counts(self):
        s,c=self.fixture(0);before=copy.deepcopy(s);r,_=self.env['diagnose_c033'](s,c);x=r['symbols'][0]
        self.assertEqual(x['diagnostic_cause'],'VOLUME_ALL_ZERO')
        self.assertEqual(x['condition_counts']['upper_close'],1)
        self.assertEqual(x['condition_counts']['positive_body'],1)
        self.assertEqual(x['condition_counts']['joint_long'],0)
        self.assertEqual(s,before)
    def test_nonzero_constant_is_distinct_from_zero(self):
        s,c=self.fixture(10);r,_=self.env['diagnose_c033'](s,c)
        self.assertEqual(r['symbols'][0]['diagnostic_cause'],'VOLUME_CONSTANT')
        self.assertEqual(r['symbols'][0]['condition_counts']['positive_prior_volume'],1)
    def test_diagnostic_fails_if_sealed_zero_is_contradicted(self):
        s,c=self.fixture(10);c.rows['a'][-1]['volume']=20
        with self.assertRaisesRegex(ValueError,'DIAGNOSTIC_CONTRADICTS_SEALED_ZERO'):self.env['diagnose_c033'](s,c)
    def test_contract_charges_and_existing_reservation_are_distinct_without_refund(self):
        private={'trial_book':{'limits':{'V2':84},'used':{'V2':22},'identities':{'V2:V2-C033':{'units':1,'state':'RESERVED'}}}}
        before=copy.deepcopy(private);r=self.env['budget_projection']({'V2':{'used':21,'result_observations':29}},private)
        self.assertEqual((r['contract_outcome_charged_identities'],r['economic_observations'],r['runtime_legacy_used_including_hold']),(21,29,22))
        self.assertEqual(r['refunds_or_counter_mutations'],0);self.assertIsNone(r['global_universal_budget'])
        self.assertEqual(private,before)
if __name__=='__main__':unittest.main()
