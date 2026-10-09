"""New scientific and adapter boundaries only, no old crash-campaign replay."""
import copy,json,math,unittest
from unittest.mock import patch
from research_core_v4.diverse_mechanism_wave_v1 import kernel_v1 as k,worker_v1 as w,authority_v1 as a,synthetic_v1 as s
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n
from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob,PublicDisclosureDenied,ROOT

def buffer(variant=0):
    return {n.canonical.timestamp(r['time_utc']):n._bar(r,2)[1] for r in s.rows(variant+1,2)}

class Scientific(unittest.TestCase):
    def test_range_long_and_activity_exhaustion_short(self):
        d,valid=k.directions(buffer(),n.START+3*3600,0)
        self.assertTrue(valid);self.assertEqual(d[k.MECHANISMS[0]][0],1);self.assertEqual(d[k.MECHANISMS[1]][0],-1)
    def test_true_short_and_activity_exhaustion_long(self):
        b=buffer()
        for x in b.values():
            o,c,h,l=x['open'],x['close'],x['high'],x['low']
            x.update(open=2000-o,close=2000-c,high=2000-l,low=2000-h)
        d,_=k.directions(b,n.START+3*3600,0);self.assertEqual(d[k.MECHANISMS[0]][0],-1);self.assertEqual(d[k.MECHANISMS[1]][0],1)
    def test_precise_positive_and_negative_responses(self):
        for variant,sign in [(0,1),(1,-1)]:
            b=buffer(variant);t=n.START+3*3600;y,why=n.frozen.response(b,t,0,t+3600,n.END)
            expected=math.log(b[t+3300]['close']/b[t-300]['close'])
            self.assertEqual(y,expected);self.assertEqual(why,'SUPPORTED');self.assertEqual(1 if y>0 else -1,sign)
    def test_no_event_flat_features(self):
        d,valid=k.directions(buffer(5),n.START+3*3600,0);self.assertTrue(valid);self.assertTrue(all(x==(None,'NO_EVENT') for x in d.values()))
    def test_zero_activity_does_not_disable_price_mechanism(self):
        d,_=k.directions(buffer(3),n.START+3*3600,0);self.assertEqual(d[k.MECHANISMS[0]][0],1);self.assertEqual(d[k.MECHANISMS[1]],(None,'ZERO_ACTIVITY'))
    def test_missing_feature_and_market_closed_period(self):
        for variant in (2,4):
            d,valid=k.directions(buffer(variant),n.START+3*3600,0);self.assertFalse(valid);self.assertTrue(all(x==(None,'FEATURE_GAP') for x in d.values()))
    def test_late_feature_no_stale_substitution(self):
        b=buffer();t=n.START+3*3600;b[t-300]['available_at']=t+1
        d,valid=k.directions(b,t,0);self.assertFalse(valid);self.assertTrue(all(x==(None,'FEATURE_RECEIPT') for x in d.values()))
    def test_future_rows_do_not_change_features(self):
        b=buffer();t=n.START+3*3600;before=k.directions(b,t,0)
        for ts in list(b):
            if ts>=t:b[ts]={'timestamp':ts,'available_at':ts+300,'open':999.,'high':1000.,'low':998.,'close':999.,'tick_volume':999}
        self.assertEqual(before,k.directions(b,t,0))
    def test_all_lags_chronology(self):
        b=buffer();t=n.START+4*3600
        for lag in k.LAGS:
            hs,reason=k.hours(b,t,lag);self.assertIsNotNone(hs);self.assertEqual(reason,'FEATURE_VALID')
            h=3600*((t-lag)//3600)-3600;self.assertEqual(hs[1]['c'],b[h+3300]['close'])
    def test_label_gap(self):
        b=buffer();t=n.START+3*3600;del b[t+300];self.assertEqual(n.frozen.response(b,t,0,t+3600,n.END),(None,'LABEL_GAP'))
    def test_label_receipt_and_maturity(self):
        b=buffer();t=n.START+3*3600
        with self.assertRaises(ValueError):n.frozen.response(b,t,900,t+3600,n.END)
        b[t+3300]['available_at']=t+3600+1
        self.assertEqual(n.frozen.response(b,t,900,t+3600+900,n.END),(None,'LABEL_RECEIPT'))
    def test_domain_censor(self):
        self.assertEqual(n.frozen.response({},n.END-3600,900,n.END+900,n.END),(None,'DOMAIN_CENSOR'))
    def test_invalid_and_nonfinite_ohlc_fail_closed(self):
        for mutate in (lambda x:x.update(low=-1),lambda x:x.update(close=float('nan'))):
            b=buffer();mutate(b[n.START+3600])
            with self.assertRaises(n.NumericalStop):k.directions(b,n.START+3*3600,0)
    def test_grid_and_timestamp_integrity(self):
        with self.assertRaises(n.NumericalStop):k.directions(buffer(),n.START+3*3600+1,0)
        with self.assertRaises(n.NumericalStop):k.directions(buffer(),n.START+3*3600,301)
        b=buffer();b[n.START+3600]['timestamp']+=300
        with self.assertRaises(n.NumericalStop):k.directions(b,n.START+3*3600,0)
    def test_distinct_from_weighted_sign_A_and_inverse(self):
        # Equal positive weighted M5 signs can have different two-hour
        # elasticity events; range and elasticity laws are not +/-old A.
        b=buffer();t=n.START+3*3600;d,_=k.directions(b,t,0)
        for ts,x in b.items():
            if n.START+7200<=ts<n.START+10800:x['tick_volume']=1
        d2,_=k.directions(b,t,0)
        self.assertEqual(d[k.MECHANISMS[0]][0],d2[k.MECHANISMS[0]][0]);self.assertEqual(d[k.MECHANISMS[1]][0],-1);self.assertIsNone(d2[k.MECHANISMS[1]][0])

class Boundaries(unittest.TestCase):
    def test_public_identity_new_design_and_kernel(self):
        doc=w.safe_status('a'*40,'SYNTHETIC','PASS',failure_code='NONE');raw=validate_public_blob(ROOT+'DIVERSE_WAVE_SYNTHETIC_COMPLETION_V1.json',doc)
        self.assertEqual(json.loads(raw)['scientific_design_sha256'],a.DESIGN_SHA);self.assertEqual(json.loads(raw)['worker_sha256'],a.digest(a.KERNEL))
    def test_public_vectors_and_raw_rows_denied(self):
        for field in ('identity_results','full_frontier','rows','private_key','lag_vectors'):
            doc=w.safe_status('a'*40,'FINAL','PASS');doc[field]=[]
            with self.assertRaises(PublicDisclosureDenied):validate_public_blob(ROOT+'DIVERSE_WAVE_REAL_COMPLETION_V1.json',doc)
    def test_real_missing_acceptance_denied(self):
        with self.assertRaises(n.NumericalStop):a.real_gate('a'*40)
    def test_design_and_source_cannot_silently_change(self):
        arm=a.candidate('a'*40,{},'synthetic');arm['scope']=dict(arm['scope']);arm['scope']['comparisons']=3
        with self.assertRaises(n.NumericalStop):a.validate_candidate('b'*40,arm,'synthetic')
    def test_original_invocation_different(self):a.unavailable_acceptance_preflight()
    def test_new_support_reason_accounting(self):
        m=w.metrics();w.tally(m,None,'NO_EVENT',True,False);z=w.summary(m,1)
        self.assertEqual(z['supported'],0);self.assertIsNone(z['gross_supported_bps']);self.assertEqual(z['gross_calendar_bps'],0)
        with self.assertRaises(n.NumericalStop):w.summary(m,2)
    def test_fabricated_source_parser_and_hash_and_ordinal_rejection(self):
        master,entries,digits,manifest=w.old.verify_science();raw,meta=s.fabricated_shard(0,master,digits);cipher=b'test-cipher';meta['ENCRYPTED_ASSET_SHA256']=a.sha(cipher)
        engine=w.new(master);self.assertEqual(w.consume(engine,raw,meta,master,digits,cipher),meta['ROW_COUNT'])
        with self.assertRaises(n.NumericalStop):w.consume(w.new(master),raw,meta,master,digits,b'wrong')
        obj=json.loads(raw);obj['items'][0]['ordinal']=2;bad=n.canonical.canonical(obj);mm=dict(meta,PLAINTEXT_CANONICAL_SHA256=a.sha(bad))
        with self.assertRaises(n.NumericalStop):w.consume(w.new(master),bad,mm,master,digits,cipher)
    def test_all1576_accounting_six_cells_four_weeks(self):
        master,entries,digits,manifest=w.old.verify_science();engine=w.new(master);processed=[];rows=0
        for idx in range(2):
            raw,meta=s.fabricated_shard(idx,master,digits);cipher=b'test';meta['ENCRYPTED_ASSET_SHA256']=a.sha(cipher);w.consume(engine,raw,meta,master,digits,cipher);rows+=meta['ROW_COUNT'];processed.append(w.v2.source_record(idx,meta))
        arm=a.candidate('a'*40,{},'synthetic');r=w.report(engine,rows,2,processed,arm)
        self.assertEqual(len(r['identity_results']),1576);self.assertEqual(r['identity_results'][514]['symbol_id'],3741);self.assertEqual(r['identity_results'][514]['rows'],0)
        for lag in map(str,k.LAGS):
            self.assertEqual(len(r['four_weeks'][lag]),4)
            for m in k.MECHANISMS:
                cell=r['full_frontier'][lag][m];self.assertEqual(cell['calendar'],1059072);self.assertGreater(cell['supported'],0);self.assertEqual(sum(x[m]['supported'] for x in r['four_weeks'][lag]),cell['supported'])
        from types import SimpleNamespace
        store=SimpleNamespace(arm=arm,approval_sha='b'*64,original_run=1,mode='synthetic',release={'target_commitish':'c'*40})
        j={'schema':'mxm.numeric.finalization.input.v3','arm_sha256':a.sha(a.enc(arm)),'approval_sha256':'b'*64,'invocation_id':arm['invocation_id'],'bindings':arm['bindings'],'original_run':1,'source_head':'c'*40,'engine':engine,'report':r}
        w.validate_journal(store,j)
        for key,value in [('invocation_id','0'*64),('approval_sha256','0'*64),('bindings',{'wrong':'0'*64})]:
            bad=dict(j);bad[key]=value
            with self.assertRaises(n.NumericalStop):w.validate_journal(store,bad)
        for key,value in [('design_sha256','0'*64),('input_shards',100),('rows',rows+1),('mechanisms',list(k.MECHANISMS)[:1])]:
            bad=dict(j);bad['report']=dict(r);bad['report'][key]=value
            with self.assertRaises(n.NumericalStop):w.validate_journal(store,bad)
        bad=dict(j);bad['report']=dict(r);bad['report']['identity_results']=r['identity_results'][:-1]
        with self.assertRaises(n.NumericalStop):w.validate_journal(store,bad)

if __name__=='__main__':unittest.main()
