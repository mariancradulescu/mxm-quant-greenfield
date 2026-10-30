"""ONE finite, predeclared, causal M5 OHLCV predictive DEVELOPMENT inquiry.

Prospective single pooled ridge model: past 24 exact M5 bars, volume surprise,
bar pressure, three-bar velocity -> NEXT 30-minute open-to-open return.
Train segments 1+2 (2026-08-20 to 09-02); read evaluation outcomes only
AFTER fitting (segments 3+4, 2026-09-03 to 09-16).
All 100 exact original encrypted shards / 1576 identities are read and verified.
No broker access, no orders, no closed strategy reuse, no account backtest.
"""
from __future__ import annotations
import collections
import datetime as dt
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import tempfile

from . import m5_authentic_envelope as env

ROOT = env.ROOT
REPO = env.REPO
MANIFEST = env.MANIFEST
RELEASE = env.RELEASE_IDENTITY
OUT = ROOT/"verification/m5-volume-response-20261030"
START = "2026-08-20T00:00:00Z"
SPLIT = "2026-09-03T00:00:00Z"
END = "2026-09-17T00:00:00Z"
HOUR = 3600
BAR = 300
FEATURE_LOOKBACK = 25
ENTRY_DELAY = 2
EXIT_BARS = 8
STRIDE = 3
MIN_TRAIN = 5000
MIN_EVAL = 5000
DIM = 6
REGULARIZATION = .02
BPS_HURDLE = 10.
COST_STRESS = (10.,20.)
MAX_SIGNALS = 1000000
CODE_CUSTODY = "464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11"
FROZEN_ID = "V4-M5-OHLCV-POOLED-RESPONSE-20261030-V1"


def need(flag,why):
    if not flag:raise ValueError("MXM_M5_VOLUME_"+why)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def clipped(v,limit):
    return max(-limit,min(limit,v))


def utc_week(t):
    return dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime("%G-W%V")


def inspect(rows,segment):
    start=dt.datetime.fromisoformat(env.STARTS[segment-1]+"T00:00:00+00:00").timestamp()
    stop=dt.datetime.fromisoformat(env.ENDS[segment-1]+"T23:59:59+00:00").timestamp()
    stamp=[];bars=[]
    prev=-1
    for row in rows:
        need(set(row)=={"time_utc","open","high","low","close","tick_volume"},"ROW_SCHEMA")
        d=dt.datetime.fromisoformat(row["time_utc"].replace("Z","+00:00"))
        t=int(d.timestamp())
        need(d.utcoffset()==dt.timedelta(0) and t>=start and t<=stop and t%300==0
             and t>prev and row["time_utc"] < END,"M5_TIMESTAMP_OR_PROTECTED")
        vals=[float(row[f]) for f in ("open","high","low","close")]
        vol=int(row["tick_volume"])
        op,hi,lo,cl=vals
        need(all(math.isfinite(z) and z>0 for z in vals) and
             lo<=min(op,cl)<=max(op,cl)<=hi and vol>=0,"M5_OHLCV")
        stamp.append(t);bars.append((op,hi,lo,cl,vol));prev=t
    return stamp,bars


def features(stamp,bars,i):
    if i<FEATURE_LOOKBACK or stamp[i]-stamp[i-FEATURE_LOOKBACK]!=FEATURE_LOOKBACK*BAR:
        return None
    cur=bars[i]
    prev=bars[i-24:i]
    scale=sum(abs(bars[j][3]/bars[j-1][3]-1) for j in range(i-24,i))/24
    if scale<=1e-9:return None
    spread=cur[1]-cur[2]
    body=(cur[3]-cur[0])/spread if spread>0 else 0.
    location=(2*cur[3]-cur[1]-cur[2])/spread if spread>0 else 0.
    baseline=statistics.median(x[4] for x in prev)
    volume=clipped(math.log((cur[4]+1)/(baseline+1)),3.)
    velocity=clipped((cur[3]/bars[i-3][3]-1)/scale,3.)
    x=(1.,clipped(body,1.),clipped(location,1.),volume,
       clipped(body*volume,3.),velocity)
    need(all(math.isfinite(z) for z in x),"FEATURE_FINITE")
    return x,scale


def solve(A,b):
    # Deterministic 6x6 regularized normal equations; ridge slopes only.
    n=DIM; aug=[list(A[i])+[b[i]] for i in range(n)]
    for k in range(n):
        pivot=max(range(k,n),key=lambda i:abs(aug[i][k]))
        need(abs(aug[pivot][k])>1e-12,"SINGULAR_SYSTEM")
        aug[k],aug[pivot]=aug[pivot],aug[k]
        den=aug[k][k]
        aug[k]=[z/den for z in aug[k]]
        for i in range(n):
            if i==k:continue
            fac=aug[i][k]
            aug[i]=[aug[i][j]-fac*aug[k][j] for j in range(n+1)]
    out=[aug[k][-1] for k in range(n)]
    need(all(math.isfinite(x) for x in out),"BAD_COEFFICIENT")
    return out


class Fit:
    def __init__(self):
        self.xx=[[0.]*DIM for _ in range(DIM)]
        self.xy=[0.]*DIM
        self.n=0
        self.sumy=0.
        self.sumy2=0.

    def add(self,x,y):
        need(math.isfinite(y) and all(math.isfinite(z) for z in x),"TRAIN_FINITE")
        self.n+=1;self.sumy+=y;self.sumy2+=y*y
        for j in range(DIM):
            self.xy[j]+=x[j]*y
            for k in range(DIM):
                self.xx[j][k]+=x[j]*x[k]

    def learn(self):
        need(self.n>=MIN_TRAIN,"TRAIN_SUPPORT")
        a=[row[:] for row in self.xx]
        for i in range(1,DIM):
            a[i][i]+=REGULARIZATION*self.n
        coefs=solve(a,self.xy)
        train_sse=(self.sumy2-2*sum(coefs[i]*self.xy[i] for i in range(DIM))
                   +sum(coefs[i]*self.xx[i][j]*coefs[j]
                        for i in range(DIM) for j in range(DIM)))
        return coefs,{'examples':self.n,'train_mse':max(0.,train_sse/self.n),
                      'zero_mse':self.sumy2/self.n,'mean_y':self.sumy/self.n}


def ready(stamps,bars,i):
    p=features(stamps,bars,i)
    if p is None:return None
    x,scale=p
    return x,scale


def training_rows(stamps,bars):
    for i in range(FEATURE_LOOKBACK,len(stamps)-EXIT_BARS,STRIDE):
        if stamps[i+EXIT_BARS]>=int(dt.datetime.fromisoformat(SPLIT.replace("Z","+00:00")).timestamp()):
            continue
        p=ready(stamps,bars,i)
        if p is None or stamps[i+EXIT_BARS]-stamps[i]!=EXIT_BARS*BAR:continue
        x,scale=p
        y=clipped((bars[i+EXIT_BARS][0]/bars[i+ENTRY_DELAY][0]-1)/scale,10.)
        yield x,y


def evaluation_rows(stamps,bars):
    split=int(dt.datetime.fromisoformat(SPLIT.replace("Z","+00:00")).timestamp())
    end=int(dt.datetime.fromisoformat(END.replace("Z","+00:00")).timestamp())
    for i in range(FEATURE_LOOKBACK,len(stamps),STRIDE):
        t=stamps[i]
        if t<split or t>=end:continue
        p=ready(stamps,bars,i)
        if p is None:continue
        x,scale=p
        observed=(i+EXIT_BARS<len(stamps) and
                  stamps[i+EXIT_BARS]-t==EXIT_BARS*BAR)
        gross=(10000*(bars[i+EXIT_BARS][0]/bars[i+ENTRY_DELAY][0]-1)
               if observed else None)
        y=clipped(gross/10000/scale,10.) if observed else None
        yield {'time':t,'x':x,'scale':scale,'gross':gross,'y':y,
               'settlement_observed':observed}


def aggregate(model,evaluation_file):
    coefs,training=model
    counters=collections.Counter()
    weeks=collections.defaultdict(lambda:dict(decisions=0,proposals=0,
                                                 settled=0,censored=0,gross_bps=0.))
    gross=0.;wins=0;net={v:0. for v in COST_STRESS}
    mse=0.;mse_zero=0.;mse_mean=0.
    latest_exit_by_symbol={}
    with open(evaluation_file) as f:
        for line in f:
            row=json.loads(line)
            counters['evaluated_with_past_support']+=1
            stamp=row['time'];sym=row['ordinal'];x=row['x'];scale=row['scale']
            predicted=sum(a*b for a,b in zip(coefs,x))
            predicted_bps=predicted*scale*10000
            # MSE on all causally feature-eligible rows with observed response.
            if row['settlement_observed']:
                y=row['y']
                mse+=(predicted-y)**2;mse_zero+=y*y
                mse_mean+=(y-training['mean_y'])**2
                counters['mse_labels']+=1
            # Do not consult future response support for proposing a trade.
            week=utc_week(stamp)
            weeks[week]['decisions']+=1
            if abs(predicted_bps)<=BPS_HURDLE:continue
            if stamp<=latest_exit_by_symbol.get(sym,-1):continue
            counters['causal_proposals']+=1
            weeks[week]['proposals']+=1
            latest_exit_by_symbol[sym]=stamp+EXIT_BARS*BAR
            if not row['settlement_observed']:
                counters['right_censored']+=1;weeks[week]['censored']+=1
                continue
            g=math.copysign(row['gross'],predicted)
            counters['settled']+=1
            weeks[week]['settled']+=1
            weeks[week]['gross_bps']+=g
            gross+=g
            wins+=int(g>0)
            for fee in COST_STRESS:net[fee]+=g-fee
    n=counters['settled'];l=counters['mse_labels']
    need(l>=MIN_EVAL,"EVAL_SUPPORT")
    return {'train':training,'coefficients':coefs,
      'evaluation_examples':counters['evaluated_with_past_support'],
      'evaluation_labels':l,
      'mse':{'pooled_ridge':mse/l,'zero_forecast':mse_zero/l,
             'training_mean_baseline':mse_mean/l},
      'causal_proposals':counters['causal_proposals'],'settled':n,
      'right_censored':counters['right_censored'],
      'gross_bps_sum':gross,'gross_bps_per_settled_trade':gross/n if n else None,
      'gross_positive_rate':wins/n if n else None,
      'hypothetical_net_bps_sums':{str(k):net[k] for k in COST_STRESS},
      'max_weekly_proposals':max((a['proposals'] for a in weeks.values()),default=0),
      'weekly':dict(sorted(weeks.items())),
      'risk_of_ruin_estimated':False,'eur200_account_executed':False,
      'historical_broker_costs_certified':False,'historical_fills_certified':False,
      'independent_confirmation':False}


def selftest():
    t=int(dt.datetime(2026,9,2,tzinfo=dt.timezone.utc).timestamp())
    times=[t+300*i for i in range(150)]
    bars=[]
    for i in range(len(times)):
        p=1.+.001*i+.0007*math.sin(i/3)
        bars.append((p,p+.002,p-.002,p+.0003*math.cos(i/3),50+i%7))
    p=features(times,bars,40)
    need(p is not None and len(p[0])==DIM,"SYNTHETIC_FEATURE")
    a=Fit()
    for _ in range(6500):a.add(p[0],.05)
    x,details=a.learn()
    need(len(x)==DIM and abs(x[0]-.05)<1e-7,"RIDGE_CONSTANT")
    times[38]+=600
    need(features(times,bars,40) is None or features(times,bars,40)!=p,
         "FAIL_ON_GAP") # false chronological gap must never be accepted silently
    rows=[{'time_utc':(dt.datetime.fromtimestamp(tt,dt.timezone.utc).isoformat().replace('+00:00','Z')),
           'open':str(v[0]),'high':str(v[1]),'low':str(v[2]),
           'close':str(v[3]),'tick_volume':str(v[4])} for tt,v in zip(times,bars)]
    rows[0]['time_utc']=END
    try:inspect(rows,3)
    except ValueError:pass
    else:need(False,"PROTECTED_GUARD_TEST")
    print('MXM_M5_VOLUME_POOLED_CAUSAL_SYNTHETIC_TEST_PASS')


def authenticated_source_run():
    need(os.getenv('GITHUB_REPOSITORY')==REPO and
         os.getenv('GITHUB_REF')=='refs/heads/mxm-remediation-p0-p4-20261015-v1' and
         os.getenv('GITHUB_EVENT_NAME')=='push' and
         os.getenv('GITHUB_RUN_ATTEMPT')=='1',"WORKFLOW_SCOPE")
    manifest=json.loads(MANIFEST.read_bytes())
    entries=manifest['entries']
    need(manifest['status']=='COMPLETE' and
         manifest['DURABLE_RELEASE_IDENTITY']==RELEASE and
         manifest['PROTECTED_FORWARD_ROW_COUNT']==0 and
         len(entries)==100 and sum(z['ROW_COUNT'] for z in entries)==3355389,
         'FROZEN_MARKET_SOURCE')
    expected={z['ENCRYPTED_ASSET_NAME']:z for z in entries}
    need(len(expected)==100,'ASSET_SET')
    remote=env.gh_json('repos/'+REPO+'/releases/tags/'+RELEASE)
    asset={a['name']:a for a in remote['assets']}
    need(set(asset)==set(expected) and remote['target_commitish']==manifest['ARM_COMMIT'],'SOURCE_RELEASE_CHANGED')
    for name,e in expected.items():
        need(asset[name]['digest']=='sha256:'+e['ENCRYPTED_ASSET_SHA256'] and
             asset[name]['state']=='uploaded','ASSET_HASH_CHANGED')
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import decrypt_synthetic_package
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    fit=Fit()
    support=collections.Counter()
    with tempfile.TemporaryDirectory(prefix='mxm-new-volume-model-') as d:
        temp=Path(d);key,fp=_private_key_from_secret(temp)
        need(fp==CODE_CUSTODY,"CUSTODY_FINGERPRINT")
        src=temp/'market';src.mkdir(mode=0o700)
        subprocess.run(['gh','release','download',RELEASE,'--repo',REPO,'--dir',str(src)],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=240)
        need({x.name for x in src.iterdir()}==set(expected),'100_ORIGINAL_ASSETS')
        eval_file=temp/'future_eval.jsonl'
        with eval_file.open('w') as stream:
            for shard in range(25):
                by_ordinal=collections.defaultdict(list)
                for seg in range(1,5):
                    e=next(z for z in entries if z['SEGMENT_INDEX']==seg and z['SHARD_INDEX']==shard)
                    cipher=(src/e['ENCRYPTED_ASSET_NAME']).read_bytes()
                    need(sha(cipher)==e['ENCRYPTED_ASSET_SHA256'],'CIPHER_CHANGED')
                    plain=decrypt_synthetic_package(cipher,private_key=key)
                    need(sha(plain)==e['PLAINTEXT_CANONICAL_SHA256'],'PLAINTEXT_CHANGED')
                    original=json.loads(plain)
                    need(original['schema']=='mxm.v4.shallow-m5-v2.raw-shard.v1' and
                         original['segment_index']==seg and
                         original['shard_index']==shard and
                         original['identity_range']==e['IDENTITY_RANGE'],'SHARD_CONTEXT')
                    count=0
                    expected_ord=list(range(e['IDENTITY_RANGE'][0],e['IDENTITY_RANGE'][1]+1))
                    need([i['ordinal'] for i in original['items']]==expected_ord,'SHARD_ORDINALS')
                    for item in original['items']:
                        rows=item['rows']
                        need(isinstance(rows,list),'ROW_LIST')
                        count+=len(rows);support['verified_market_rows']+=len(rows)
                        stamps,bars=inspect(rows,seg)
                        by_ordinal[item['ordinal']].append((stamps,bars))
                    need(count==e['ROW_COUNT'],'MARKET_SHARD_ROWS')
                    support['verified_shards']+=1
                for ordinal,segments in by_ordinal.items():
                    stamps=[t for z,_ in segments for t in z]
                    bars=[q for _,z in segments for q in z]
                    need(stamps==sorted(set(stamps)),'CROSS_SEGMENT_MONOTONIC')
                    support['market_identities']+=1
                    for x,y in training_rows(stamps,bars):fit.add(x,y)
                    for row in evaluation_rows(stamps,bars):
                        row['ordinal']=ordinal
                        stream.write(json.dumps(row,separators=(',',':'))+'\n')
                        support['eval_candidate_feature_rows']+=1
        need(support['verified_market_rows']==3355389 and support['verified_shards']==100 and
             support['market_identities']==1576,'ORIGINAL_FULL_GEOMETRY')
        model=fit.learn()
        diagnostic=aggregate(model,eval_file)
    OUT.mkdir(parents=True,exist_ok=False)
    pubkey=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
    need(public_spki_sha256(pubkey)==CODE_CUSTODY,'CUSTODY_RECIPIENT')
    secret={'identity':FROZEN_ID,'original_manifest_sha256':sha(MANIFEST.read_bytes()),
            'source':RELEASE,'diagnostic':diagnostic,'support':dict(support),
            'protected_forward':False,'new_market_requests':0,'orders':0,
            'new_v4_development_identity':1,'economic_confirmation':False}
    private=OUT/'complete-study.mxmenc'
    encrypt_shard(gzip.compress(json.dumps(secret,sort_keys=True,allow_nan=False).encode(),mtime=0),
                  public_key=pubkey,output=private)
    # Public receipt is deliberately aggregate. Do not publish individual
    # symbol selections, bars, forecast rows, fitted model/coefficients.
    eval_result={k:v for k,v in diagnostic.items()
                 if k not in ('coefficients','weekly')}
    pub={'schema':'mxm.m5.volume-response.pooled-first-economic.v1',
         'identity':FROZEN_ID,'release':RELEASE,
         'original_manifest_sha256':sha(MANIFEST.read_bytes()),
         'verified_source':dict(support),'economic':eval_result,
         'week_count':len(diagnostic['weekly']),
         'censored_outcome_count':diagnostic['right_censored'],
         'status':'NO_PROVEN_NET_EDGE_DEVELOPMENT_ONLY',
         'hypothetical_10bps_is_not_broker_cost':True,
         'fixed_training_period':['2026-08-20','2026-09-02'],
         'fixed_evaluation_period':['2026-09-03','2026-09-16'],
         'risk_of_ruin_proven':False,'eur200_portfolio_executed':False,
         'historical_broker_costs_proven':False,'independent_confirmation':False,
         'closed_models_rerun':0,'new_broker_requests':0,'orders':0,'cloud':False,
         'private_study_sha256':sha(private.read_bytes())}
    (OUT/'public.json').write_text(json.dumps(pub,sort_keys=True,allow_nan=False)+'\n')
    print('MXM_M5_NEW_POOLED_VOLUME_RESEARCH '+json.dumps(pub,sort_keys=True,allow_nan=False),flush=True)


if __name__=='__main__':
    import sys
    need(sys.argv[1:] in (['selftest'],['protected']),'ENTRYPOINT')
    if sys.argv[1:]==['selftest']:selftest()
    else:authenticated_source_run()
