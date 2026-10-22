"""Adversarial regressions from the two independent R3 audits; no market work."""
import unittest
from copy import deepcopy
from dataclasses import replace
from .common import LabError,digest
from .data import DataCatalogue
from . import test_cold_producer_v3 as cold_fixture
from competition.continuous_account_replay_v2 import CapitalEvent,ReplayContractError,replay_continuous_account

class OwnerAuditRegressions(unittest.TestCase):
    def cache(self,rows):
        c=DataCatalogue();m={'instrument':'EURUSD','resolution':'BID_ASK',
          'partition':'DEVELOPMENT','start_ms':60000,'end_ms':120000,
          'source':'PEPPERSTONE_TEST_ONLY','source_sha256':'a'*64,
          'available_at_ms':120000,'session_semantics':'TEST',
          'completeness':'CONFIRMED_COMPLETE','account_scope':'TEST'}
        c.ingest(m,rows,trust='AUTHENTICATED_NATIVE_COLLECTION');return c
    def test_A01_empty_not_usable(self):
        self.assertEqual(self.cache([]).query('EURUSD','BID_ASK',60000,120000,authentic_only=True),[])
    def test_A02_unilateral_not_usable(self):
        for side in ('bid','ask'):
            with self.subTest(side=side):
                c=self.cache([{'t':60001,'side':side,'price':1.1}])
                self.assertEqual(c.query('EURUSD','BID_ASK',60000,120000,authentic_only=True),[])
    def test_A02_async_not_fabricated_and_crossed_rejected(self):
        rows=[{'t':60001,'side':'bid','price':1.1},{'t':60002,'side':'ask','price':1.2}]
        c=self.cache(rows);self.assertEqual(len(next(iter(c.rows.values()))),2)
        rows[1]['price']=1.0;c=self.cache(rows)
        self.assertEqual(c.query('EURUSD','BID_ASK',60000,120000,authentic_only=True),[])
    def test_A04_hold_is_not_complete(self):
        f=cold_fixture.ColdV3ProducerTests();p,s,a=f.fixture()
        p['programmes'][a['programmes'][1]['id']]['progress']['stop_reason']='NO_ADMISSIBLE_CONTINUATION'
        with self.assertRaises(LabError):f.attest(p,s,a)
    def test_A05_truncated_journal(self):
        f=cold_fixture.ColdV3ProducerTests();p,s,a=f.fixture();p['programme_execution_history'].pop()
        with self.assertRaises(LabError):f.attest(p,s,a)
    def replay(self,events):
        return replay_continuous_account(events,starting_equity_eur=200,account_type='HEDGED',total_margin_calculation_type='SUM')
    def position_events(self):
        e=CapitalEvent('2025-01-06T12:00:00Z','ENTRY','C','EURUSD','P',direction='LONG',
            direction_feasibility='EUR200_MIN_VOLUME_FEASIBLE',volume_cents=100,min_volume_cents=100,
            step_volume_cents=100,max_volume_cents=100,margin_eur=20,price=1,base_units=1,quote_to_eur_rate=1)
        f=CapitalEvent('2025-01-06T12:01:00Z','FINANCING','C','EURUSD','P',financing_eur=2)
        x=replace(e,kind='EXIT',timestamp_utc='2025-01-06T12:02:00Z')
        return e,f,x
    def test_A06_orphan_closed_mismatch_duplicate(self):
        e,f,x=self.position_events()
        for events in ([f],[e,x,replace(f,timestamp_utc='2025-01-06T12:03:00Z')],
                       [e,replace(f,candidate_id='OTHER'),x],[e,f,f,x],
                       [e,replace(f,symbol='OTHER'),x]):
            with self.subTest(events=events),self.assertRaises(ReplayContractError):self.replay(events)
    def test_A06_valid_positive_negative_conservation(self):
        e,f,x=self.position_events()
        for amount in (2,-2):
            r=self.replay([e,replace(f,financing_eur=amount),x])
            self.assertEqual(r.financing_eur,amount)
            self.assertEqual(r.terminal_broker_equity_eur,200+amount)
    def test_A07_adapter_rejects_future_signal_before_economic_open(self):
        from .fixtures import native_path_fixture,candidate
        from .science import native_replay
        generated,corpus,authority,_,spec=native_path_fixture()
        old=deepcopy(generated['intents'][0]);bad=generated['intents'][0]
        bad.update(decision_ms=bad['exit_ms']+30000,feature_available_ms=bad['exit_ms']+60000)
        authority['by_intent'][digest(bad)]=authority['by_intent'].pop(digest(old))
        opened=[]
        with self.assertRaises(LabError):native_replay(candidate('V2-C999','TEST'),generated,corpus,authority,spec,lambda:opened.append(1))
        self.assertEqual(opened,[])
    def test_A03_forged_winner_not_certified(self):
        from .test_native_acceptance_v3 import make_fixture,RUN,SOURCE
        from .attest_v3 import validate_negative_artifact
        import json
        from .test_native_acceptance_v3 import HEAD
        route,gate,paths=make_fixture()
        state=json.loads(route.storage[('typed-successor/program-state.json',HEAD)])
        negative=json.loads(route.storage[(paths['negative'],HEAD)])
        negative['concurrent_writers'][0]['oid']='NOT_A_REAL_COMMIT'
        with self.assertRaises((LabError,KeyError)):validate_negative_artifact(route,negative,RUN,SOURCE,state)
    def test_A03_mutated_cas_facts_and_native_logs(self):
        import json
        from .test_native_acceptance_v3 import make_fixture,RUN,SOURCE,HEAD
        from .attest_v3 import validate_negative_artifact
        for mutation in ('parent','observed','candidate','refusal','payload','log'):
            route,gate,paths=make_fixture()
            state=json.loads(route.storage[('typed-successor/program-state.json',HEAD)])
            proof=json.loads(route.storage[(paths['negative'],HEAD)])
            if mutation=='parent':proof['concurrent_writers'][1]['expected_oid']='1'*40
            if mutation=='observed':proof['concurrent_writers'][1]['observed_oid']='1'*40
            if mutation=='candidate':proof['concurrent_writers'][1]['candidate_oid']='7'*40
            if mutation=='refusal':proof['concurrent_writers'][1]['reason']='NETWORK_FAILURE'
            if mutation=='payload':route.storage[('typed-successor/fault-probes/'+str(RUN)+'/A.json','7'*40)]=b'{}'
            if mutation=='log':route.cas_writers[1]['reason']='AUTH_FAILURE'
            with self.subTest(mutation=mutation),self.assertRaises(LabError):validate_negative_artifact(route,proof,RUN,SOURCE,state)
    def test_A05_reordered_rechained_duplicate_and_orphan_events(self):
        for mutation in ('reordered','duplicate','extra'):
            f=cold_fixture.ColdV3ProducerTests();p,s,a=f.fixture();events=p['programme_execution_history']
            if mutation=='reordered':events.reverse()
            elif mutation=='duplicate':events.append(deepcopy(events[-1]))
            else:events[-1]['task']='ORPHAN'
            previous=None
            for e in events:
                e['previous_event_sha256']=previous;e['event_sha256']=digest({k:v for k,v in e.items() if k!='event_sha256'});previous=e['event_sha256']
            with self.subTest(mutation=mutation),self.assertRaises((LabError,KeyError)):f.attest(p,s,a)
    def test_A07_engine_independently_rejects_clocks(self):
        from .fixtures import economic_fixture
        from .economics import replay
        for mutation in ('feature','decision','quote','fx','missing','changed_exit'):
            s,e=economic_fixture();entry=e['events'][0];m=entry['metadata'];p=m['signal_provenance']
            if mutation=='feature':p['feature_available_ms']=p['entry_ms']
            if mutation=='decision':p['decision_ms']=p['entry_ms']
            if mutation=='quote':m['quote_available_at_ms']=p['entry_ms']+1
            if mutation=='fx':m['fx_available_at_ms']=p['entry_ms']+1
            if mutation=='missing':m.pop('signal_provenance')
            if mutation=='changed_exit':e['events'][-1]['metadata']['signal_provenance']['exit_ms']+=1000
            with self.subTest(mutation=mutation),self.assertRaises(ReplayContractError):replay(s,e)
    def test_A07_adapter_rejects_late_quote(self):
        from .fixtures import native_path_fixture,candidate
        from .science import native_replay
        generated,corpus,authority,_,spec=native_path_fixture()
        side=corpus['raw_quote_receipts'][0]['sides']['ask'];side['available_at_ms']=side['timestamp_ms']+1
        opened=[]
        with self.assertRaises(LabError):native_replay(candidate('V2-C999','TEST'),generated,corpus,authority,spec,lambda:opened.append(1))
        self.assertEqual(opened,[])
    def test_DAT01_preserves_same_millisecond_side_revisions(self):
        c=self.cache([{'t':60001,'side':'bid','price':1.1},{'t':60001,'side':'bid','price':1.11},
                      {'t':60002,'side':'ask','price':1.2}])
        m=next(iter(c.assets.values()));self.assertEqual(m['conflicts'],0);self.assertEqual(m['row_count'],3)
        self.assertEqual([r['price'] for r in next(iter(c.rows.values())) if r['side']=='bid'],[1.1,1.11])
    def test_DAT02_trust_mutation_rejected_on_restore(self):
        c=self.cache([{'t':60001,'side':'bid','price':1.1}]);v=c.export()
        next(iter(v['assets'].values()))['trust']='AUTHENTICATED_NATIVE_CUSTODY'
        with self.assertRaisesRegex(LabError,'CACHE_MANIFEST_CHANGED'):DataCatalogue.restore(v)
    def test_SEC04_additive_rule_and_timestamp_changes_allowed(self):
        from .runtime import source_admission
        rule={'id':25222248,'enforcement':'active','conditions':{'ref_name':{'include':['refs/heads/mxm-o04-*'],'exclude':[]}},
              'rules':[{'type':r} for r in ('deletion','non_fast_forward','required_linear_history','update')],
              'updated_at':'2099-01-01T00:00:00Z','bypass_actors':[]}
        source_admission('a'*40,'a'*40,'a'*40,rule)
        rule['rules'].pop(0)
        with self.assertRaises(LabError):source_admission('a'*40,'a'*40,'a'*40,rule)
    def test_REC01_retry_requires_independent_preclaim_failure(self):
        from .handoff_recovery import inspect_dispatch,WORKFLOW,BRANCH
        record={'schema':'mxm.native-dispatch-intent.v3','issued_at_unix':1000,'retry_budget':1,'automatic_post_retry':True}
        r={'id':9,'path':WORKFLOW,'head_branch':BRANCH,'display_title':'MXM P0 '+'a'*40,'status':'completed','conclusion':'failure'}
        self.assertEqual(inspect_dispatch(record,'a'*40,[r],3000),'RUN_OBSERVED_NO_REISSUE')
        for conclusion in ('failure','cancelled','timed_out'):
            r['conclusion']=conclusion
            self.assertEqual(inspect_dispatch(record,'a'*40,[r],3000,preclaim_failed_run_ids=[9]),'REISSUE_AFTER_ATOMIC_STALE_PARENT_INVALIDATION')
    def test_REC04_missing_protocol_refuses_before_network(self):
        from unittest.mock import patch
        from . import claim,publish,runtime
        for module in (claim,publish,runtime):
            with patch.dict('os.environ',{},clear=True),self.assertRaisesRegex(LabError,'EXPLICIT_INTEGRATED_PROTOCOL_REQUIRED'):module.main()
    def test_SEC03_forward_commit_rollback_or_receipt_tamper_refused(self):
        from .integrated import verify_monotone_checkpoint
        from unittest.mock import patch
        from .common import encoded
        state={'sequence':20,'source_sha':'a'*40,'ciphertext_sha256':'b'*64,'accounting':{'refunds':0}}
        class Route:
            maximum=20
            def json(self,path):
                if path=='git/commits/HEAD':return {'tree':{'sha':'ROOT'}}
                if path=='git/trees/ROOT':return {'tree':[{'path':'typed-successor','type':'tree','sha':'TYPED'}]}
                if path=='git/trees/TYPED':return {'tree':[{'path':'segments','type':'tree','sha':'SEGMENTS'}]}
                if path=='git/trees/SEGMENTS':return {'tree':[{'path':str(n),'type':'tree'} for n in range(17,self.maximum+1)]}
                raise KeyError(path)
        route=Route();receipt={**state,'accounting_after':state['accounting']}
        def fetch(*args):return encoded(receipt)
        with patch('research_core_v4.laboratory.integrated.file_at',fetch):
            verify_monotone_checkpoint(route,'HEAD',state)
            route.maximum=21
            with self.assertRaisesRegex(LabError,'CHECKPOINT_ROLLBACK'):verify_monotone_checkpoint(route,'HEAD',state)
            route.maximum=20;receipt['ciphertext_sha256']='c'*64
            with self.assertRaisesRegex(LabError,'CHECKPOINT_RECEIPT_STATE'):verify_monotone_checkpoint(route,'HEAD',state)
    def test_I04_different_native_workflow_head_refused(self):
        from .attest_v3 import native_jobs
        from .test_native_acceptance_v3 import ArtificialRoute,RUN
        with self.assertRaisesRegex(LabError,'WORKFLOW_HEAD_MISMATCH'):
            native_jobs(ArtificialRoute(),RUN,('preflight',),expected_head_sha='1'*40)
    def test_SEC02_protected_boolean_does_not_replace_effective_authority(self):
        from .operational_acceptance import verify_effective_controls
        from .test_native_acceptance_v3 import ArtificialRoute
        from unittest.mock import patch
        for mutation in ('no_rules','wrong_writer','source_bypass'):
            route=ArtificialRoute();original=route.json
            def read(path):
                if mutation=='no_rules' and path=='rules/branches/main':return []
                value=original(path)
                if mutation=='wrong_writer' and path=='rulesets/2':value['bypass_actors'][0]['actor_id']=1
                if mutation=='source_bypass' and path=='rulesets/1':value['bypass_actors']=[{'actor_id':5343530,'actor_type':'Integration','bypass_mode':'always'}]
                return value
            with patch.object(route,'json',read),self.subTest(mutation=mutation),self.assertRaises(LabError):verify_effective_controls(route)
    def test_REC01_filtered_inventory_paginates(self):
        from .handoff_recovery import dispatch_inventory
        class Route:
            paths=[]
            def json(self,path):
                self.paths.append(path)
                ids=range(100) if path.endswith('&page=1') else range(100,101)
                return {'total_count':101,'workflow_runs':[{'id':i} for i in ids]}
        route=Route();self.assertEqual(len(dispatch_inventory(route,1000,4000)),101)
        self.assertEqual(len(route.paths),2)
        self.assertTrue(all('workflows/mxm-integrated-p0.yml/runs?' in p and 'event=workflow_dispatch' in p for p in route.paths))

if __name__=='__main__':unittest.main()
