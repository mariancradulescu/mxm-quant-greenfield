"""Deterministic synthetic-only prearm tests. Zero market CSV parsing."""
import copy
import csv
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile
import numpy as np
from . import worker as w
from . import entrypoint as e

def fixture(days=63,offset=0):
    bars={}
    for k in range(days*288):
        t=w.START+300*k;o=20+offset+.002*(k%113);sign=(-1,0,1)[(k*7+k//12)%3]
        c=o+.001*sign
        bars[t]=dict(timestamp=t,available_at=t+300,open=o,high=max(o,c)+.01,
                     low=min(o,c)-.01,close=c,tick_volume=1+k%17)
    return bars

def raw_fixture(rows=None):
    rows=rows or [('2025-09-16T00:00:00Z',2,3,1,2,3),('2025-09-16T00:05:00Z',2,3,1,2.1,4)]
    f=io.StringIO();writer=csv.writer(f,lineterminator='\n');writer.writerow(['time_utc','open','high','low','close','tick_volume']);writer.writerows(rows)
    raw=f.getvalue().encode()
    expected=dict(symbol_id=3,file='raw/3_M5.csv',series_sha256=w.digest(raw),row_count=len(rows),
                  first_timestamp_utc=rows[0][0],last_timestamp_utc=rows[-1][0])
    return raw,expected

class Offline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clocks=np.arange(w.START,w.START+63*w.DAY,21600,dtype=np.int64)
        cls.bars=fixture();cls.cache=w.derive(cls.bars,cls.clocks)
        cls.other=w.derive(fixture(offset=5),cls.clocks)
        cls.report=w.evaluate([cls.cache,cls.other],[3,7],cls.clocks,w.START,w.START+63*w.DAY)

    def test_01_both_archive_routes_and_all145_identities(self):
        manifest=json.loads(w.MANIFEST.read_bytes());self.assertEqual(len(manifest['primary_series']),145)
        self.assertEqual({manifest['original_capture_sha256'],manifest['delta_capture_sha256']},{x['source_archive_sha256'] for x in manifest['primary_series']})
        raw,x=raw_fixture()
        with tempfile.TemporaryDirectory() as td:
            for name in ('original.zip','delta.zip'):
                p=Path(td)/name
                with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr(x['file'],raw)
                with w.verified_archive(p,w.digest(p.read_bytes())) as z:
                    self.assertEqual(len(w.parse_series(w.accepted_member(z,x),x)),2)

    def test_02_archive_bad_digest(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad.zip';p.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'ARCHIVE_DIGEST'):w.verified_archive(p,'0'*64)

    def test_03_duplicate_zip_member(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'dup.zip'
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                with zipfile.ZipFile(p,'w') as z:z.writestr('a',b'1');z.writestr('a',b'2')
            with self.assertRaisesRegex(ValueError,'DUPLICATE_MEMBER'):w.verified_archive(p,w.digest(p.read_bytes()))

    def test_04_bad_series_and_wrong_member(self):
        raw,x=raw_fixture()
        with self.assertRaisesRegex(ValueError,'SERIES_DIGEST'):w.parse_series(raw+b'\n',x)
        x['file']='raw/7_M5.csv'
        with self.assertRaisesRegex(ValueError,'SOURCE_MEMBER_SCOPE'):w.accepted_member(None,x)

    def test_05_duplicate_source_timestamp(self):
        raw,x=raw_fixture([('2025-09-16T00:00:00Z',2,3,1,2,3)]*2)
        with self.assertRaisesRegex(ValueError,'SOURCE_CHRONOLOGY'):w.parse_series(raw,x)

    def test_06_offgrid_and_outside_domain(self):
        for t in ('2025-09-16T00:01:00Z','2026-09-17T00:00:00Z'):
            raw,x=raw_fixture([(t,2,3,1,2,3)])
            with self.assertRaisesRegex(ValueError,'SOURCE_CHRONOLOGY'):w.parse_series(raw,x)

    def test_07_source_columns_dimensions_and_bad_values(self):
        for rows in [[('2025-09-16T00:00:00Z',2,3,1,2,3,'extra')],
                     [('2025-09-16T00:00:00Z',2,3,1,2,-1)],
                     [('2025-09-16T00:00:00Z',2,3,1,float('nan'),3)],
                     [('2025-09-16T00:00:00Z',4,3,1,2,3)]]:
            raw,x=raw_fixture(rows)
            with self.assertRaises(ValueError):w.parse_series(raw,x)
        raw,x=raw_fixture();raw=raw.replace(b'time_utc',b'wrong');x['series_sha256']=w.digest(raw)
        with self.assertRaisesRegex(ValueError,'SOURCE_COLUMNS'):w.parse_series(raw,x)

    def test_08_mature_label_only(self):
        t=w.START+3600
        for h in w.HORIZONS:
            for lag in w.LAGS:
                with self.assertRaisesRegex(ValueError,'LABEL_NOT_MATURE'):w.response(self.bars,t,h,lag,t+300*h+lag-1)
                self.assertIsNotNone(w.response(self.bars,t,h,lag,t+300*h+lag))

    def test_09_incomplete_horizon_and_late_bar(self):
        t=w.START+7200;bars=dict(self.bars);del bars[t+300]
        self.assertIsNone(w.response(bars,t,12,0,t+3600))
        bars=dict(self.bars);bars[t-300]=dict(bars[t-300],available_at=t+1)
        self.assertEqual(w.features(bars,t,0)[1],'FEATURE_LATE_OR_INVALID')

    def test_10_zero_volume_common_support(self):
        t=w.START+7200;bars=dict(self.bars)
        for ts in range(t-3600,t,300):bars[ts]=dict(bars[ts],tick_volume=0)
        self.assertEqual(w.features(bars,t,0)[1],'ZERO_ACTIVITY_COMMON_ABSTENTION')

    def test_11_features_ignore_future_bars(self):
        t=w.START+7200
        a=w.features(self.bars,t,0)[0];changed={k:dict(v,close=v['open']) if k>=t else v for k,v in self.bars.items()}
        b=w.features(changed,t,0)[0]
        np.testing.assert_array_equal(a[0],b[0]);np.testing.assert_array_equal(a[1],b[1])

    def test_12_future_labels_cannot_change_forecasts(self):
        cache=copy.deepcopy(self.cache);cache['y'][:,:,self.clocks>=w.START+56*w.DAY]+=9
        report=w.evaluate([cache,self.other],[3,7],self.clocks,w.START,w.START+63*w.DAY)
        self.assertEqual([x['forecast_sha256'] for x in report['comparisons']],
                         [x['forecast_sha256'] for x in self.report['comparisons']])
        self.assertNotEqual([x['mean_bounded_score_gain'] for x in report['comparisons']],
                            [x['mean_bounded_score_gain'] for x in self.report['comparisons']])

    def test_13_strict_purge_and_fit_maturity(self):
        for f in self.report['fit_audits']:
            self.assertLess(f['latest_training_maturity'],f['refit'])
            self.assertLess(f['latest_training_clock']+245*60,f['refit'])
            totals=f['identity_weight_totals'];self.assertAlmostEqual(sum(totals.values()),1)
            self.assertTrue(all(abs(v-1/len(totals))<1e-12 for v in totals.values()))

    def test_14_future_label_contamination_rejected(self):
        t=np.array([w.START]);b=np.zeros((1,10));p=np.zeros((1,2))
        with self.assertRaisesRegex(ValueError,'LABEL_MATURITY_ORDER'):
            w.fit_family(t,t,np.array([3]),b,p,np.ones(1),np.ones(1,bool),w.START+56*w.DAY,w.START)

    def test_15_full_family_and_paired_equality(self):
        self.assertEqual(len(self.report['comparisons']),18)
        for i in range(0,18,3):
            triple=self.report['comparisons'][i:i+3]
            self.assertEqual(len({x['paired_supported'] for x in triple}),1)
            self.assertEqual(len({x['forecast_sha256'] for x in triple}),1)
        self.assertEqual(self.report['inference_class'],'EXPLORATORY_ONLY_NO_FORMAL_REJECTION')
        self.assertFalse(self.report['alpha_allocated'])

    def test_16_fixed_cross_symbol_weights_and_bounded_scores(self):
        for x in self.report['comparisons']:
            self.assertAlmostEqual(np.mean(x['identity_gain_fixed_calendar']),x['mean_bounded_score_gain'])
            self.assertEqual(x['fixed_opportunities'],28*2)
            self.assertTrue(np.max(np.abs(x['calendar_gain']))<=1)
            self.assertIsNone(x['formal_p_value']);self.assertIsNone(x['formal_rejection'])
        self.assertEqual(np.shape(self.report['descriptive_common_calendar_covariance']),(18,18))

    def test_17_all_unsupported_and_missing_emit18(self):
        cache=copy.deepcopy(self.cache);cache['feature_ok'][:]=False
        report=w.evaluate([cache],[3],self.clocks,w.START,w.START+63*w.DAY)
        self.assertEqual(len(report['comparisons']),18)
        self.assertTrue(all(x['status']=='UNSUPPORTED' and x['mean_bounded_score_gain']==0 for x in report['comparisons']))

    def test_18_no_real_reader_without_capability(self):
        with self.assertRaisesRegex(ValueError,'SEPARATE_ARM_REQUIRED'):w.read_production('/does/not/exist','/does/not/exist',None)

    def test_19_no_real_open_before_independent_key(self):
        with tempfile.TemporaryDirectory() as td,patch.object(e,'KEY',Path(td)/'absent'):
            with self.assertRaisesRegex(ValueError,'INDEPENDENT_VERIFICATION_KEY_NOT_INSTALLED'):e.authorize('/unsigned/arm.json')

    def test_20_arm_exact_head_scope_and_limits(self):
        payload=dict(schema='mxm.primary145.single-exploratory-arm.v1',independent_preexecution_audit='APPROVED',execution_head='a'*40,
                     repository=e.REPO,branch=e.BRANCH,campaign='PRIMARY145_EXPLORATORY_DEV_V1_SINGLE_PASS',
                     inference_class='EXPLORATORY_ONLY_NO_FORMAL_REJECTION',limits=e.LIMITS.copy(),files_sha256={'x':'h'},
                     archive_directory='/a',checkpoint_directory='/c',output_file='/o')
        self.assertTrue(e.validate_payload(payload,'a'*40,'a'*40,{'x':'h'}))
        for key,val in [('execution_head','b'*40),('limits',{}),('files_sha256',{}),('independent_preexecution_audit','PENDING'),('archive_directory','relative')]:
            bad=dict(payload,**{key:val})
            with self.assertRaises(ValueError):e.validate_payload(bad,'a'*40,'a'*40,{'x':'h'})

    def test_21_clock_no_compression(self):
        self.assertEqual(len(w.CLOCK[w.CLOCK>=w.START+56*w.DAY]),1240)
        self.assertTrue(np.all(np.diff(self.report['score_clock_utc_epoch'])==21600))

    def test_22_both_structural_maps_and_baseline_direct_parity(self):
        from research_core_v4.main_reentry_v1.offline_falsification import fabricated_hour,diagnostic_maps
        a=fabricated_hour([1,3,1]+[3]*9);b=fabricated_hour([1,1]+[3]*10)
        self.assertEqual(w.baseline(10800,a),w.baseline(10800,b))
        self.assertNotEqual(diagnostic_maps(a),diagnostic_maps(b))

    def test_23_archive_decrypt_crc_failure_not_replaced(self):
        raw,x=raw_fixture()
        class BadArchive:
            def read(self,path):raise RuntimeError('Bad password / bad CRC')
        with self.assertRaises(RuntimeError):w.accepted_member(BadArchive(),x)

    def test_24_signature_tampering_and_forged_capability(self):
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
        from cryptography.exceptions import InvalidSignature
        key=Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        public=key.public_key().public_bytes(Encoding.PEM,PublicFormat.SubjectPublicKeyInfo)
        payload={'execution_head':'a'*40}
        envelope={'payload':payload,'signature_base64':base64.b64encode(key.sign(e.canonical(payload))).decode()}
        e.verify_signature(public,envelope)
        envelope['payload']={'execution_head':'b'*40}
        with self.assertRaises(InvalidSignature):e.verify_signature(public,envelope)
        with self.assertRaisesRegex(ValueError,'SIGNED_GATE_CAPABILITY_REQUIRED'):e.Permit({},'fake')

    def test_25_crash_reservation_prevents_second_invocation(self):
        with tempfile.TemporaryDirectory() as td:
            payload={'checkpoint_directory':td,'execution_head':'a'*40}
            e.reserve_invocation(payload)
            state=json.loads((Path(td)/'INVOCATION_CONSUMED.json').read_bytes())
            self.assertEqual(state['CPU_budget_reserved_seconds'],7200)
            with self.assertRaises(FileExistsError):e.reserve_invocation(payload)

    def test_26_negative_results_are_emitted(self):
        negative=[x for x in self.report['comparisons'] if x['mean_bounded_score_gain']<0]
        self.assertGreater(len(negative),0)
        self.assertEqual(len(self.report['comparisons']),18)

if __name__=='__main__':unittest.main(verbosity=2)
