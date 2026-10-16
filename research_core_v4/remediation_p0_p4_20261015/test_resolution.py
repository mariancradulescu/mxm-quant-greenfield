"""Adversarial controls for the bounded evidence reader and saved label errata."""
import copy
import unittest
from .resolution import EvidenceIndex,unique_metadata,economic_errata,consumer_state,public_summary,LOW,END
from .safety import canonical,sha

def meta(aid):
    return {'id':aid,'release_id':7,'ciphertext_sha256':'c'*64,'gzip_sha256':'g'*64,'canonical_sha256':'p'*64,'size':10,'name':str(aid)+'.mxmenc'}

def journal(*ids):
    return {'snapshots_v2':[meta(i) for i in ids],'generation':1807}

class P0(unittest.TestCase):
    def test_duplicate_manifest_conflict_rejects(self):
        j=journal(1);j['increments_v2']=[{**meta(1),'gzip_sha256':'x'*64}]
        with self.assertRaisesRegex(ValueError,'DUPLICATE_ASSET_MANIFEST_CONFLICT'):unique_metadata(j)
        j['increments_v2']=[meta(1)];self.assertEqual(len(unique_metadata(j)),1)

    def test_missing_duplicate_foreign_asset_rejected(self):
        i=EvidenceIndex(journal(1,2));i.consume(meta(1),{})
        with self.assertRaisesRegex(ValueError,'EVIDENCE_UNIVERSE_NOT_EXACT'):i.finish()
        with self.assertRaisesRegex(ValueError,'FOREIGN_ASSET'):i.consume(meta(3),{})
        i.unavailable(meta(2),'SOURCE_ABSENT');self.assertEqual(i.finish()['unavailable_assets'],1)
        i.unavailable(meta(2),'DUPLICATE')
        with self.assertRaisesRegex(ValueError,'EVIDENCE_UNIVERSE_NOT_EXACT'):i.finish()

    def test_declared_bound_receipt_does_not_create_identity(self):
        raw={'request':{'s':1,'k':'bid','a':LOW,'b':LOW+10},'state':'UNKNOWN_TRANSPORT','exception_class':'TransportError','preserved_failure_evidence':{'state':'REQUEST_BOUND','evidence':{'request':{'s':2}}}}
        obj={'raw':[raw]};before=canonical(obj);i=EvidenceIndex(journal(1));i.consume(meta(1),obj);result=i.finish()
        self.assertEqual(canonical(obj),before);self.assertEqual(result['additive_errata'][0]['physical_cause'],'UNKNOWN');self.assertEqual(result['raw_receipts'][0]['failure_binding'],'EVIDENCE_UNBOUND')
        self.assertFalse(result['original_changed']);self.assertFalse(result['global_historical_impact_closed'])

class P1(unittest.TestCase):
    def test_conflict_has_both_asset_ids_and_keeps_original(self):
        t=LOW;one={'wire':[[1,'bid',t,t+10,'UNCERTAIN_WIRE',None]],'spans':[[1,'bid',t,t+10,'UNKNOWN_TRANSPORT']]};two={'wire':[[1,'bid',t,t+10,'CONFIRMED_COMPLETE','x']],'spans':[[1,'bid',t+5,t+15,'CONFIRMED_COMPLETE']]}
        before=[sha(canonical(x)) for x in (one,two)]
        for order in ((1,2),(2,1)):
            i=EvidenceIndex(journal(1,2))
            for aid in order:i.consume(meta(aid),one if aid==1 else two)
            r=i.finish();self.assertEqual(len(r['wire_conflicts']),1);self.assertEqual(len(r['span_conflicts']),1);self.assertEqual({s['asset_id'] for s in r['span_conflicts'][0]['sources']},{1,2});self.assertEqual(r['span_conflicts'][0]['disposition'],'UNKNOWN_CONFLICT_QUARANTINE')
        self.assertEqual(before,[sha(canonical(x)) for x in (one,two)])

    def test_no_false_boundary_or_ohlc_clean(self):
        t=LOW//1000;v={'bars':[[1,t,2,1,0,2,-1]],'ticks':[[1,'bid',END,100]],'spans':[[1,'M5',END,LOW,'CONFIRMED_COMPLETE']]}
        i=EvidenceIndex(journal(1));i.consume(meta(1),v);r=i.finish();self.assertEqual(len(r['sources'][0]['invalid_rows']),3);self.assertEqual(len(r['additive_errata']),3)

    def test_complete_source_integrity_is_not_complete_provenance(self):
        i=EvidenceIndex(journal(1));i.consume(meta(1),{'bars':[[1,LOW//1000,2,3,1,2,0]]});r=i.finish();s=public_summary(r,{'OWNER_readback':True})
        self.assertEqual(s['verified_assets'],1);self.assertEqual(s['additive_errata'],0);self.assertFalse(s['row_provenance_complete']);self.assertTrue(consumer_state(s)['data_blocked'])

class P2(unittest.TestCase):
    def test_historical_catalog_scope_is_not_invented(self):
        j=journal(1);j['archive']={'asset_receipts':[{'asset_id':4,'state':'UNKNOWN_WITH_EXACT_CAUSE'}]};i=EvidenceIndex(j);i.consume(meta(1),{});r=i.finish()
        self.assertEqual(r['historical_import_locator_catalog'][0]['asset_id'],4);self.assertFalse(r['historical_catalog_complete'])

def economic_fixture():
    c={'accepted_result_reused_without_signal_replay':{'canonical_sha256':'a'*64},'new_directional_outcomes':0,'corrected_cost_populations':{'M_h15_s2':{k:{'n':n} for k,n in [('all_cost_observable',8),('entry_feasible',6),('entry_feasible_exit_observed',4),('entry_feasible_path_complete',2)]}}}
    a={'summary':{'cases':{'M_h15_s2':{'cohort':8,'cost':'HISTORICAL_UNCHANGED'}}}}
    h={'summary':{'schema':'historic','decision':'CLOSED_NEGATIVE','alpha_certified':False,'HARD21':False,'portfolio':{'equity':199},'economic_aggregate':{'net':-1},'NET_semantics':'REFERENCE_ONLY'}}
    return c,a,h,{'accepted':{'canonical_sha256':'a'*64}}

class P3(unittest.TestCase):
    def test_saved_populations_and_equity_labels_no_recompute(self):
        args=economic_fixture();before=canonical(args);r=economic_errata(*args)
        self.assertEqual(before,canonical(args));self.assertEqual(r['input_before_sha256'],r['input_after_sha256']);self.assertIsNone(r['new_NET']);self.assertEqual(r['new_outcomes'],0);self.assertEqual(r['historical_reference']['decision'],'CLOSED_NEGATIVE');self.assertFalse(r['successor_continuous_ledger']['real_account_certified'])

    def test_wrong_saved_source_or_new_outcomes_rejected(self):
        args=list(economic_fixture());args[0]['accepted_result_reused_without_signal_replay']['canonical_sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'CORRECTED_ACCEPTED_SOURCE_MISMATCH'):economic_errata(*args)
        args=list(economic_fixture());args[0]['new_directional_outcomes']=1
        with self.assertRaisesRegex(ValueError,'CORRECTION_HAS_NEW_OUTCOME'):economic_errata(*args)

    def test_wrong_case_cohort_and_nonmonotonic_counts_rejected(self):
        for kind in ('case','cohort','hierarchy'):
            args=list(economic_fixture())
            if kind=='case':args[1]['summary']['cases']['OTHER']={}
            if kind=='cohort':args[1]['summary']['cases']['M_h15_s2']['cohort']=9
            if kind=='hierarchy':args[0]['corrected_cost_populations']['M_h15_s2']['entry_feasible_path_complete']['n']=7
            with self.assertRaises(ValueError):economic_errata(*args)

class P4(unittest.TestCase):
    def test_public_summary_does_not_leak_private_locator_or_promote(self):
        i=EvidenceIndex(journal(1));i.consume(meta(1),{'raw':[{'request':{'account':'PRIVATE_ACCOUNT_CANARY','s':1},'state':'UNKNOWN_TRANSPORT'}]});r=i.finish();s=public_summary(r,{'ciphertext_sha256':'x'*64})
        self.assertNotIn('PRIVATE_ACCOUNT_CANARY',canonical(s).decode());self.assertNotIn('raw_receipts',s);self.assertFalse(s['independent_acceptance']);self.assertFalse(s['alpha_certified']);self.assertFalse(s['history_complete'])
