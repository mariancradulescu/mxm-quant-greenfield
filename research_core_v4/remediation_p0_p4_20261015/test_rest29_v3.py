"""Only residual controls and workflow guard affected by this change are run."""
import copy
import io
import json
import pathlib
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from . import rest29_v3 as r
from .safety import sha,canonical

class RemainingTests(unittest.TestCase):
    def test_native_observation_sweep_matches_existing_control_and_empty_differs(self):
        import sqlite3
        from research_core_v4.remediation_p0_p4_20261015.control import observed_interval
        db=sqlite3.connect(':memory:');db.executescript('CREATE TABLE tick(s,k,t,p);CREATE TABLE span(s,k,a,b,z);')
        a=1788000000000;b=a+900000
        db.executemany('INSERT INTO span VALUES(?,?,?,?,?)',[(1,s,a,b,'EMPTY_AUTHENTIC_RESPONSE') for s in ('bid','ask')])
        self.assertTrue(all(r.legacy_known_coverage(db,1,s,a,b) for s in ('bid','ask')))
        self.assertFalse(r.native_observation_mask(db,1,a,b)['observed'])
        for side,price in (('bid',100),('ask',101)):
            db.executemany('INSERT INTO tick VALUES(?,?,?,?)',[(1,side,a+t,price) for t in (0,300000,600000,900000)])
        self.assertTrue(r.native_observation_mask(db,1,a,b)['observed'])
        self.assertEqual(r.native_observation_mask(db,1,a,b)['observed'],observed_interval(db,1,a,b))
        db.execute('DELETE FROM tick WHERE k="ask" AND t=?',(a+300000,))
        self.assertFalse(r.native_observation_mask(db,1,a,b)['observed']);self.assertEqual(r.native_observation_mask(db,1,a,b)['observed'],observed_interval(db,1,a,b))
        db.execute('INSERT INTO tick VALUES(?,?,?,?)',(1,'ask',a+300000,99))
        self.assertEqual(r.native_observation_mask(db,1,a,b)['reason'],'INVALID_CROSSED_NATIVE_QUOTE')
        db.close()

    def test_cold_receipt_all_three_hashes_or_reject(self):
        p={'ciphertext_sha256':'a','gzip_sha256':'b','canonical_sha256':'c'}
        self.assertTrue(r.validate_cold_receipt(p,p))
        for k in p:
            bad=dict(p);bad[k]='WRONG'
            with self.assertRaisesRegex(ValueError,'COLD_RECEIPT_MISMATCH'):r.validate_cold_receipt(p,bad)

    def test_family_roles_exact_original_partition_no_execution_promotion(self):
        f=json.loads((r.ROOT/'research_core_v4/state/STRICT_PREOUTCOME_V2_CURRENT_TESTABILITY_FRONTIER_V1.json').read_text())
        before=canonical(f);p=r.family_partition(f);self.assertEqual([len(p[k]) for k in ('selected','parked','baseline')],[5,6,1]);self.assertFalse(p['roles_are_execution_outcomes']);self.assertEqual(before,canonical(f))
        f['parked_sources'][0]=f['current_wave'][0]
        with self.assertRaisesRegex(ValueError,'FAMILY_ROLE_COLLISION'):r.family_partition(f)

    def test_get_only_rejects_all_mutations_before_io(self):
        t=r.GetOnly()
        with patch.object(t.opener,'open') as opened:
            for method in ('POST','PATCH','PUT','DELETE'):
                with self.assertRaisesRegex(ValueError,'READER_MUTATION_DENIED'):t.open(urllib.request.Request('https://api.github.com/repos/'+r.REPO+'/releases/1',method=method,data=b'{}'))
            opened.assert_not_called()

    def test_get_only_rejects_broker_and_foreign_namespace(self):
        t=r.GetOnly()
        with patch.object(t.opener,'open') as opened:
            for u in ('https://broker.invalid/','https://api.github.com/user','http://api.github.com/repos/'+r.REPO+'/releases/1'):
                with self.assertRaises(ValueError):t.open(u)
            opened.assert_not_called()

    def test_real_get_or_create_helper_cannot_create_in_reader(self):
        from research_core_v4.critical_frontier_repair_20261014_v2 import storage_v2
        t=r.GetOnly();seen=[]
        def missing(req,timeout=60):
            seen.append(req.get_method());raise urllib.error.HTTPError(req.full_url,404,'synthetic missing',{},None)
        def api(path,method='GET',data=None):
            req=urllib.request.Request('https://api.github.com/repos/'+r.REPO+'/'+path,method=method,data=None if data is None else canonical(data))
            return t.open(req)
        with patch.object(t.opener,'open',side_effect=missing),patch.object(storage_v2,'api',side_effect=api):
            with self.assertRaisesRegex(ValueError,'READER_MUTATION_DENIED'):storage_v2.get_or_create('SYNTHETIC_TEST_ONLY','H')
        self.assertEqual(seen,['GET'])

    def test_missing_or_malformed_source_never_calls_mutation(self):
        t=r.GetOnly()
        with patch.object(t,'data',return_value=b'{bad') as read:
            with self.assertRaises(ValueError):t.json('releases/1')
            read.assert_called_once_with('releases/1')

    def test_redirect_strips_token_for_asset_host(self):
        h=r.Redirect();req=urllib.request.Request('https://api.github.com/repos/'+r.REPO+'/actions/artifacts/1/zip',headers={'Authorization':'Bearer SYNTHETIC_TOKEN'})
        new=h.redirect_request(req,None,302,'',{},'https://release-assets.githubusercontent.com/signed-asset')
        self.assertIsNone(new.get_header('Authorization'))

    def test_redirect_to_broker_or_http_is_rejected(self):
        h=r.Redirect();req=urllib.request.Request('https://api.github.com/repos/'+r.REPO+'/releases/1')
        for url in ('https://broker.invalid/','http://release-assets.githubusercontent.com/asset'):
            with self.assertRaises(ValueError):h.redirect_request(req,None,302,'',{},url)

    def test_exact_native_partial_suffix_explained_without_promotion(self):
        c={'key':[1,'bid'],'a':51,'b':100,'sources':[{'a':0,'b':100,'state':'PARTIAL_HASMORE'},{'a':51,'b':100,'state':'CONFIRMED_COMPLETE'}]}
        receipt={'request':{'s':1,'k':'bid','a':0,'b':100},'has_more_present':True,'has_more':True,'native_tick_times_ms':[50,99],'response_sha256':'h','raw_sha256':'r','asset_id':1,'complete_source_identity':False}
        wire=[[1,'bid',0,100,'PARTIAL_HASMORE','h']];before=canonical([c,receipt,wire]);out=r.pagination_assessment(c,[receipt],wire)
        self.assertEqual(out['state'],'NATIVE_HASMORE_NESTING_RECONCILED_SOURCE_IDENTITY_STILL_UNKNOWN');self.assertFalse(out['coverage_promoted']);self.assertTrue(out['quarantine_retained']);self.assertFalse(out['complete_source_identity']);self.assertEqual(before,canonical([c,receipt,wire]))

    def test_unrelated_complete_page_or_wire_hash_does_not_erase_partial(self):
        c={'key':[1,'bid'],'a':51,'b':100,'sources':[{'a':0,'b':100,'state':'PARTIAL_HASMORE'},{'a':51,'b':100,'state':'CONFIRMED_COMPLETE'}]}
        receipt={'request':{'s':1,'k':'bid','a':0,'b':100},'has_more_present':True,'has_more':True,'native_tick_times_ms':[50,99],'response_sha256':'h','raw_sha256':'r','asset_id':1,'complete_source_identity':False}
        self.assertTrue(r.pagination_assessment(c,[receipt],[[1,'bid',0,100,'PARTIAL_HASMORE','WRONG']])['state'].startswith('UNKNOWN'))
        receipt['has_more']=False
        self.assertTrue(r.pagination_assessment(c,[receipt],[[1,'bid',0,100,'PARTIAL_HASMORE','h']])['state'].startswith('UNKNOWN'))

    def test_m5_nested_suffix_requires_exact_native_bar_time(self):
        c={'key':[1,'M5'],'a':60000,'b':90000,'sources':[{'a':0,'b':90000,'state':'PARTIAL_HASMORE'},{'a':60000,'b':90000,'state':'CONFIRMED_COMPLETE'}]}
        receipt={'request':{'s':1,'k':'M5','a':0,'b':90000},'has_more_present':True,'has_more':True,'native_minutes':[1],'response_sha256':'h','raw_sha256':'r','asset_id':1,'complete_source_identity':False}
        self.assertEqual(r.pagination_assessment(c,[receipt],[[1,'M5',0,90000,'PARTIAL_HASMORE','h']])['state'],'NATIVE_HASMORE_NESTING_RECONCILED_SOURCE_IDENTITY_STILL_UNKNOWN')
        receipt['native_minutes']=[2]
        self.assertTrue(r.pagination_assessment(c,[receipt],[[1,'M5',0,90000,'PARTIAL_HASMORE','h']])['state'].startswith('UNKNOWN'))

    def test_partial_boundary_exact_content_join_without_identity_promotion(self):
        c={'key':[1,'bid'],'a':50,'b':50,'sources':[{'a':50,'b':50,'state':'PARTIAL_HASMORE_BOUNDARY_UNRESOLVED'},{'a':11,'b':50,'state':'CONFIRMED_COMPLETE'}]}
        old={'request':{'s':1,'k':'bid','a':0,'b':100},'has_more_present':True,'has_more':True,'native_tick_rows':[[50,100],[99,101]],'response_account':1,'response_sha256':'old','raw_sha256':'o'}
        new={'request':{'s':1,'k':'bid','a':0,'b':50},'has_more_present':True,'has_more':True,'native_tick_rows':[[10,99],[50,100],[50,101]],'response_account':1,'response_sha256':'new','raw_sha256':'n'}
        wires=[[1,'bid',0,100,'PARTIAL_HASMORE','old'],[1,'bid',0,50,'PARTIAL_HASMORE','new']]
        out=r.pagination_assessment(c,[old,new],wires)
        self.assertEqual(out['state'],'NATIVE_PAGINATION_BOUNDARY_RECONCILED_SOURCE_IDENTITY_STILL_UNKNOWN');self.assertEqual(out['boundary_partial_rows'],1);self.assertEqual(out['boundary_covering_rows'],2);self.assertTrue(out['quarantine_retained']);self.assertFalse(out['complete_source_identity'])

    def test_boundary_join_rejects_missing_tick_and_foreign_account(self):
        c={'key':[1,'bid'],'a':50,'b':50,'sources':[{'a':50,'b':50,'state':'PARTIAL_HASMORE_BOUNDARY_UNRESOLVED'},{'a':11,'b':50,'state':'CONFIRMED_COMPLETE'}]}
        old={'request':{'s':1,'k':'bid','a':0,'b':100},'has_more_present':True,'has_more':True,'native_tick_rows':[[50,100],[99,101]],'response_account':1,'response_sha256':'old','raw_sha256':'o'}
        new={'request':{'s':1,'k':'bid','a':0,'b':50},'has_more_present':True,'has_more':True,'native_tick_rows':[[10,99],[50,102]],'response_account':1,'response_sha256':'new','raw_sha256':'n'}
        wires=[[1,'bid',0,100,'PARTIAL_HASMORE','old'],[1,'bid',0,50,'PARTIAL_HASMORE','new']]
        self.assertTrue(r.pagination_assessment(c,[old,new],wires)['state'].startswith('UNKNOWN'))
        new['native_tick_rows'][1]=[50,100];new['response_account']=2
        self.assertTrue(r.pagination_assessment(c,[old,new],wires)['state'].startswith('UNKNOWN'))

    def test_complete_parent_chain_has_exact_three_digests(self):
        def item(i,parent=None):return {'state':'OWNER_DECODED','meta':{'id':i,'ciphertext_sha256':str(i)*64,'gzip_sha256':'g'*64,'canonical_sha256':'p'*64},'parent_ledger':parent}
        a=item(1);b=item(2,a['meta']);out=r.verify_chain(b['meta'],{1:a,2:b});self.assertTrue(out['complete']);self.assertEqual(out['nodes'],[2,1])
        bad=copy.deepcopy(a['meta']);bad['gzip_sha256']='X'*64
        with self.assertRaisesRegex(ValueError,'PARENT_DIGEST_MISMATCH'):r.verify_chain(bad,{1:a})

    def test_missing_parent_or_cycle_never_returns_complete(self):
        self.assertFalse(r.verify_chain({'id':1},{})['complete'])
        a={'state':'OWNER_DECODED','meta':{'id':1},'parent_ledger':{'id':1}}
        with self.assertRaisesRegex(ValueError,'LEDGER_CYCLE'):r.verify_chain({'id':1},{1:a})

    def test_unbound_failure_keeps_unknown(self):
        raw={'request':{'s':1,'k':'bid','a':1,'b':2},'state':'UNKNOWN_TRANSPORT','exception_class':'TransportError','preserved_failure_evidence':{'request':{'s':2}}};before=canonical(raw)
        got=r.raw_receipt(raw,1);self.assertEqual(got['failure_binding'],'EVIDENCE_UNBOUND');self.assertEqual(got['physical_cause'],'UNKNOWN');self.assertFalse(got['promote_coverage']);self.assertEqual(before,canonical(raw))

    def test_stored_response_presence_does_not_invent_server_or_dispatch(self):
        from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAGetTickDataRes
        import base64
        res=ProtoOAGetTickDataRes(ctidTraderAccountId=3,hasMore=False)
        raw={'request':{'s':1,'k':'bid','a':1,'b':2},'response_b64':base64.b64encode(res.SerializeToString()).decode()};got=r.raw_receipt(raw,1)
        self.assertTrue(got['has_more_present']);self.assertFalse(got['has_more']);self.assertEqual(got['native_rows'],0);self.assertFalse(got['complete_source_identity']);self.assertFalse(got['promote_coverage'])

    def test_hasmore_absent_never_inferred_from_default_false(self):
        from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAGetTickDataRes
        import base64
        res=ProtoOAGetTickDataRes(ctidTraderAccountId=3)
        got=r.raw_receipt({'response_b64':base64.b64encode(res.SerializePartialToString()).decode()},1)
        self.assertFalse(got['has_more_present']);self.assertIsNone(got['has_more'])

    def test_historical_impact_does_not_use_short_m5_lookback(self):
        ev={'sid':1,'t':200000,'kind':'REOPEN'};conf=[{'key':[1,'M5'],'a':1000,'b':2000}];before=canonical(ev)
        got=r.contact(ev,conf);self.assertEqual(got['state'],'POTENTIAL_INPUT_CONTACT_NOT_RECOMPUTED');self.assertEqual(before,canonical(ev));self.assertTrue(got['old_net_unchanged'])

    def test_unknown_fx_mask_cannot_be_reported_zero_impact(self):
        ev={'sid':1,'t':2000};conf=[{'key':[2,'bid'],'a':1999000,'b':2000000}]
        self.assertEqual(r.contact(ev,conf)['state'],'UNKNOWN_FX_DEPENDENCY_MASK')
        ev['ids']=[1];self.assertEqual(r.contact(ev,conf)['state'],'NO_CONFLICT_DOMAIN_CONTACT_WITHIN_DECLARED_DEPENDENCIES')

    def test_event_foreign_time_and_identity_remain_unknown(self):
        self.assertEqual(r.contact({'t':1},[])['state'],'UNKNOWN_EVENT_IDENTITY')
        self.assertTrue(r.overlaps(1,2,2,3));self.assertFalse(r.overlaps(1,2,3,4))

    def test_epoch_scan_preserves_bad_authentic_rows_for_errata(self):
        data={'bars':[[1,123,2,3,1,2,0]],'ticks':[[1,'bid','naive',1]]};before=canonical(data);out=r.asset_rows(data)
        self.assertEqual(out['time_schema_errors'],{'bar_time':1,'tick_time':1});self.assertEqual(out['transformed_rows'],0);self.assertEqual(before,canonical(data))

    def test_global_predecessor_release_cas_is_not_claimed(self):
        from research_core_v4.critical_frontier_repair_20261014_v2 import storage_v2
        a=object.__new__(storage_v2.RotatingStore);b=object.__new__(storage_v2.RotatingStore);remote={'body':'{}'};patches=[]
        for x in (a,b):x.index=0;x.release={'id':2};x.limit=750;x.anchor={'id':1,'body':'{}'}
        def api(path,method='GET',data=None):
            if method=='PATCH':patches.append(data);remote.update(data)
            return dict(remote)
        with patch.object(storage_v2,'api',side_effect=api):
            a.commit({'generation':1808,'journal_sha':'A'});b.commit({'generation':1808,'journal_sha':'B'})
        self.assertEqual(len(patches),2);self.assertEqual(json.loads(remote['body'])['journal_sha'],'B')
        # This is an explicit counterexample on a fixture, not a real write or
        # a global safety pass. O04.1 must stay NO-GO under this mandate.

    def test_current_workflow_guard_affected_by_new_jobs(self):
        from .policy import workflow_guard
        self.assertEqual(workflow_guard(r.ROOT)['legacy_inert'],193)

def main():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(RemainingTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    p=r.ROOT/'verification';p.mkdir(exist_ok=True)
    (p/'rest29-tests.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'scope':'ONLY_REST29_AND_AFFECTED_WORKFLOW_POLICY;NO_FULL_162_PASS_REEXECUTION','alpha_certified':False,'broker_requests':0},sort_keys=True)+'\n')
    if not result.wasSuccessful():raise SystemExit(1)

if __name__=='__main__':main()
