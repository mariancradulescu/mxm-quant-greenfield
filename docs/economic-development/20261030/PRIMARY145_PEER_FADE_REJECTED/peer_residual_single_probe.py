"""ONE distinct, frozen PEER-DISLOCATION-FADE annual DEVELOPMENT hypothesis.

Inputs: existing independently original-archive-hash-validated causal hourly M5
feature tensors. NO inputs from the earlier Ridge model's fitted coefficients,
predictions, or chosen episodes. No funding, no historical BID/ASK or real fills.

Frozen before reading any economic label: use 60m normalized causal returns
r12 (X[:,2]); same broker-native asset class contemporaneous median with
>=5 available peers; require absolute own-minus-peer residual >= 2.5 sigma;
one strongest available proposal across all 145 per common hourly slot; fade
sign of residual, execute at next-bar-delay open, exit 8 M5 bars later.
No using future-availability for candidate eligibility or ranking. Account
serial, no overlapping 40m positions, one position max. Entire previously
studied 2026-06-08..09-16 chronology treated as DEVELOPMENT_ONLY.
"""
from pathlib import Path
from collections import Counter,defaultdict
import datetime as dt,hashlib,json
import numpy as np
ROOT=Path('/mnt/data/mxm_primary145_originals')
Z={'base':'MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip','delta':'MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip'}
ZIP_SHA={'base':'09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259',
 'delta':'37a47cb9ff8bc9cce50aee830c1bd286b9db359df1200d4e4b9a0ce35f8fd12e'}
# Broker-native context from immutable MASTER1576_V2_DEEP_HISTORICAL_M5_ELIGIBLE_ROSTER_V1.json;
# all 145 PRIMARY symbol IDs included; no outcome-driven class exclusion.
GROUPS={
 'Forex (Spot)':[3,7,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,37,39,40,43,44,46,47,49,50,51,54,60,61,64,75,82,84,86,87,91,98,118,134,2762,2763,2764,2765,2766,2767,2768,2769,2770,2771,2772,2773,2774,2775,2776,2777,2779,2780,2781,2783,2785,2786,2788],
 'Metals (Spot)':[41,93,95,97,104,255,256,262,2753],
 'Currency Index (Spot)':[110,146], 'Indices (Spot)':[116,117],
 'Crypto Currency (Spot)':[130,284,286,323,324,326,888,2083,2086,2737,2738,2739,2740,2742,2744,2746,7186,7187,7188,7189,7190,7191,7192,7193,7194,7195,7196,7198,7285,7286],
 'Energies (Spot)':[251], 'Forwards - Indices':[2917,2926], 'Forwards - Commodities':[2924],
 'US Equities':[2998,2999,3000,3002,3019,3020,3025,3027,3029,3032,3033,3034,5402,5403,5406,5410,5411,5414,5424,5449,5470],
 'Perpetual Commodity':[7393,7394]}
assert len(set(sum(GROUPS.values(),[])))==145
SID_CLASS={sid:cl for cl,lst in GROUPS.items() for sid in lst}
THRESHOLD_SIGMA=2.5
MIN_SAME_CLASS=5
COST_STRESS_BPS=(10.,20.,40.)
TRAIN_END='2026-06-01T00:00:00Z'  # historical Ridge train cutoff only for comparability, NOT used to fit this rule
DEVELOPMENT_START='2026-06-08T00:00:00Z'
DEVELOPMENT_END='2026-09-17T00:00:00Z'
PARTIAL_WEEK='2026-W38'
DURABLE_IDS=tuple(sorted(ROOT.glob('features-*.npz')))
assert len(DURABLE_IDS)==5
utc=lambda stamp:int(dt.datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp())

def choose_at_one_clock(entries):
    """entry: (sid,class,causal_1h_vol_normalized_return, future, outcome)
    ranking must never read `future` or `outcome`.
    """
    groups=defaultdict(list)
    for e in entries:
        sid,cl,z,future,outcome=e
        assert SID_CLASS[sid]==cl and np.isfinite(z)
        groups[cl].append(e)
    scores=[]
    for cl,peers in groups.items():
        if len(peers)<MIN_SAME_CLASS:continue
        median=float(np.median([p[2] for p in peers]))
        for e in peers:
            residual=float(e[2]-median)
            if abs(residual)>=THRESHOLD_SIGMA:
                scores.append((abs(residual),int(e[0]),int(-np.sign(residual)),e))
    if not scores:return None
    # Stable and future-blind max, ties to lowest symbol_id
    scores.sort(key=lambda row:(-row[0],row[1]))
    magnitude,sid,side,entry=scores[0]
    return {'symbol_id':sid,'class':entry[1], 'causal_peer_residual_z':float(magnitude),
      'side':int(side),'future_observed':bool(entry[3]),
      'gross_bps':float(side*entry[4]) if entry[3] else None,
      'eligible_class_peers':len(groups[entry[1]])}


def selftest():
    s=GROUPS['Forex (Spot)'][:6];base=[(x,'Forex (Spot)',0.,True,100.) for x in s]
    a=[*base[:-1],(s[-1],'Forex (Spot)',5.,False,99999.)]
    b=[*base[:-1],(s[-1],'Forex (Spot)',5.,True,-99999.)]
    assert choose_at_one_clock(a)['symbol_id']==choose_at_one_clock(b)['symbol_id']==s[-1]
    assert choose_at_one_clock(a)['gross_bps'] is None
    assert choose_at_one_clock(b)['gross_bps']==99999.
    assert choose_at_one_clock(base) is None
    assert choose_at_one_clock(a[:4]) is None
    print('PEER_RESIDUAL_CAUSAL_SELFTEST_OK')

if __name__=='__main__':
    import sys
    if '--selftest' in sys.argv:selftest();sys.exit(0)
    # No label access until code is frozen and test passed. Manifest of source files
    # here consists of deterministic feature-cache hashes, not new originals.
    selftest()
    parts=[];shas={}
    for p in DURABLE_IDS:
        shas[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
        with np.load(p,allow_pickle=False) as z:
            parts.append({k:z[k] for k in ('X','y','t','sid','future')})
    D={k:np.concatenate([p[k] for p in parts]) for k in ('X','y','t','sid','future')}
    t=D['t'];mask=(t>=utc(DEVELOPMENT_START))&(t<utc(DEVELOPMENT_END))
    T=t[mask];S=D['sid'][mask];X=D['X'][mask,2];Y=D['y'][mask];F=D['future'][mask]
    assert len(set(S.tolist()))==145 and np.all((np.isfinite(Y))==F)
    order=np.argsort(T,kind='stable');T=T[order];S=S[order];X=X[order];Y=Y[order];F=F[order]
    dates,starts,nrows=np.unique(T,return_index=True,return_counts=True)
    picks=[]
    for k,start,n in zip(dates,starts,nrows):
        e=[(int(s),SID_CLASS[int(s)],float(z),bool(f),float(y) if f else None)
            for s,z,f,y in zip(S[start:start+n],X[start:start+n],F[start:start+n],Y[start:start+n])]
        v=choose_at_one_clock(e)
        if v is not None:
            v['utc']=dt.datetime.fromtimestamp(int(k),tz=dt.timezone.utc).isoformat().replace('+00:00','Z')
            v['week']=dt.datetime.fromtimestamp(int(k),tz=dt.timezone.utc).strftime('%G-W%V')
            picks.append(v)
    # Finite single-account one common hourly slot; 8*5=40 minutes hold.
    assert len(picks)==len({x['utc'] for x in picks})
    fullweeks=[f'2026-W{w:02d}' for w in range(24,38)]
    grouped=defaultdict(list)
    for v in picks:grouped[v['week']].append(v)
    def weekly(w):
        p=grouped[w];com=[x['gross_bps'] for x in p if x['future_observed']]
        return {'week':w,'proposals':len(p),'observable':len(com),'censored':len(p)-len(com),
         'gross_bps_sum':round(sum(com),7),'gross_bps_median':round(float(np.median(com)),5) if com else None,
         'hypothetical_net_10bps':round(sum(com)-10*len(com),7),
         'hypothetical_net_20bps':round(sum(com)-20*len(com),7),
         'hypothetical_net_40bps':round(sum(com)-40*len(com),7),
         'meets_21_proposals_not_fills':len(p)>=21}
    wk=[weekly(w) for w in fullweeks]
    completed=[x for x in picks if x['week'] in fullweeks and x['future_observed']]
    full=[x for x in picks if x['week'] in fullweeks]
    gross=sum(x['gross_bps'] for x in completed)
    top=Counter(x['symbol_id'] for x in full)
    cls=Counter(x['class'] for x in full)
    o={'schema':'mxm.primary145.peer-relative-dislocation-fade.development.v1',
       'classification':'DEVELOPMENT_ONLY_FROZEN_SINGLE_TRIAL_NOT_BROKER_NET',
       'source_original_archive_sha256':ZIP_SHA,'source_feature_cache_sha256':shas,
       'source_primary_symbols':145,'source_rows_verified_prior_execution':11406418,
       'policy':{'signal':'fade asset-class peer median of contemporaneous 12-M5 close-to-close / own 48-M5 realized sigma',
        'peers_same_broker_native_class_minimum':MIN_SAME_CLASS,'abs_peer_deviation_sigma_threshold':THRESHOLD_SIGMA,
        'select':'one highest causal peer residual across all eligible groups per hourly common account slot',
        'entry':'second future M5-bar open, after causal bar close','exit':'8 M5-bars after entry (40m)',
        'signal_uses_future_availability':False,'one_position_max':True,
        'closed_ridge_fit_or_policy_reused':False},
       'evaluation':{'identity':'DEVELOPMENT_ONLY; period economics of previous Ridge known',
        'full_iso_utc_weeks':fullweeks,'full_weeks':14,'proposals':len(full),
        'observable_completed':len(completed),'censored':len(full)-len(completed),
        'gross_bps_sum':round(gross,7),
        'hypothetical_cost_stress_bps_per_completion':{str(int(c)):round(gross-c*len(completed),7) for c in COST_STRESS_BPS},
        'weeks_with_21_or_more_proposals_not_fills':sum(w['meets_21_proposals_not_fills'] for w in wk),
        'weeks_negative_gross':sum(w['gross_bps_sum']<0 for w in wk),
        'weeks_negative_hypothetical_20bps':sum(w['hypothetical_net_20bps']<0 for w in wk)},
       'weekly':wk,'partial_W38_observation_only':weekly(PARTIAL_WEEK),
       'concentration_top15':top.most_common(15),'by_broker_asset_class':dict(cls),
       'costs':{'bidask_authenticated':False,'pepperstone_historical_slippage':False,'friction_bps_are_assumptions':True,
         'historical_volume_minimum_certified':False,'continuously_funded_account_200_eur_replayed':False},
       'hard21_executed_proven':False,'orders_live_or_demo':0,'cloud_activated':False,
       'protected_forward_opened':False,'originals_reprocessed':False,'model_retraining':False}
    private={**o,'private_episode_outcomes':picks}
    path=ROOT/'PRIMARY145_PEER_DISLOCATION_ONE_TRIAL_PUBLIC.json'
    path.write_text(json.dumps(o,sort_keys=True,indent=2)+'\n')
    (ROOT/'PRIMARY145_PEER_DISLOCATION_ONE_TRIAL_PRIVATE.json').write_text(json.dumps(private,sort_keys=True,separators=(',',':'))+'\n')
    print('ECONOMIC_RESEARCH_RESULT',json.dumps({'evaluation':o['evaluation'],
          'by_broker_asset_class':o['by_broker_asset_class'],'top':o['concentration_top15'][:7]},sort_keys=True))
