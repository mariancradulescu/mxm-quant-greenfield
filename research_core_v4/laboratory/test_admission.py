"""Accounting fixtures only: no market data, historical replay or economics."""
import unittest
import ast
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
from .admission import TypedTrialBook,bootstrap_typed_book,semantic_hash
from .common import digest,need,number,DEVELOPMENT_END_MS

def fixture():
    legacy={'limits':{'V2':84},'used':{'V2':22},'identities':{'V2:V2-C033':{'spec_hash':'c'*64,'units':1,'state':'RESERVED'}}}
    history={'V2':{'used':21,'result_observations':29,'charged':['opened-'+str(i) for i in range(21)]}}
    return bootstrap_typed_book(history,legacy,[{'id':'unopened','mechanism':'old','universe':['2','1']}])

def policies(book,lane='V2',cap=2,observations=2,programme='p',family='f'):
    if family not in book.families:
        book.register_family({'id':family,'lane':lane,'lane_cap':84 if lane=='V2' else cap,'identity_cap':cap,'observation_cap':observations,
          'decision_sha256':'d'*64,'novelty_justification':'UNIT FIXTURE ONLY; not an actual scientific novelty decision.','selection_history_ref':'fixture','adaptive_exposure':'fixture-known'})
    book.register_programme({'id':programme,'family':family,'lane':lane,'identity_cap':cap,'observation_cap':observations,'manifest_sha256':'a'*64})

def reserve(book,ident='new',lane='V2',programme='p',mechanism='different'):
    c={'id':ident,'mechanism':mechanism,'universe':['1','2']}
    book.reserve(lane,ident,'b'*64,1,candidate=c,programme=programme)

class AdmissionTests(unittest.TestCase):
    def test_baseline_preserved(self):
        b=fixture();self.assertEqual(b.view()['lanes']['V2'],{'limit':84,'outcome_charged':21,'reservation_holds':1,'encumbered':22})
        self.assertEqual(b.view()['economic_observations'],29);self.assertEqual(b.export()['events'],[])
        self.assertEqual(b.export()['baseline']['legacy_snapshot']['used']['V2'],22)
    def test_reservation_is_not_outcome(self):
        b=fixture();policies(b);reserve(b)
        self.assertEqual(b.view()['lanes']['V2']['outcome_charged'],21)
        b.open_outcome('V2','new','b'*64);b.open_outcome('V2','new','b'*64)
        self.assertEqual(b.view()['lanes']['V2']['outcome_charged'],22)
        b.observe('V2','new','b'*64,'task','e'*64)
        self.assertEqual(b.view()['economic_observations'],30)
        self.assertEqual(TypedTrialBook.restore(b.export()).export(),b.export())
    def test_hold_not_refunded_or_reopened(self):
        b=fixture()
        with self.assertRaises(Exception):b.open_outcome('V2','V2-C033','c'*64)
        self.assertEqual(b.view()['refunds'],0)
    def test_no_observation_without_exposure(self):
        b=fixture();policies(b);reserve(b);before=b.export()
        with self.assertRaises(Exception):b.observe('V2','new','b'*64,'task','e'*64)
        self.assertEqual(b.export(),before)
    def test_observation_cap_checked_before_further_exposure(self):
        b=fixture();policies(b,observations=1);reserve(b)
        b.open_outcome('V2','new','b'*64);b.observe('V2','new','b'*64,'first','e'*64)
        with self.assertRaises(Exception):b.open_outcome('V2','new','b'*64)
    def test_duplicate_observation_rejected(self):
        b=fixture();policies(b);reserve(b);b.open_outcome('V2','new','b'*64);b.observe('V2','new','b'*64,'task','e'*64)
        with self.assertRaises(Exception):b.observe('V2','new','b'*64,'task','e'*64)
    def test_shared_family_cap_not_reset_by_programme(self):
        b=fixture();policies(b,cap=1);policies(b,cap=1,programme='renamed');reserve(b)
        with self.assertRaises(Exception):reserve(b,'another',programme='renamed',mechanism='other')
    def test_distinct_lane_has_explicit_finite_cap(self):
        b=fixture();policies(b,lane='DISTINCT_FIXTURE',cap=1);reserve(b,lane='DISTINCT_FIXTURE')
        self.assertEqual(b.view()['lanes']['DISTINCT_FIXTURE']['limit'],1)
        self.assertEqual(b.view()['lanes']['V2']['encumbered'],22)
        self.assertIsNone(b.view()['universal_project_cap'])
        with self.assertRaises(Exception):reserve(b,'another',lane='DISTINCT_FIXTURE',mechanism='other')
    def test_semantic_rename_blocked_across_lanes(self):
        b=fixture();policies(b,lane='DISTINCT_FIXTURE')
        with self.assertRaises(Exception):reserve(b,'renamed',lane='DISTINCT_FIXTURE',mechanism='old')
    def test_same_unopened_identity_not_blanket_rejected(self):
        b=fixture();policies(b);reserve(b,'unopened',mechanism='old')
        self.assertEqual(b.view()['lanes']['V2']['reservation_holds'],2)
    def test_changed_historical_identity_rejected(self):
        b=fixture();policies(b)
        with self.assertRaises(Exception):reserve(b,'unopened',mechanism='changed')
    def test_tampered_journal_and_view_rejected(self):
        b=fixture();policies(b);v=b.export();v['events'][0]['payload']['identity_cap']=10
        with self.assertRaises(Exception):TypedTrialBook.restore(v)
        v=b.export();v['view']['refunds']=1
        with self.assertRaises(Exception):TypedTrialBook.restore(v)
    def test_semantic_hash_ignores_only_identity_metadata_and_universe_order(self):
        self.assertEqual(semantic_hash({'id':'a','universe':['1','2'],'rule':1}),semantic_hash({'id':'b','universe':['2','1'],'rule':1}))
        self.assertNotEqual(semantic_hash({'rule':1}),semantic_hash({'rule':2}))
    def test_family_cap_not_changed_after_registration(self):
        b=fixture();policies(b);before=b.export();p=deepcopy(b.families['f']);p['id']='new-family';p['lane_cap']=85
        with self.assertRaises(Exception):b.register_family(p)
        self.assertEqual(b.export(),before)
    def screen_fixture(self,account,missing_quotes=False,empty=False):
        # Execute the exact production adapter AST with explicitly artificial
        # transport/account/screen stubs. This is not a market observation.
        source=ast.parse(Path(__file__).with_name('science.py').read_text())
        function=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='native_quote_screen')
        calls=[]
        def publish(spec,evidence):
            if evidence['trades']:self.assertEqual(calls,['opened'])
            return {'status':'FIXTURE_ONLY'}
        ns={'DEVELOPMENT_END_MS':DEVELOPMENT_END_MS,'native':SimpleNamespace(graph=lambda x:{},point=lambda q:q,account=lambda *a:account,
              currencies=lambda *a:{'EUR'},route=lambda *a:[]),'screen':publish,'need':need,'number':number,'digest':digest}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'production-science-adapter','exec'),ns)
        intent={'symbol_id':1,'feature_available_ms':0,'decision_ms':0,'entry_ms':1000,'exit_ms':2000,'direction':1}
        quotes=[{'symbol_id':1,'boundary_ms':t,'sides':{s:{'timestamp_ms':t} for s in ('bid','ask')}} for t in (1000,2000)]
        corpus={'all_identity_status':[{'sid':1,'quote':'EUR'}],'catalog':{'full':{'1':{'digits':2}}},'raw_quote_receipts':[] if missing_quotes else quotes}
        ns['native_quote_screen']({}, {'intents':[] if empty else [intent],'missing':[],'feature_asset_sha256':'f'*64},corpus,{'state':'UNRESOLVED'},on_economic_open=lambda:calls.append('opened'))
        return calls
    def test_empty_intents_do_not_open_outcome(self):self.assertEqual(self.screen_fixture({'gross_eur':0},empty=True),[])
    def test_missing_quotes_do_not_open_outcome(self):self.assertEqual(self.screen_fixture({'gross_eur':0},missing_quotes=True),[])
    def test_missing_account_does_not_open_outcome(self):self.assertEqual(self.screen_fixture(None),[])
    def test_supported_gross_opens_even_with_unknown_costs(self):self.assertEqual(self.screen_fixture({'gross_eur':0}),['opened'])

if __name__=='__main__':unittest.main()
