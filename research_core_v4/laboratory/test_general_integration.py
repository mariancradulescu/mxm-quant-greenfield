"""Isolated artificial integration fixtures. Never a canonical economic opening."""
import ast,sys,types,unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from .common import digest,need,number
from .admission import TypedTrialBook,semantic_hash
from .test_admission import fixture
from .execution import bind_native,preserve_node
from .programs import Laboratory,AUTHORITY
from .protocol import economic_gate,recovered_public_base

def upgraded_fixture():
    b=fixture();b._append('FINGERPRINT_INDEX_UPGRADED',{'previous_index_sha256':digest(b.semantic_registry),'identity_semantics':dict(b.baseline['identity_semantics']),'source_spec_hashes':{k:'a'*64 for k in b.baseline['identity_semantics']},'source_sha':'b'*40});return b

class GeneralIntegrationTests(unittest.TestCase):
    def test_rationale_and_identity_labels_cannot_avoid_causal_fingerprint(self):
        a={'id':'V2-C997','mechanism':'ARTIFICIAL','rationale':'A'};b={**a,'id':'V2-C998','rationale':'B'}
        self.assertNotEqual(semantic_hash(a),semantic_hash(b));self.assertEqual(semantic_hash(a,2),semantic_hash(b,2))
    def test_index_upgrade_preserves_legacy_and_roundtrips(self):
        b=upgraded_fixture();self.assertEqual(b.view()['lanes']['V2']['outcome_charged'],21);self.assertEqual(b.view()['lanes']['V2']['reservation_holds'],1)
        self.assertEqual(b.view()['economic_observations'],29);self.assertEqual(b.baseline['legacy_snapshot']['used']['V2'],22);self.assertEqual(TypedTrialBook.restore(b.export()).export(),b.export())
    def test_cosmetic_rationale_rename_cannot_reserve_an_extra_identity(self):
        from .test_admission import policies
        b=upgraded_fixture();policies(b);before=b.export()
        with self.assertRaises(Exception):b.reserve('V2','cosmetic','a'*64,1,candidate={'id':'cosmetic','mechanism':'old','universe':['1','2'],'rationale':'Changed narrative only'},programme='p')
        self.assertEqual(b.export(),before)
    def test_gate_rejects_missing_reception_or_unprotected_control_plane(self):
        source='a'*40;protected={'main':True,'mxm-remediation-p0-p4-20261015-v1':True};good={'status':'END_TO_END_OPERATIONAL_ACCEPTED','source_sha':source}
        economic_gate(good,source,protected)
        for g,p in (({'status':'BLOCKED','source_sha':source},protected),(good,{**protected,'main':False}),({**good,'source_sha':'b'*40},protected)):
            with self.assertRaises(Exception):economic_gate(g,source,p)
    def test_recovered_new_admission_preserves_closed_predecessor_and_identity(self):
        base={'pending':None,'safe_stop':True,'sequence':19,'ciphertext_sha256':'a'*64,'admission_ref':'OLD'}
        intent={'base_state':base,'pending':{'run_id':7},'preflight':{'admission_ref':'NEW','admission_path':'NEW_PATH','admission_sha256':'b'*64}}
        recovered=recovered_public_base(intent);self.assertEqual(recovered['sequence'],19);self.assertEqual(recovered['ciphertext_sha256'],base['ciphertext_sha256']);self.assertTrue(recovered['safe_stop']);self.assertEqual(recovered['recovery_continuation']['admission_ref'],'NEW');self.assertNotIn('recovery_continuation',base)
    def setup_lab(self):
        from discovery.schema import CANDIDATE_REQUIRED_FIELDS
        c={k:{} for k in CANDIDATE_REQUIRED_FIELDS};c.update(id='V2-C999',mechanism='ARTIFICIAL_CALLBACK_FIXTURE_ONLY',rationale='No economic interpretation',universe=['FIXTURE'],features=[],lookbacks=[],filters=[],parameters={},cost_state={'state':'UNRESOLVED'},position_admission_policy={'fixture':True},stage_a_economic_unit={'fixture':True},provenance={'programme':'GENERAL_FIXTURE','prospective_at_ms':1})
        m={'schema':'mxm.laboratory-program.v2','id':'GENERAL_FIXTURE','version':1,'authority':AUTHORITY,'partition':'DEVELOPMENT','orders':0,'mode':'DEVELOPMENT_RESEARCH','economic_lane':'DISTINCT_FIXTURE','family_id':'FIXTURE_FAMILY','budget':{'steps':2,'broker_requests':0,'new_identities':1},'prospective_at_ms':1,'provenance':{'fixture_only':True},'source_sha256':'f'*64,
          'tasks':{'freeze':{'operator':'freeze','priority':1,'trial_units':1,'dependencies':[],'input':{'candidate':c}},'screen':{'operator':'native_screen','priority':2,'trial_units':0,'dependencies':['freeze'],'input':{'candidate':{'result_of':'freeze'},'generated':{'intents':[{'symbol_id':1,'entry_ms':1000,'exit_ms':2000,'direction':1}],'missing':[],'feature_asset_sha256':'e'*64},'corpus':{'bound_authentic_corpus':True},'terms_authority':{'state':'UNRESOLVED'}}}}}
        b=upgraded_fixture();b.register_family({'id':'FIXTURE_FAMILY','lane':'DISTINCT_FIXTURE','lane_cap':1,'identity_cap':1,'observation_cap':1,'decision_sha256':'d'*64,'novelty_justification':'Explicit artificial unit fixture; not a real programme or market outcome.','selection_history_ref':'fixture-only','adaptive_exposure':'fixture-only'})
        b.register_programme({'id':m['id'],'family':'FIXTURE_FAMILY','lane':'DISTINCT_FIXTURE','identity_cap':1,'observation_cap':1,'manifest_sha256':digest(m)})
        return Laboratory(m,{'reconciled':True,'V2':{'charged':[]}},b)
    def test_actual_freeze_native_callback_checkpoint_chain(self):
        lab=self.setup_lab();lab.execute(lab.next());self.assertFalse(lab.book.items['DISTINCT_FIXTURE:V2-C999']['opened'])
        corpus={'all_identity_status':[{'sid':1}],'catalog':{'full':{'1':{'digits':2}}},'raw_quote_receipts':[{'symbol_id':1,'boundary_ms':1000},{'symbol_id':1,'boundary_ms':2000}]}
        lazy=bind_native(lab,corpus);self.assertIsNone(lazy.instance)
        tree=ast.parse(Path(__file__).with_name('science.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='native_quote_screen')
        env={'need':need,'digest':digest,'number':number,'native':types.SimpleNamespace(graph=lambda x:{},point=lambda x:x,account=lambda *a:{'gross_eur':0}), 'screen':lambda *a:{'status':'COST_UNRESOLVED'}}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<exact-production-screen-with-artificial-dependencies>','exec'),env)
        module=types.ModuleType('research_core_v4.laboratory.science');module.native_quote_screen=env['native_quote_screen']
        with patch.dict(sys.modules,{'research_core_v4.laboratory.science':module}):lab.execute(lab.next())
        self.assertIsNone(lab.next());view=lab.book.view();self.assertEqual(view['lanes']['DISTINCT_FIXTURE']['outcome_charged'],1);self.assertEqual(view['economic_observations'],30)
        restored=Laboratory.restore(lab.checkpoint(),lab.history);self.assertEqual(restored.book.view(),view);self.assertIsNone(lazy.instance);self.assertEqual(len(corpus['raw_quote_receipts']),2)
    def test_binding_keeps_reserved_resource_budget_and_original_corpus(self):
        lab=self.setup_lab();lab.acquisition.budget={'M5':3,'H1':0,'BID_ASK':2};lab.acquisition.remaining=4;lab.acquisition.receipts=[{'quote_point':{'fixture':True}}];source={'raw_quote_receipts':[]}
        lazy=bind_native(lab,source);self.assertEqual(lazy.caps,{'M5':3,'H1':0,'BID_ASK':2});self.assertEqual(lab.acquisition.remaining,4);self.assertEqual(source,{'raw_quote_receipts':[]});self.assertEqual(lab.authentic_corpus['raw_quote_receipts'],[{'fixture':True}])
    def test_shared_cache_and_remaining_survive_checkpoint(self):
        lab=self.setup_lab();lab.acquisition.remaining=0;private={'programmes':{},'shared_catalogue':None};preserve_node(private,lab)
        self.assertEqual(private['shared_catalogue'],lab.cache.export());self.assertEqual(Laboratory.restore(private['programmes'][lab.m['id']],lab.history).acquisition.remaining,0)

if __name__=='__main__':unittest.main()
