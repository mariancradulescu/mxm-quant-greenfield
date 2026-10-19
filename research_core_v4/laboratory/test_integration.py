"""New integration tests only; no accepted historical campaign is rerun."""
import unittest,json
from pathlib import Path
from copy import deepcopy
from .common import *
from .budgets import historical_accounting,TrialBook
from .data import DataCatalogue,Acquisition
from .programs import Laboratory,validate_manifest
from .economics import screen,replay
from .fixtures import programme,T,economic_fixture,trades
ROOT=Path(__file__).resolve().parents[2]
class IntegratedReception(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.history=historical_accounting(ROOT)
    def lab(self,m=None):return Laboratory(m or programme(),self.history,TrialBook({'RECEPTION':0,'V2':84},{'RECEPTION':0,'V2':21}))
    def finish(self,lab):
        while (k:=lab.next()) is not None:lab.execute(k)
        return lab
    def test_historical_budget_reconciled_without_refund(self):
        h=self.history;self.assertEqual((h['V2']['used'],h['V2']['remaining'],h['V2']['result_observations']),(21,63,29));self.assertIsNone(h['V4']['effective_independent_trial_count'])
    def test_complete_branching_economic_integration_and_cold_resume(self):
        lab=self.lab();lab.execute(lab.next());lab.execute(lab.next())
        # Cold reconstruction between finite segments; no fixture/event replay.
        lab=Laboratory.restore(json.loads(encoded(lab.checkpoint())),self.history);self.finish(lab)
        self.assertEqual(len(lab.state['results']),7);self.assertIn('rejected_followup',lab.state['skipped'])
        r=lab.state['results']['deep_account']['value'];self.assertEqual(r['replay']['terminal_broker_equity_eur'],'202.0');self.assertFalse(r['HARD21']);self.assertEqual(r['entries_per_week']['2025-W03'],0)
        self.assertEqual(lab.book.used['V2'],21);self.assertTrue(lab.state['safe_stop'])
    def test_three_distinct_programme_graphs_without_source_change(self):
        for i,op in enumerate(('normal','negative','missing'),1):
            m=programme('RECEPTION_'+op.upper(),i)
            if op=='negative':m['tasks']['cheap_screen']['input']['evidence']['trades']=trades(-2)
            if op=='missing':m['tasks']['validate_data']['input']['rows']=[]
            lab=self.finish(self.lab(m));self.assertTrue(lab.state['safe_stop']);self.assertIsNone(lab.next())
            if op=='negative':self.assertEqual(lab.state['results']['cheap_screen']['classification'],'GROSS_EDGE_FAIL');self.assertIn('rejected_followup',lab.state['results'])
            if op=='missing':self.assertNotIn('cheap_screen',lab.state['results'])
    def test_unknown_cost_is_not_zero_or_a_loss(self):
        m=programme();e=m['tasks']['cheap_screen']['input']['evidence'];e['trades'][0]['costs']['funding']=None
        lab=self.finish(self.lab(m));r=lab.state['results']['cheap_screen']['value'];self.assertEqual(r['status'],'COST_UNRESOLVED');self.assertEqual(r['metrics']['coarse_net_pnl']['state'],'UNAVAILABLE');self.assertNotIn('deep_account',lab.state['results'])
    def test_budget_exhausted_and_duplicate_identity(self):
        b=TrialBook({'V2':1});b.reserve('V2','a','a'*64,1)
        with self.assertRaisesRegex(LabError,'DUPLICATE'):b.reserve('V2','a','a'*64,1)
        with self.assertRaisesRegex(LabError,'BUDGET_EXHAUSTED'):b.reserve('V2','b','b'*64,1)
    def test_invalid_candidate_before_execution(self):
        m=programme();del m['tasks']['admit_candidate']['input']['candidate']['position_admission_policy']
        with self.assertRaises(ValueError):self.lab(m)
    def test_duplicate_execution_and_unsafe_resume(self):
        l=self.lab();k=l.next();l.execute(k)
        with self.assertRaisesRegex(LabError,'DUPLICATE_OR_INADMISSIBLE'):l.execute(k)
        cp=l.checkpoint();cp['progress']['pending']={'task':'admit_candidate'}
        with self.assertRaisesRegex(LabError,'UNSAFE_PENDING_RESUME'):Laboratory.restore(cp,self.history)
    def test_changed_result_manifest_and_cache_fail_closed(self):
        l=self.lab();l.execute(l.next());cp=l.checkpoint();cp['progress']['results']['validate_data']['classification']='FAKE'
        with self.assertRaisesRegex(LabError,'CHECKPOINT_RESULT_CHANGED'):Laboratory.restore(cp,self.history)
        cp=l.checkpoint();cp['programme']['version']=2
        with self.assertRaisesRegex(LabError,'CHECKPOINT_MANIFEST_CHANGED'):Laboratory.restore(cp,self.history)
        cp=l.checkpoint();ident=next(iter(cp['catalogue']['rows']));cp['catalogue']['rows'][ident][0]['close']=88
        with self.assertRaisesRegex(LabError,'CACHE_CHANGED'):Laboratory.restore(cp,self.history)
    def test_data_quality_dedup_conflict_and_causality(self):
        x=programme()['tasks']['validate_data']['input'];c=DataCatalogue();i=c.ingest(x['manifest'],x['rows']*2)
        self.assertEqual(c.assets[i]['row_count'],1);self.assertEqual(c.view(i,T-1),[])
        bad=deepcopy(x['rows'][0]);bad['close']=100.5;i=c.ingest(x['manifest'],x['rows']+[bad]);self.assertEqual(c.assets[i]['conflicts'],1);self.assertEqual(c.assets[i]['row_count'],0)
        future=deepcopy(x['manifest']);future['partition']='PROTECTED';i=c.ingest(future,x['rows'])
        with self.assertRaisesRegex(LabError,'PROTECTED_READ_GATE'):c.view(i,T)
    def test_acquisition_cache_first_and_bounded_whitelist(self):
        x=programme()['tasks']['validate_data']['input'];c=DataCatalogue();c.ingest(x['manifest'],x['rows'],trust='AUTHENTICATED_NATIVE_CUSTODY')
        p={'provider':'PEPPERSTONE_OPEN_API','partition':'DEVELOPMENT','read_only':True,'automatic_retries':0,'instrument':'SYNTHETIC','kind':'M5','start_ms':T-300000,'end_ms':T,'max_pages':3}
        a=Acquisition(c,None,{'M5':0});self.assertEqual(a.request(p)['state'],'CACHE_REUSED')
        p['start_ms']-=300000
        with self.assertRaisesRegex(LabError,'ACQUISITION_BUDGET'):a.request(p)
        p['kind']='ORDER'
        with self.assertRaisesRegex(LabError,'ACQUISITION_SCOPE'):a.request(p)
    def test_future_information_and_missing_deep_cost(self):
        l=self.lab();l.execute(l.next());l.execute(l.next());s=l.state['results']['admit_candidate']['value'];e=deepcopy(l.m['tasks']['cheap_screen']['input']['evidence']);e['trades'][0]['feature_available_ms']=T+1
        with self.assertRaisesRegex(LabError,'FUTURE_INFORMATION'):screen(s,e)
        s,e=economic_fixture();e['events'][0]['metadata']['cost_components_eur']['commission']=None
        with self.assertRaisesRegex(LabError,'REPLAY_MISSING_COST'):replay(s,e)
    def test_cycles_invalid_operator_and_post_outcome_tuning(self):
        for change in ('cycle','operator','identity'):
            m=programme()
            if change=='cycle':m['tasks']['validate_data']['dependencies']=['programme_report']
            if change=='operator':m['tasks']['validate_data']['operator']='shell'
            if change=='identity':m['tasks']['admit_candidate']['input']['candidate']['provenance']['programme']='OTHER'
            with self.assertRaises(ValueError):self.lab(m)
    def test_general_causal_dsl_cross_symbol_and_temporal_features(self):
        from .science import causal_intents,expression
        l=self.lab();l.execute(l.next());asset=l.state['results']['validate_data']['value']['asset_id']
        c=l.m['tasks']['admit_candidate']['input']['candidate'];c['parameters']['causal_dsl']={
          'entry_delay_ms':1000,'hold_ms':60000,'trade_symbol_id':9999,'decision_times_ms':[T-1,T],
          'features':[{'name':'a','asset':'left','field':'close','lag':0},{'name':'b','asset':'right','field':'close','lag':0}],
          'direction_expression':{'mul':[{'gt':[{'feature':'utc_hour'},0]},{'div':[{'feature':'a'},{'feature':'b'}]}]}}
        out=causal_intents(c,l.cache,{'left':asset,'right':asset});self.assertEqual(len(out['intents']),1);self.assertEqual(len(out['missing']),1)
        self.assertLessEqual(out['intents'][0]['feature_available_ms'],T)
        with self.assertRaisesRegex(LabError,'FEATURE_OPERATOR'):expression({'eval':['x']},{})
    def test_native_cost_adapter_unknown_terms_and_missing_exit(self):
        from .science import native_quote_screen
        from discovery.engine import DiscoveryEngine
        l=self.lab();c=DiscoveryEngine().freeze_candidate(l.m['tasks']['admit_candidate']['input']['candidate'])
        def q(t,bid,ask):return {'symbol_id':9999,'boundary_ms':t,'sides':{side:{'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':t,'price':price,'age_ms':0,'source_has_more':False} for side,price in [('bid',bid),('ask',ask)]}}
        corpus={'all_identity_status':[{'sid':9999,'class':'SYNTHETIC_FOREX','base':'EUR','quote':'EUR','min_units':1,'reasons':[]}],
          'catalog':{'full':{'9999':{'commissionType':4,'preciseTradingCommissionRate':0,'lotSize':100,'preciseMinCommission':0,'minCommissionType':2,'pnlConversionFeeRate':0}}},
          'raw_quote_receipts':[q(T+1000,100,101),q(T+61000,102,103)]}
        g={'intents':[{'decision_ms':T,'feature_available_ms':T,'entry_ms':T+1000,'exit_ms':T+61000,'direction':1,'symbol_id':9999}],
          'missing':[],'feature_asset_sha256':digest('synthetic')}
        r=native_quote_screen(c,g,corpus,{'state':'UNRESOLVED'});self.assertEqual(r['classification'],'COST_UNRESOLVED');self.assertEqual(r['result']['metrics']['coarse_net_pnl']['state'],'UNAVAILABLE')
        corpus['raw_quote_receipts'].pop();r=native_quote_screen(c,g,corpus,{'state':'UNRESOLVED'});self.assertEqual(r['classification'],'DATA_INSUFFICIENT')
    def test_frozen_account_sizing_and_common_factor_contention(self):
        s,e=economic_fixture();s['sizing_policy']={'frozen':True,'increase_after_loss':False,'maximum_equity_risk_fraction':.01,
          'free_margin_reserve_fraction':0.,'common_factor_limits_fraction':{'shared':.01}}
        entry=e['events'][0]
        entry['metadata']['certified_volume_options']=[{'volume_cents':v,'causally_available_at_ms':T,'source_sha256':digest('synthetic_ladder'),
          'margin_eur':v/5,'entry_cost_eur':0.,'worst_case_loss_eur':v/100,'expected_net_eur':v/50,'risk_exposures_eur':{'shared':v/100}} for v in (100,200)]
        e['events'][-1]['metadata']['exit_cost_by_volume_cents']={'100':0.,'200':0.}
        other=deepcopy(e['events']);
        for row in other:row['position_id']='p2';row['priority']=200
        e['events']+=other;r=replay(s,e)
        self.assertEqual(r['replay']['accepted_entries'],1);self.assertEqual(r['replay']['rejected_entries'],1)
        self.assertEqual(r['replay']['terminal_broker_equity_eur'],'204.0')
        self.assertIn('REJECT_NO_SAFE_EXECUTABLE_VOLUME',[d['reason'] for d in r['replay']['decisions']])
    def test_gap_lags_are_not_compressed(self):
        from .science import causal_intents
        m=programme();x=m['tasks']['validate_data']['input'];x['manifest']['start_ms']-=600000
        old=deepcopy(x['rows'][0]);old['t']-=600000;old['available_at']-=600000;x['rows'].insert(0,old)
        l=self.lab(m);l.execute(l.next());asset=l.state['results']['validate_data']['value']['asset_id'];c=deepcopy(l.m['tasks']['admit_candidate']['input']['candidate'])
        c['parameters']['causal_dsl']={'entry_delay_ms':1000,'hold_ms':60000,'trade_symbol_id':9999,'decision_times_ms':[T],
          'features':[{'name':'lag','asset':'x','field':'close','lag':1}],'direction_expression':{'feature':'lag'}}
        self.assertTrue(causal_intents(c,l.cache,{'x':asset})['missing'])
    def test_durable_intent_blocks_new_push_retry_until_recovery(self):
        from .claim import claim_state
        state={'pending':None,'safe_stop':True,'sequence':4,'admission_sha256':'old'}
        claim=claim_state(state,100,'new','a'*40,'b'*40)
        self.assertEqual(claim['sequence'],4);self.assertFalse(claim['pending']['automatic_retry'])
        with self.assertRaisesRegex(LabError,'PENDING_SEGMENT_REQUIRES_RECOVERY'):claim_state(claim,101,'new','c'*40,'b'*40)
        with self.assertRaisesRegex(LabError,'PROGRAMME_ALREADY_STOPPED'):claim_state(state,100,'old','a'*40,'b'*40)
    def test_partial_day_interval_includes_next_iso_week(self):
        s,e=economic_fixture();s['evaluation_start']='2025-01-05T23:30:00Z';s['evaluation_end']='2025-01-06T12:02:00Z'
        r=replay(s,e);self.assertEqual(set(r['entries_per_week']),{'2025-W01','2025-W02'});self.assertEqual(r['entries_per_week']['2025-W01'],0)
    def test_native_quote_path_into_shared_account_and_unresolved_gates(self):
        from .science import native_replay
        from discovery.engine import DiscoveryEngine
        m=programme();c=DiscoveryEngine().freeze_candidate(m['tasks']['admit_candidate']['input']['candidate'])
        def q(t,bid,ask):return {'symbol_id':9999,'boundary_ms':t,'sides':{side:{'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':t,'price':price,'age_ms':0,'source_has_more':False} for side,price in [('bid',bid),('ask',ask)]}}
        intent={'decision_ms':T,'feature_available_ms':T,'entry_ms':T+1000,'exit_ms':T+61000,'direction':1,'symbol_id':9999}
        g={'intents':[intent],'missing':[]};corpus={'all_identity_status':[{'sid':9999,'symbol':'SYNTHETIC','class':'SYNTHETIC_FOREX','base':'EUR','quote':'EUR','reasons':[]}],
          'raw_quote_receipts':[q(T+1000,100,101),q(T+31000,100.5,101.5),q(T+61000,102,103)]}
        costs={'spread':0.,'commission':.1,'slippage':0.,'funding':0.,'fx_conversion':0.}
        terms={'volume_cents':100,'min_volume_cents':100,'step_volume_cents':100,'max_volume_cents':10000,'margin_eur':20.,
          'entry_cost_components_eur':costs,'exit_cost_components_eur':costs,'financing_cashflows':[{'timestamp_ms':T+31000,'amount_eur':-.05,'source_sha256':'a'*64}],
          'source_sha256':'a'*64,'effective_start_ms':T,'effective_end_ms':T+100000}
        authority={'screen_status':'DISCOVERY_SURVIVOR','cost_state':'CONSERVATIVE_BOUND','prospectively_frozen':True,'source_sha256':'b'*64,
          'current_snapshot_is_historical':False,'by_intent':{digest(intent):terms},'mark_interval_ms':30000}
        spec,_=economic_fixture();spec['price_cost_convention']='BID_ASK_PLUS_NONSPREAD_COSTS'
        out=native_replay(c,g,corpus,authority,spec);self.assertEqual(out['result']['replay']['terminal_broker_equity_eur'],'200.75')
        corpus['raw_quote_receipts'].pop();self.assertEqual(native_replay(c,g,corpus,authority,spec)['classification'],'DATA_INSUFFICIENT')
        authority['cost_state']='UNRESOLVED';self.assertEqual(native_replay(c,g,corpus,authority,spec)['classification'],'COST_UNRESOLVED')
    def test_screen_reporting_and_broker_metadata_are_bound(self):
        l=self.lab();l.execute(l.next());l.execute(l.next());r=l.execute(l.next())['value']
        self.assertEqual(r['metrics']['hold_duration']['mean_seconds'],60.)
        self.assertEqual(r['metrics']['exposure']['value'],60.)
        l.authentic_corpus={'catalog':{'full':{'9':{'digits':5}}}}
        self.assertEqual(l.resolve({'native_acquisition_plan':{'symbol_id':9,'digits':3}})['digits'],5)
    def test_rejected_position_has_no_simulated_financing_charge(self):
        s,e=economic_fixture();e['events'][0]['margin_eur']=300
        e['events'].append({'timestamp_utc':'2025-01-06T12:00:30Z','kind':'FINANCING','position_id':'p1','candidate_id':'V2-C990001','symbol':'SYNTHETIC',
          'causal_state':True,'financing_eur':-99,'metadata':{'source_sha256':'a'*64,'available_at_ms':T}})
        r=replay(s,e);self.assertEqual(r['replay']['terminal_broker_equity_eur'],'200');self.assertEqual(r['replay']['financing_eur'],'0')
    def test_chunked_atomic_ciphertext_and_corrupt_part(self):
        from .custody import chunk_ciphertext,restore_ciphertext
        blob=b'SYNTHETIC_ENCRYPTED_ENVELOPE_TEST'*30000;files,m=chunk_ciphertext(blob,'segments/test')
        self.assertGreater(len(m['parts']),1);self.assertEqual(restore_ciphertext(m,files.__getitem__),blob)
        files[m['parts'][0]['path']]=b'Y29ycnVwdA=='
        with self.assertRaisesRegex(LabError,'CIPHER_PART_CHANGED'):restore_ciphertext(m,files.__getitem__)
    def test_synthetic_catalogue_never_satisfies_native_cache(self):
        x=programme()['tasks']['validate_data']['input'];c=DataCatalogue();c.ingest(x['manifest'],x['rows'])
        self.assertTrue(c.query('SYNTHETIC','M5',T-300000,T))
        self.assertEqual(c.query('SYNTHETIC','M5',T-300000,T,authentic_only=True),[])
    def test_reception_assertions_block_false_success(self):
        m=programme();m['acceptance']={'deep_account':{'classification':'SUPPORTED_FOR_ROBUSTNESS','value_equal':{'replay.terminal_broker_equity_eur':'202.0','HARD21':False}}}
        l=self.finish(self.lab(m));l.checkpoint()
        m['acceptance']['deep_account']['value_equal']['replay.terminal_broker_equity_eur']='999.0'
        l=self.finish(self.lab(m))
        with self.assertRaisesRegex(LabError,'RECEPTION_KNOWN_ANSWER'):l.checkpoint()
if __name__=='__main__':unittest.main()
