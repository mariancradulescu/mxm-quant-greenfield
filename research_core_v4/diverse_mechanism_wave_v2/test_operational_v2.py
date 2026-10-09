"""Only new diagnostics, unchanged mathematics and scientific recovery adapter."""
import copy,json,math,unittest
from types import SimpleNamespace
from unittest.mock import patch
from research_core_v4.diverse_mechanism_wave_v1 import worker_v1 as original,synthetic_v1 as fixtures,kernel_v1 as k
from research_core_v4.diverse_mechanism_wave_v1.test_wave_v1 import Scientific,buffer
from research_core_v4.diverse_mechanism_wave_v2 import worker_v2 as w,authority_v2 as a
from research_core_v4.numeric_development_v1.public_output_guard_v1 import PublicDisclosureDenied,ROOT,validate_public_blob

def fabricated():
    master,entries,digits,_=w.old.verify_science();e=w.new(master);legacy=original.new(master);processed=[]
    for idx in range(2):
        raw,meta=fixtures.fabricated_shard(idx,master,digits);blob=b'fabricated-test';meta['ENCRYPTED_ASSET_SHA256']=a.sha(blob)
        w.consume(e,raw,meta,master,digits,blob);original.consume(legacy,raw,meta,master,digits,blob);processed.append(w.v2.source_record(idx,meta))
    arm=a.candidate('a'*40,{},'synthetic');rows=e['rows'];r=w.report(e,rows,2,processed,arm);r0=original.report(legacy,rows,2,processed,arm)
    store=SimpleNamespace(arm=arm,approval_sha='b'*64,original_run=1,mode='synthetic',release={'target_commitish':'c'*40})
    j={'schema':'mxm.numeric.finalization.input.v3','arm_sha256':a.sha(a.enc(arm)),'approval_sha256':'b'*64,'invocation_id':arm['invocation_id'],'bindings':arm['bindings'],'original_run':1,'source_head':'c'*40,'engine':e,'report':r}
    return master,entries,digits,e,r,r0,store,j

class Operational(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=fabricated()
    def test_all_gross_and_support_outputs_identical_to_v1(self):
        _,_,_,e,r,r0,_,_=self.data
        for lag in map(str,k.LAGS):
            for mech in k.MECHANISMS:
                v=dict(r['full_frontier'][lag][mech]);del v['h2_diagnostic'];self.assertEqual(v,r0['full_frontier'][lag][mech])
                for week in range(4):
                    v=dict(r['four_weeks'][lag][week][mech]);del v['h2_diagnostic'];self.assertEqual(v,r0['four_weeks'][lag][week][mech])
        for i,(one,old) in enumerate(zip(r['identity_results'],r0['identity_results'])):
            for lag in map(str,k.LAGS):
                for mech in k.MECHANISMS:
                    v=dict(one['lags'][lag][mech]);del v['h2_diagnostic'];self.assertEqual(v,old['lags'][lag][mech])
    def test_positive_negative_h2_invariants_for_all_lags(self):
        for negative in (False,True):
            b=buffer()
            if negative:
                for x in b.values():
                    o,c,h,l=x['open'],x['close'],x['high'],x['low'];x.update(open=2000-o,close=2000-c,high=2000-l,low=2000-h)
            for lag in k.LAGS:
                t=w.n.START+(3 if lag==0 else 4)*3600;d,_=k.directions(b,t,lag);hs,_=k.hours(b,t,lag);sign=1 if hs[1]['c']>hs[1]['o'] else -1
                self.assertEqual(d[k.MECHANISMS[0]][0],sign);self.assertEqual(d[k.MECHANISMS[1]][0],-sign)
    def test_emitted_and_mature_subsets_separate(self):
        m=w.metrics();w.tally(m,None,'LABEL_GAP',True,True,'agreements');w.validate_metric(m,k.MECHANISMS[0]);self.assertEqual(m['h2_diagnostic']['emitted']['eligible'],1);self.assertEqual(m['h2_diagnostic']['supported']['eligible'],0)
    def test_final_journal_complete(self):
        *_,store,j=self.data;w.validate_journal(store,j)
    def test_missing_diagnostic_rejected_in_state_and_report(self):
        *_,store,j=self.data
        for place in ('state','report'):
            bad=copy.deepcopy(j)
            m=bad['engine']['states'][0]['lag']['0'][k.MECHANISMS[0]] if place=='state' else bad['report']['full_frontier']['0'][k.MECHANISMS[0]]
            del m['h2_diagnostic']
            with self.assertRaises((w.n.NumericalStop,KeyError)):w.validate_journal(store,bad)
    def test_diagnostic_denominator_and_wrong_invariant_rejected(self):
        master,_,_,e,*_=self.data
        for field in ('eligible','agreements','undefined'):
            bad=copy.deepcopy(e);bad['states'][0]['lag']['0'][k.MECHANISMS[0]]['h2_diagnostic']['emitted'][field]+=1
            with self.assertRaises(w.n.NumericalStop):w.validate_engine(bad,master)
    def test_weekly_identity_and_full_reconciliation(self):
        master,_,_,e,r,*_=self.data;w.validate_engine(e,master)
        for lag in map(str,k.LAGS):
            for mech in k.MECHANISMS:
                for sub in ('emitted','supported'):
                    full=r['full_frontier'][lag][mech]['h2_diagnostic'][sub]
                    self.assertEqual(full,w.diagnostic() | {x:sum(week[mech]['h2_diagnostic'][sub][x] for week in r['four_weeks'][lag]) for x in w.diagnostic()})
                    self.assertEqual(full,{x:sum(identity['lags'][lag][mech]['h2_diagnostic'][sub][x] for identity in r['identity_results']) for x in w.diagnostic()})
    def test_causal_buffer_and_source_prefix_rejections(self):
        master,entries,digits,_=w.old.verify_science();e=w.new(master);raw,meta=fixtures.fabricated_shard(0,master,digits);blob=b'prefix';meta['ENCRYPTED_ASSET_SHA256']=a.sha(blob);w.consume(e,raw,meta,master,digits,blob)
        prefix={'engine':e,'processed_sources':[w.v2.source_record(0,meta)],'expected_rows':e['rows']};w.verify_processed(prefix,'synthetic',master,digits,entries)
        mutations=[lambda x:x['processed_sources'][0].update(ordinal=1),lambda x:x['engine']['states'][0].update(symbol_id=-1),lambda x:x['engine']['states'][0]['buffer'].pop(str(x['engine']['states'][0]['last'])),lambda x:next(iter(x['engine']['states'][0]['buffer'].values())).update(available_at=0),lambda x:x['engine']['states'][0]['weekly'][0]['0'][k.MECHANISMS[0]]['h2_diagnostic']['emitted'].update(eligible=999)]
        for mutate in mutations:
            bad=copy.deepcopy(prefix);mutate(bad)
            with self.assertRaises(w.n.NumericalStop):w.verify_processed(bad,'synthetic',master,digits,entries)
    def test_worker_and_kernel_exact_separate_identities(self):
        doc=w.safe_status('a'*40,'FINAL','PASS');self.assertEqual(doc['worker_sha256'],a.digest(a.WORKER));self.assertNotEqual(doc['worker_sha256'],a.digest(a.KERNEL));validate_public_blob(ROOT+'DIVERSE_WAVE_V2_SYNTHETIC_COMPLETION_V1.json',doc)
    def test_public_guard_at_actual_release_and_git_callsites(self):
        master,_,_,e,r,_,store,j=self.data;unsafe=w.safe_status('a'*40,'FINAL','PASS');unsafe['h2_diagnostic']=r['full_frontier']
        instance=w.Store('a'*40,None,None,None,store.arm,store.approval_sha,'0'*64);instance.release={'id':1,'target_commitish':'a'*40}
        with patch.object(w.old,'api') as api:
            for action in (lambda:instance.body(unsafe),lambda:instance.publish_exact(unsafe,ROOT+'DIVERSE_WAVE_V2_SYNTHETIC_COMPLETION_V1.json')):
                with self.assertRaises(PublicDisclosureDenied):action()
            api.assert_not_called()
    def test_real_default_deny_and_scope_or_source_tamper(self):
        with self.assertRaises(w.n.NumericalStop):a.real_gate('a'*40)
        arm=a.candidate('a'*40,{},'synthetic');arm['worker_sha256']='0'*64
        with self.assertRaises(w.n.NumericalStop):a.validate_candidate('a'*40,arm,'synthetic')
    def test_authenticated_prefix_exact_buffer_hash_and_resources(self):
        master,entries,digits,_=w.old.verify_science();e=w.new(master)
        raw,meta=fixtures.fabricated_shard(0,master,digits);cipher=b'prefix';meta['ENCRYPTED_ASSET_SHA256']=a.sha(cipher);w.consume(e,raw,meta,master,digits,cipher)
        arm=a.candidate('a'*40,{},'synthetic');store=w.Store('a'*40,None,None,None,arm,'0'*64,'0'*64)
        prefix=store.envelope(e,e['rows'],[w.v2.source_record(0,meta)],{'wall_seconds':1,'cpu_seconds':1})
        w.verify_processed(prefix,'synthetic',master,digits,entries)
        for field in ('rolling_buffer_sha256','scientific_state_sha256','worker_sha256'):
            bad=copy.deepcopy(prefix);bad[field]=[] if field=='rolling_buffer_sha256' else '0'*64
            with self.assertRaises(w.n.NumericalStop):w.verify_processed(bad,'synthetic',master,digits,entries)
    def test_recovery_body_keeps_original_invocation_identity(self):
        *_,s,j=self.data;store=w.Store('d'*40,None,None,None,s.arm,s.approval_sha,'0'*64);store.release={'id':1,'target_commitish':'c'*40}
        with patch.object(w.v2.Store,'body') as body:
            store.body(w.safe_status('d'*40,'NUMERIC_DEVELOPMENT','NOT_PERSISTED'));self.assertEqual(body.call_args.args[0]['source_head'],'c'*40)
    def test_prepared_journal_resources_include_original_budget(self):
        *_,s,j=self.data;store=w.Store('d'*40,None,None,None,s.arm,s.approval_sha,'0'*64);store.original_run=1;store.release=s.release;store.prior={'wall_seconds':100,'cpu_seconds':50}
        with patch.object(store,'asset',return_value=None),patch.object(store,'put',return_value={'name':'test.mxmenc','ciphertext_sha256':'0'*64}),patch.object(store,'body'),patch.object(w.old,'usage',return_value={'wall_seconds':20,'cpu_seconds':10,'peak_kib':100}):
            prepared=store.prepare(j['report'],j['engine'],1);self.assertEqual(prepared['resources'],{'wall_seconds':120,'cpu_seconds':60,'peak_kib':100})
    def test_missing_recovery_acceptance_denied(self):
        with self.assertRaises(w.n.NumericalStop):a.recovery_document('a'*40)

if __name__=='__main__':unittest.main()
