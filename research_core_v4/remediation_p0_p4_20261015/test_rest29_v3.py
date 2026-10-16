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
        new=h.redirect_request(req,None,302,'',{},'https://example.invalid/signed-asset')
        self.assertIsNone(new.get_header('Authorization'))

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
