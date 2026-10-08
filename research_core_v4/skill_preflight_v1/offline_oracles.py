"""Deterministic forensic oracles. No generator, market reader or campaign run.

Historical git reads below are Boolean masks and already published synthetic
counts only. No OHLC, market response, protected row or secret is read.
"""
import hashlib
import io
import json
import math
from pathlib import Path
from fractions import Fraction as F
import socket
import subprocess
import unittest
import numpy as np
from research_core_v4.compact_baseline_v2 import baseline
from research_core_v4.prospective_exact_semantics_v3 import feature
from research_core_v4.main_reentry_v1.offline_falsification import fabricated_hour, diagnostic_maps, receipt_worlds_witness
from research_core_v4.operational_v1 import inference as engine

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
S = 'research_core_v4/state/'

def git_bytes(head, path):
    return subprocess.check_output(['git', 'show', head+':'+path], cwd=ROOT)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def fifth_map(t, peers):
    """Literal frozen cross-sectional Phi law, not an existing numeric runner.
    Caller supplies entry-frozen, same-context peers excluding own identity.
    The V2 production code implemented masks; it did not compute this Phi.
    """
    coords = [b[5] for rows in peers if (b := baseline(t, rows)) is not None]
    if len(coords) < 2:
        return None
    mu = sum(map(F, coords))/len(coords)
    variance = sum((F(x)-mu)**2 for x in coords)/len(coords)
    # Squared Phi is injective on the nonnegative domain and exact rational.
    return variance

def direct_parity():
    t = 10800
    prev = [dict(x, timestamp=x['timestamp']-3600,
                 available_at=x['available_at']-3600) for x in fabricated_hour([3]*12)]
    a = prev+fabricated_hour([1,3,1]+[3]*9)
    b = prev+fabricated_hour([1,1]+[3]*10)
    peers = [fabricated_hour([1]*12), fabricated_hour([3]*12)]
    names = ['MULTISCALE_PRICE_STATE','BROKER_NATIVE_ACTIVITY_STATE',
             'VOLATILITY_AND_REALIZED_VARIANCE_STATE','REGIME_AND_STRUCTURAL_BREAK_STATE']
    maps = {s: {'A':str(feature(s,t,a)), 'B':str(feature(s,t,b)),
                'equal':feature(s,t,a)==feature(s,t,b)} for s in names}
    maps['CROSS_SECTIONAL_RELATIVE_STATE'] = {
        'A_squared_Phi':str(fifth_map(t,peers)),
        'B_squared_Phi':str(fifth_map(t,peers)), 'equal': True,
        'route':'literal frozen authority; squared Phi equality implies Phi equality'}
    assert baseline(t,a)==baseline(t,b) and all(v['equal'] for v in maps.values())
    assert diagnostic_maps(a[-12:]) != diagnostic_maps(b[-12:])
    return {'baseline_equal':True,'all_five_equal':True,'maps':maps,
            'new_maps_A':list(map(str,diagnostic_maps(a[-12:]))),
            'new_maps_B':list(map(str,diagnostic_maps(b[-12:]))),
            'scope':'finite legal-domain structural witness, not forecasting evidence'}

def independent_wilson(k,n,z):
    # Solve the quadratic score-test inequality (n+z²)p²-(2k+z²)p+k²/n<=0.
    a=n+z*z; b=-(2*k+z*z); c=k*k/n
    return (-b-math.sqrt(b*b-4*a*c))/(2*a),(-b+math.sqrt(b*b-4*a*c))/(2*a)

def historical():
    h='4cefedb84841639781381c2afc4f3ac4d12d98a5'
    a=json.loads((ROOT/S/'STRICT_PREOUTCOME_OPERATIONAL_V2_STAGE7_RECOVERY224_FINAL_CANONICAL_STATE_V1.json').read_text())
    path='support_depth_v2/stage7/cumulative/daily_score_mask.npy'
    raw=git_bytes(h,path); assert sha(raw)==a['frozen_files_sha256'][path]
    m=np.load(io.BytesIO(raw),allow_pickle=False)
    assert m.dtype==bool and m.shape==(168,261) and sha(m.tobytes())==a['daily_score_mask_sha256']
    blocks=m.reshape(24,7,261).any(1)
    ok=(blocks.sum(0)>=12)
    for start,end in [(0,8),(8,16),(16,24)]: ok &= blocks[start:end].sum(0)>=4
    assert int(ok.sum())==242
    p=json.loads(git_bytes(h,'support_depth_v2/stage7/power.json'))
    assert sha(git_bytes(h,'support_depth_v2/stage7/power.json'))==a['referenced_result_files_sha256']['support_depth_v2/stage7/power.json']
    eligible=np.all(np.array([p['cases'][c]['wilson_lowers'] for c in ['NORMAL','AR025','AR050']])>=.8,axis=0)
    assert not eligible.any() and not p['shared_ready']
    for c in ['NORMAL','AR025','AR050']:
        cell=p['cases'][c]
        oracle=[independent_wilson(k,16384,4.669289888046892)[0] for k in cell['counts']]
        assert np.allclose(oracle,cell['wilson_lowers'],rtol=0,atol=2e-14)
    rraw=git_bytes('ba6557481f3c32f5d07cf841dac3d9b280f1e4f9','extended_certification/result.json')
    assert sha(rraw)=='9449b231be6870d8052177174b819c7355f725133abcdc121ab371afd7e0d729'
    r=json.loads(rraw); upper=independent_wilson(714,16384,r['wilson_z'])[1]
    assert r['false_complete_lead_count']==714 and not r['pass'] and abs(upper-r['simultaneous_wilson_upper'])<1e-14
    # AR050 daily generator uses rho=.5. Exact stationary adjacent-week correlation.
    var=sum(F(1,2)**abs(i-j) for i in range(7) for j in range(7))
    cov=sum(F(1,2)**(7+j-i) for i in range(7) for j in range(7))
    return {'Stage7_mask_shape':list(m.shape),'structurally_supported':int(ok.sum()),
            'joint_power_eligible':int(eligible.sum()),'all_783_stored_power_lower_bounds_match_oracle':True,
            'AR050_count':714,'trials':16384,'rate':714/16384,'Wilson_upper':upper,'verdict_preserved':'FAIL',
            'AR050_adjacent_week_mean_correlation':str(cov/var),
            'AR050_week_independence':False,'new_null_trials':0,'mask_file_sha256':sha(raw)}

def score_range(pb,pa):
    if not all(math.isfinite(v) and -8<=v<=8 for v in (pb,pa)):
        raise ValueError('FORECAST_NOT_BOUNDED')
    vals=[((y-pb)**2-(y-pa)**2)/256 for y in (-8,8)]
    return min(vals),max(vals)

def fixed_radius(n,alpha,family):
    if n<1 or not 0<alpha<1 or family<1: raise ValueError('BOUND_INPUT')
    return math.sqrt(2*math.log(family/alpha)/n)

class Oracles(unittest.TestCase):
    def test_01_direct_five_map_parity(self): self.assertTrue(direct_parity()['all_five_equal'])
    def test_02_fifth_map_requires_two_peers(self): self.assertIsNone(fifth_map(10800,[fabricated_hour([3]*12)]))
    def test_03_receipt_is_unknown(self): self.assertEqual(receipt_worlds_witness()['archive_receipt_status'],'UNKNOWN')
    def test_04_old_calendar_guard_is_exact_known_defect(self):
        old=(ROOT/'research_core_v4/operational_v2/masks.py').read_bytes()
        new=(ROOT/'research_core_v4/operational_v2/masks_calendar224_v1.py').read_bytes()
        self.assertEqual(old.replace(b'28<=days<=196',b'28<=days<=224'),new)
        self.assertFalse(28<=224<=196); self.assertTrue(28<=224<=224)
    def test_05_recovery_uses_successor_and_first64(self):
        s=(ROOT/'research_core_v4/operational_v2_extended/resume_stage7_attempt2_v1.py').read_text()
        self.assertIn('masks_calendar224_v1',s); self.assertIn('range(64,',s)
    def test_06_historical_mask_and_counts_not_replayed(self): self.assertEqual(historical()['structurally_supported'],242)
    def test_07_bootstrap_algebra_against_scalar_oracle(self):
        x=np.array([[[((d*3+l*5)%17)-8 for l in range(3)] for d in range(84)]],float)
        mask=np.ones_like(x,bool); mask[:,7:14,1]=False
        g=engine.cluster(x,mask)
        bank=np.array([[1 if (b+r)%3 else -1 for b in range(12)] for r in range(4)],float)
        # Keep all three supported for rank comparison; support fixture separately.
        g['support'][:]=True
        expected=[]
        for signs in bank:
            tt=[]
            for l in range(3):
                z=g['u'][0,:,l]*signs; z=z[g['valid'][0,:,l]]
                se=z.std(ddof=1)/math.sqrt(len(z))
                tt.append(z.mean()/se)
            expected.append(max(tt))
        np.testing.assert_allclose(engine.bootstrap_max(g,bank)[0],sorted(expected),rtol=1e-12,atol=1e-12)
    def test_08_mask_does_not_compress_calendar_thirds(self):
        x=np.arange(168,dtype=float).reshape(1,168,1);mask=np.ones_like(x,bool);mask[:,56:112]=False
        g=engine.cluster(x,mask);self.assertFalse(g['support'][0,0]);self.assertEqual(g['n'][0,0],16)
    def test_09_local_shift_reference_invariant(self):
        x=np.arange(84,dtype=float).reshape(1,84,1);m=np.ones_like(x,bool)
        a=engine.cluster(x,m);b=engine.cluster(x+3,m)
        np.testing.assert_allclose(a['u'],b['u']);np.testing.assert_allclose(a['se'],b['se'])
    def test_10_rank_ties_and_any_leaf(self):
        g={'mu':np.array([[0.,1.]]),'se':np.ones((1,2)),'support':np.ones((1,2),bool),'third':np.ones((1,3,2))}
        ref=np.array([[-1.,0.,1.,1.]])
        _,_,p,_=engine.decisions(g,ref,np.zeros((1,2)))
        np.testing.assert_allclose(p,[[4/5,3/5]])
        lead=np.array([[True,True],[False,True],[False,False]])
        self.assertEqual(int(lead.any(1).sum()),2);self.assertEqual(int(lead.sum()),3)
    def test_11_score_boundedness_and_predictable_range(self):
        for pb in [-8,-3,0,4,8]:
            for pa in [-8,-3,0,4,8]:
                lo,hi=score_range(pb,pa);self.assertTrue(-1<=lo<=0<=hi<=1)
                self.assertAlmostEqual(hi-lo,abs(pa-pb)/8)
                for y in [-8,-2,0,7,8]:self.assertTrue(lo-1e-14<=((y-pb)**2-(y-pa)**2)/256<=hi+1e-14)
    def test_12_bad_forecast_fails(self):
        for v in [9,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):score_range(v,0)
    def test_13_fixed_look_beats_unneeded_spending(self):
        n=1240;self.assertLess(fixed_radius(n,.025,18),math.sqrt(2*math.log(18*n*(n+1)/.025)/n))
    def test_14_serial_dependence_not_iid(self):
        v=sum(F(1,2)**abs(i-j) for i in range(7) for j in range(7))
        self.assertGreater(v,7)
    def test_15_selection_changes_filtration(self):
        # One fair sign: selecting A=X after observation yields A*X=1 always.
        atoms=[(-1,F(1,2)),(1,F(1,2))]
        self.assertEqual(sum(x*w for x,w in atoms),0)
        self.assertEqual(sum(x*x*w for x,w in atoms),1)
        # Already knowing X in F0 makes its conditional drift X, not zero.
    def test_16_historical_hash_inventory_unchanged(self):
        inv=json.loads((ROOT/'research_core_v4/main_reentry_v1/INPUT_BINDINGS_V1.json').read_text())
        for p,h in inv['files_sha256'].items():self.assertEqual(sha((ROOT/p).read_bytes()),h,p)
    def test_17_local_family_cannot_pay_unknown_prior_selection(self):
        # Algebra only: n fair signs, 2^n fixed sign-vector score algorithms.
        # Each fixed algorithm has mean-zero score. The retrospectively selected
        # matching vector scores +1 in every position, in every possible world.
        n=16; alpha=.025
        self.assertLess(fixed_radius(n,alpha,1),1)
        self.assertGreater(fixed_radius(n,alpha,2**n),1)
    def test_18_prefix_fit_maturity_and_shared_baseline(self):
        from research_core_v4.operational_v1.prequential_score import fit_prefix,predict,DAY
        t=np.arange(0,57*DAY,21600,dtype=np.int64)
        maturity=t+3600
        ids=np.arange(len(t))%3
        b=np.array([[((k+1)*(j+3)%19)/19 for j in range(10)] for k in range(len(t))])
        phi=np.array([[((k+7)%11)/11,((k+5)%13)/13] for k in range(len(t))])
        y=np.array([((k*7)%23-11)/23 for k in range(len(t))])
        f=fit_prefix(t,maturity,ids,b,phi,y,np.ones(len(t),bool),56*DAY,0)
        self.assertIsNotNone(f);self.assertTrue(np.all(maturity[f.train_indices]<f.refit))
        self.assertTrue(np.all(t[f.train_indices]+245*60<f.refit))
        pb,pa=predict(f,b[-1],phi[-1]);self.assertTrue(-8<=pb<=8 and -8<=pa<=8)
        before=f.beta_b.copy();alter=y.copy();alter[t>=f.refit]=9999
        ff=fit_prefix(t,maturity,ids,b,phi,alter,np.ones(len(t),bool),56*DAY,0)
        np.testing.assert_array_equal(before,ff.beta_b);np.testing.assert_array_equal(f.beta_aug,ff.beta_aug)
        self.assertTrue(np.all(f.weights>0));self.assertAlmostEqual(float(f.weights.sum()),1)

def main():
    def deny(*a,**k): raise RuntimeError('OFFLINE_ONLY')
    socket.socket=socket.create_connection=socket.getaddrinfo=deny
    result=unittest.TestResult();unittest.defaultTestLoader.loadTestsFromTestCase(Oracles).run(result)
    out={'tests_run':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors),
         'failures':[{'test':str(t),'traceback':s} for t,s in result.failures],
         'errors':[{'test':str(t),'traceback':s} for t,s in result.errors],
         'direct_parity':direct_parity(),'historical':historical(),
         'analytic_geometry_only':{'family_proposal':18,'n_calendar_ceiling':1240,'alpha_example_not_project_allocation':.025,
                                  'fixed_radius':fixed_radius(1240,.025,18),
                                  '80pct_sufficient_drift':fixed_radius(1240,.025,18)+math.sqrt(2*math.log(5)/1240),
                                  'n_for_0_01_radius':math.ceil(2*math.log(18/.025)/.01**2)},
         'ingress':{'market_rows':0,'real_responses':0,'new_null_trials':0,'broker_requests':0,'protected_rows':0},
         'scope':'deterministic algebraic oracles and stored-result reconciliation only'}
    (HERE/'OFFLINE_RESULT_V1.json').write_text(json.dumps(out,sort_keys=True,indent=2)+'\n')
    print(json.dumps(out,sort_keys=True))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
