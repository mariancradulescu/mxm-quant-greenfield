import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from .analysis import quote_index,pair_frontier,recover_targets,admission


def corpus():
    rows=[{'sid':i,'class':'forex','quote':'USD','min_units':1000} for i in (1,2)]
    events=[{'sid':i,'t':1700000100,'h':15,'entry':{'margin_eur':m,'cost_eur':1.,'notional_eur':1000.,'eligible':False}} for i,m in ((1,90.),(2,90.))]
    return {'all_identity_status':rows,'events':events,'catalog':{'full':{'1':{},'2':{}}}}


class Science(unittest.TestCase):
    def test_no_arbitrary_forty_percent_cap(self):
        r=pair_frontier(corpus());self.assertEqual(r['reference_affordable_pairs'],1)
        self.assertEqual(r['classification'],'COST_UNRESOLVED');self.assertIsNone(r['net_economic_edge'])
    def test_single_shared_account_not_two_eur200(self):
        c=corpus();c['events'][1]['entry']['margin_eur']=110
        self.assertEqual(pair_frontier(c)['reference_affordable_pairs'],0)
    def test_simultaneous_only(self):
        c=corpus();c['events'][1]['t']+=1
        self.assertEqual(pair_frontier(c)['same_clock_pair_observations'],0)
    def test_unknown_is_not_zero(self):
        c=corpus();c['events'][1]['entry']['cost_eur']=None
        r=pair_frontier(c);self.assertEqual(r['priced_minimum_tickets'],1);self.assertEqual(r['classification'],'DATA_INSUFFICIENT')
    def test_protected_rejected(self):
        c=corpus();c['events'][0]['t']=1789603200
        with self.assertRaisesRegex(ValueError,'DEVELOPMENT_BOUNDARY'):pair_frontier(c)
    def test_duplicate_not_independent_opportunity(self):
        c=corpus();c['events'].append(copy.deepcopy(c['events'][0]))
        self.assertEqual(pair_frontier(c)['same_clock_pair_observations'],1)
        c['events'][-1]['entry']['cost_eur']=2
        with self.assertRaisesRegex(ValueError,'EVENT_CONFLICT'):pair_frontier(c)
    def test_quote_conflict_quarantined(self):
        q={'symbol_id':1,'boundary_ms':1000,'sides':{}}
        r={**q,'sides':{'bid':2}}
        index,conflicts=quote_index([q,r]);self.assertEqual(index,{});self.assertEqual(conflicts,{(1,1)})
    def test_no_cross_quote_pair(self):
        c=corpus();c['all_identity_status'][1]['quote']='JPY'
        self.assertEqual(pair_frontier(c)['same_clock_pair_observations'],0)
    def test_original_target_and_no_replay(self):
        class Accounts:
            graph=staticmethod(lambda rows:{})
            point=staticmethod(lambda q:None)
            account=staticmethod(lambda *args:None)
        pilot={'selected_accounting':[{'sid':1,'t':100,'accounts':{'midpoint':{},'quote_count':{}},'feature':{'model_side':1}}]}
        target={'symbol_id':1,'entry_second':100,'scheduled_exit_second':1000,'missing_arms':['model']}
        r=recover_targets(pilot,[target],corpus(),{},Accounts)
        self.assertEqual(r['unresolved_arms'],1);self.assertEqual(r['pilot_replays'],0)
        self.assertFalse(r['complete_pilot_reconstructed'])
        target['entry_second']=101
        with self.assertRaisesRegex(ValueError,'ORIGINAL_TARGET'):recover_targets(pilot,[target],corpus(),{},Accounts)
    def test_no_affordability_promotion(self):
        r=admission({'pilot_replays':0,'classification':'DATA_INSUFFICIENT'},pair_frontier(corpus()))
        self.assertFalse(r['cbot_qualified']);self.assertTrue(r['safe_stop']);self.assertIsNone(r['pending'])


class Checkpoint(unittest.TestCase):
    def test_cross_stage_binding_and_tamper(self):
        from . import runtime as r
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'verification/laboratory-input').mkdir(parents=True)
            p=root/'design';p.mkdir();(p/'DESIGN.json').write_text('{}')
            blob=b'authenticated fixture ciphertext';(root/'verification/laboratory-input/recovery.mxmenc').write_bytes(blob)
            cp={'schema':'mxm.finite-laboratory-checkpoint.v1','stage':'recovery','source_sha':'a'*40,'trigger_sha':'b'*40,'run_id':1,'run_attempt':1,'design_sha256':r.sha(b'{}'),'authority':r.ACTIVE,'pending':None,'values':{'kept':True}}
            env={'LAB_PARENT_SHA256':r.sha(blob),'LAB_SOURCE_SHA':'a'*40,'GITHUB_SHA':'b'*40,'GITHUB_RUN_ID':'1'}
            with patch.object(r,'ROOT',root),patch.object(r,'P',p),patch.dict(r.os.environ,env),patch.object(r.owner,'bounded_decrypt',side_effect=lambda *a:json.dumps(cp).encode()),patch.object(r,'unpack',side_effect=lambda x:x):
                self.assertEqual(r.read_checkpoint('frontier',None,None),{'kept':True})
                cp['pending']='ambiguous intent'
                with self.assertRaisesRegex(ValueError,'COLD_BINDING'):r.read_checkpoint('frontier',None,None)
                cp['pending']=None;cp['run_id']=2
                with self.assertRaisesRegex(ValueError,'COLD_BINDING'):r.read_checkpoint('frontier',None,None)
                (root/'verification/laboratory-input/recovery.mxmenc').write_bytes(b'tampered')
                with self.assertRaisesRegex(ValueError,'PARENT_CIPHER'):r.read_checkpoint('frontier',None,None)

if __name__=='__main__':unittest.main()
