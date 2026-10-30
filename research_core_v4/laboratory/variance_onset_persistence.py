"""One NEW fixed true-scale volatility-onset directional persistence DEVELOPMENT trial.

Unlike prior closed multiscale occupancy / serial-location rules, this tests
fast M5 absolute-return intensity against a disjoint prior H4 baseline, with
direction aligned across 1h and 4h, not a re-tuned former signal.

Original accepted Pepperstone M5; three source-preselected instruments with
historical *dated* margin/min-volume metadata. Costs are coarse scenarios, NOT
time-aligned BID/ASK or funded account. No order, Cloud or live connection.
"""
import collections
import datetime as dt
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from . import m5_authentic_envelope as env

ROOT=env.ROOT
MANIFEST=env.MANIFEST
REPO=env.REPO
RELEASE=env.RELEASE_IDENTITY
SPEC=ROOT/'research_core_v4/laboratory/VARIANCE_ONSET_PERSISTENCE_20261030_V1.json'
OUT=ROOT/'verification/variance-onset-20261030'
FP='464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11'
CLOCK=300
TARGETS=(5,111,250)
SHARDS=(0,1,3)
DAYS=(1,2,3,4)
FAST=12
SLOW=48
WARM=FAST+SLOW
STEP=12
DELAY=2
EXIT=8
RATIO=1.4
MOVE=3.
START='2026-08-20T00:00:00Z'
END='2026-09-17T00:00:00Z'
ID='V4-VARIANCE-ONSET-PERSISTENCE-20261030-V1'


def need(c,k):
    if not c:raise ValueError('MXM_ONSET_'+k)


def digest(b):return hashlib.sha256(b).hexdigest()


def frozen():
    s=json.loads(SPEC.read_bytes())
    need(s['schema']=='mxm.v4.variance-onset-persistence-first-development.v1' and
         s['id']==ID and s['source_release']==RELEASE and
         [z['sid'] for z in s['precommitted_targets']]==list(TARGETS) and
         s['slow_previous_closed_m5_bars']==SLOW and
         s['fast_recent_closed_m5_bars']==FAST and
         s['entry_delay_bars']==DELAY and s['exit_offset_bars']==EXIT and
         s['decision_step_bars']==STEP and
         s['fast_to_slow_mean_absolute_return_ratio']==RATIO and
         s['min_abs_fast_return_to_slow_mean_abs_ratio']==MOVE and
         s['cost_multipliers']==[1,2] and s['extra_stress_bps']==10 and
         s['source_selection_from_outcomes'] is False and
         s['no_previous_model_rerun'] is True and
         s['automatic_retuning'] is False and
         s['real_broker_orders']==0 and s['protected_forward_opened'] is False,
         'FROZEN_ID_CHANGED')
    return s


def parse(rows,segment):
    times=[];bars=[]
    first=int(dt.datetime.fromisoformat(env.STARTS[segment-1]+'T00:00:00+00:00').timestamp())
    last=int(dt.datetime.fromisoformat(env.ENDS[segment-1]+'T23:59:59+00:00').timestamp())
    for r in rows:
        need(set(r)=={'time_utc','open','high','low','close','tick_volume'},'SCHEMA')
        z=dt.datetime.fromisoformat(r['time_utc'].replace('Z','+00:00'))
        t=int(z.timestamp())
        vals=[float(r[x]) for x in ('open','high','low','close')]
        op,hi,lo,cl=vals
        volume=int(r['tick_volume'])
        need(r['time_utc'].endswith('Z') and z.utcoffset()==dt.timedelta(0) and
             first<=t<=last and r['time_utc']<END and t%CLOCK==0 and
             (not times or t>times[-1]),'SOURCE_UTC')
        need(all(math.isfinite(x) and x>0 for x in vals) and
             lo<=min(op,cl)<=max(op,cl)<=hi and volume>=0,'OHLCV')
        times.append(t);bars.append((op,cl))
    return times,bars


def offers(times,bars):
    """Signals are computed from completed historical prices ONLY.
    The entry and exit quotes must exist later to score; missing outcomes
    are censored and never tested to decide whether to issue an offer."""
    prior_exit=-1
    for i in range(WARM,len(times),STEP):
        t=times[i]
        day=dt.datetime.fromtimestamp(t,dt.timezone.utc)
        if day.weekday()>=5 or not 7<=day.hour<=17:continue
        if any(times[j]-times[j-1]!=CLOCK for j in range(i-WARM+1,i+1)):
            continue
        slow=[abs(bars[j][1]/bars[j-1][1]-1) for j in range(i-WARM+1,i-FAST+1)]
        fast=[abs(bars[j][1]/bars[j-1][1]-1) for j in range(i-FAST+1,i+1)]
        need(len(slow)==SLOW and len(fast)==FAST,'SCALE_GEOMETRY')
        slowavg=sum(slow)/SLOW
        fastavg=sum(fast)/FAST
        if slowavg<=1e-10 or fastavg/slowavg<RATIO:continue
        fast_move=bars[i][1]/bars[i-FAST][1]-1
        slow_move=bars[i-FAST][1]/bars[i-WARM][1]-1
        if abs(fast_move)/slowavg<MOVE or fast_move*slow_move<=0:continue
        if t<=prior_exit:continue
        direction=1 if fast_move>0 else -1
        prior_exit=t+EXIT*CLOCK
        complete=(i+EXIT<len(times) and
                  times[i+EXIT]-t==EXIT*CLOCK and
                  all(times[k]-times[k-1]==CLOCK
                      for k in range(i+1,i+EXIT+1)))
        gross=10000*direction*(bars[i+EXIT][0]/bars[i+DELAY][0]-1) if complete else None
        yield {'clock':t,'side':direction,'settled':complete,
               'gross_bps':gross,'slowabs':slowavg,'fastabs':fastavg}


def evaluate(corpus,spec):
    detail=[];source={};weeks=collections.defaultdict(lambda:collections.Counter())
    for target in spec['precommitted_targets']:
        sid=target['sid']
        times,bars=corpus[sid]
        need(times==sorted(set(times)),'SOURCE_GLOBAL_TIME_UNIQUE')
        source[str(sid)]={'bars':len(times),'first_utc':dt.datetime.fromtimestamp(times[0],dt.timezone.utc).isoformat() if times else None,
                          'last_utc':dt.datetime.fromtimestamp(times[-1],dt.timezone.utc).isoformat() if times else None}
        unit_cost=10000*float(target['coarse_roundtrip_fraction'])
        for o in offers(times,bars):
            stamp=dt.datetime.fromtimestamp(o['clock'],dt.timezone.utc)
            wk=stamp.strftime('%G-W%V');w=weeks[wk]
            w['proposals']+=1
            w['by_symbol_'+str(sid)]+=1
            if o['settled']:
                w['settled']+=1
                w['gross_bps_sum']+=o['gross_bps']
            else:w['censored']+=1
            detail.append({**o,'sid':sid,'week':wk,'cost_bps':unit_cost})
    settled=[x for x in detail if x['settled']]
    need(sum(x['proposals'] for x in weeks.values())==len(detail) and
         sum(x['settled'] for x in weeks.values())==len(settled),'AGGREGATION')
    gross=sum(z['gross_bps'] for z in settled)
    net1=sum(z['gross_bps']-z['cost_bps'] for z in settled)
    net2=sum(z['gross_bps']-2*z['cost_bps'] for z in settled)
    net2plus=sum(z['gross_bps']-2*z['cost_bps']-10 for z in settled)
    bysymbol={}
    for sid in TARGETS:
        x=[z for z in settled if z['sid']==sid]
        bysymbol[str(sid)]={'count':len(x),
             'gross_bps_sum':sum(z['gross_bps'] for z in x),
             'coarse_after_cost_bps_sum':sum(z['gross_bps']-z['cost_bps'] for z in x)}
    # The four original one-week capture segments start Thursday 20 August,
    # end Wednesday 16 September. ISO W34 and W38 are *partial* and cannot
    # be treated as full-week HARD21 observations.
    full_weeks=('2026-W35','2026-W36','2026-W37')
    enough=(len(detail)>=spec['minimum_complete_decision_candidates'] and
            len(settled)>=spec['minimum_complete_trades'] and
            all(weeks[w]['settled']>=21 for w in full_weeks))
    # Even a positive scenario cannot prove profit: these are summed bps
    # over parallel different instruments without real cost or EUR200 funding.
    public={'schema':'mxm.variance-onset-frozen-first-result.v1','id':ID,
        'source_identity':RELEASE,'source':source,
        'proposals':len(detail),'settled':len(settled),
        'censored':len(detail)-len(settled),
        'gross_bps_sum':gross,'coarse_cost_bps_sum':sum(z['cost_bps'] for z in settled),
        'after_coarse_bps_sum':net1,'after_double_coarse_bps_sum':net2,
        'after_double_coarse_plus10bps_sum':net2plus,
        'gross_positive_share':sum(z['gross_bps']>0 for z in settled)/len(settled) if settled else None,
        'cost_sensitive_gross_not_eur':True,'not_independent_confirmation':True,
        'minimum_source_and_trade_support':enough,
        'full_iso_weeks_for_support':list(full_weeks),
        'partial_iso_weeks_not_hard21_eligible':['2026-W34','2026-W38'],
        'weeks':{w:{'proposals':q['proposals'],'settled':q['settled'],
                   'censored':q['censored'],'gross_bps_sum':q['gross_bps_sum']}
                 for w,q in sorted(weeks.items())},
        'by_symbol':bysymbol,
        'classification':('SOURCE_OR_EVENT_LIMITED' if not enough else
          'COARSE_NET_FAIL_FROZEN' if net1<=0 else
          'COARSE_DEVELOPMENT_POSITIVE_NOT_FINANCED'),
        'historical_broker_cost_proven':False,'historical_broker_fills_proven':False,
        'single_eur200_account_executed':False,'hard21_certified':False,
        'model_trials_opened':1,'prior_closed_models_rerun':0,
        'new_broker_requests':0,'orders':0,'cloud_activations':0,
        'protected_forward_opened':False}
    return public,detail


def selftest():
    frozen()
    start=int(dt.datetime(2026,8,24,tzinfo=dt.timezone.utc).timestamp())
    times=[start+300*i for i in range(120)]
    bars=[]
    for i in range(120):
        value=1+(.0001*i if i<65 else .0065+.001*(i-65))
        bars.append((value,value+.00001))
    rows=[{'time_utc':dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat().replace('+00:00','Z'),
           'open':str(p[0]),'close':str(p[1]),'high':str(p[1]+.0001),
           'low':str(p[0]-.0001),'tick_volume':'5'} for t,p in zip(times,bars)]
    tt,bb=parse(rows,1)
    need(tt==times and len(list(offers(tt,bb)))<=12,'SYNTHETIC_CAUSAL_SUPPORT')
    times[30]+=600
    need(not any(z['clock']==times[72] and z['gross_bps'] is None
             for z in offers(times,bars)),'FALSE_CENSOR_TRUTH')
    rows[0]['time_utc']='2026-09-17T00:00:00Z'
    try:parse(rows,1)
    except ValueError:pass
    else:need(False,'PROTECTED_CLOCK_GUARD')
    print('MXM_TRUE_SCALE_VARIANCE_ONSET_CAUSAL_SYNTHETIC_PASS')


def run():
    frozen()
    need(os.getenv('GITHUB_REPOSITORY')==REPO and
         os.getenv('GITHUB_EVENT_NAME')=='push' and
         os.getenv('GITHUB_REF')=='refs/heads/mxm-remediation-p0-p4-20261015-v1' and
         os.getenv('GITHUB_RUN_ATTEMPT')=='1','GITHUB_SCOPE')
    spec=frozen()
    manifest=json.loads(MANIFEST.read_bytes())
    need(manifest['status']=='COMPLETE' and
         manifest['DURABLE_RELEASE_IDENTITY']==RELEASE and
         manifest['PROTECTED_FORWARD_ROW_COUNT']==0 and
         len(manifest['entries'])==100 and
         sum(z['ROW_COUNT'] for z in manifest['entries'])==3355389,'MASTER_SOURCE')
    selected=[e for e in manifest['entries'] if
       e['SHARD_INDEX'] in SHARDS and e['SEGMENT_INDEX'] in DAYS]
    need(len(selected)==12,'PINNED_SOURCE_12_SHARDS')
    expected={z['ENCRYPTED_ASSET_NAME']:z for z in selected}
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import decrypt_synthetic_package,encrypt_shard,public_spki_sha256
    release=env.gh_json('repos/'+REPO+'/releases/tags/'+RELEASE)
    remote={a['name']:a for a in release['assets']}
    need(set(expected).issubset(remote) and
         len(remote)==100 and release['target_commitish']==manifest['ARM_COMMIT'],'PINNED_RELEASE')
    for name,z in expected.items():
        need(remote[name]['digest']=='sha256:'+z['ENCRYPTED_ASSET_SHA256'] and
             remote[name]['state']=='uploaded','SOURCE_ASSET_HASH')
    with tempfile.TemporaryDirectory(prefix='mxm-variance-onset-first-') as d:
        folder=Path(d)
        key,fp=_private_key_from_secret(folder)
        need(fp==FP,'ORIGINAL_CUSTODY')
        download=folder/'cipher';download.mkdir()
        for shard in SHARDS:
            subprocess.run(['gh','release','download',RELEASE,'--repo',REPO,
                 '--dir',str(download),'-p',f'shallow-m5-v2-seg*-shard{shard:02d}.mxmenc'],
                 check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120)
        need({x.name for x in download.iterdir()}==set(expected),'EXACT_12_SOURCE_SHARDS')
        corpus={sid:([],[]) for sid in TARGETS}
        rawcount=0
        for z in sorted(selected,key=lambda r:(r['SEGMENT_INDEX'],r['SHARD_INDEX'])):
            encrypted=(download/z['ENCRYPTED_ASSET_NAME']).read_bytes()
            need(digest(encrypted)==z['ENCRYPTED_ASSET_SHA256'],'CIPHER_HASH')
            original=decrypt_synthetic_package(encrypted,private_key=key)
            need(digest(original)==z['PLAINTEXT_CANONICAL_SHA256'],'ORIGINAL_HASH')
            data=json.loads(original)
            need(data['schema']=='mxm.v4.shallow-m5-v2.raw-shard.v1' and
                 data['segment_index']==z['SEGMENT_INDEX'] and
                 data['shard_index']==z['SHARD_INDEX'] and
                 data['identity_range']==z['IDENTITY_RANGE'],'SHARD_IDENTITY')
            need([a['ordinal'] for a in data['items']]==
                 list(range(z['IDENTITY_RANGE'][0],z['IDENTITY_RANGE'][1]+1)),'ALL_SOURCE_IDENTITIES')
            n=0
            for item in data['items']:
                n+=len(item['rows'])
                if item['ordinal'] not in TARGETS:continue
                times,bars=parse(item['rows'],z['SEGMENT_INDEX'])
                corpus[item['ordinal']][0].extend(times)
                corpus[item['ordinal']][1].extend(bars)
            need(n==z['ROW_COUNT'],'ORIGINAL_ROW_COUNT');rawcount+=n
        public,detail=evaluate(corpus,spec)
        public['authentic_source_shards']=len(selected)
        public['all_original_shard_rows_authenticated']=rawcount
        public['fixed_spec_sha256']=digest(SPEC.read_bytes())
        public['original_manifest_sha256']=digest(MANIFEST.read_bytes())
        public['reference_sizing']='1000EUR_PER_EPISODE_NOMINAL_STAGE_A_NOT_INITIAL_CAPITAL'
        OUT.mkdir(parents=True,exist_ok=False)
        pubkey=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
        need(public_spki_sha256(pubkey)==FP,'STUDY_RECIPIENT')
        raw=json.dumps({'public':public,'episodes':detail},sort_keys=True,allow_nan=False,separators=(',',':')).encode()
        encrypt_shard(gzip.compress(raw,mtime=0),public_key=pubkey,output=OUT/'detail.mxmenc')
        public['encrypted_private_sha256']=digest((OUT/'detail.mxmenc').read_bytes())
        (OUT/'public.json').write_text(json.dumps(public,sort_keys=True,allow_nan=False)+'\n')
        print('MXM_NEW_VARIANCE_ONSET_ECONOMIC_FIRST '+json.dumps(public,sort_keys=True,allow_nan=False))


if __name__=='__main__':
    import sys
    need(sys.argv[1:] in (['selftest'],['protected']),'ENTRYPOINT')
    selftest() if sys.argv[1:]==['selftest'] else run()
