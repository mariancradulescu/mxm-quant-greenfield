"""One fixed exploratory family. No broker, selection, alpha or significance.

Pure functions accept fabricated data. The sole production reader is called
by entrypoint only after independently signed, exact-HEAD authorization.
"""
import csv
import hashlib
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import zipfile
import numpy as np
from research_core_v4.compact_baseline_v2 import baseline
from research_core_v4.main_reentry_v1.offline_falsification import diagnostic_maps
from research_core_v4.operational_v1.prequential_score import fit_prefix, predict, solve_ridge

DAY = 86400
START = int(datetime(2025,9,16,tzinfo=timezone.utc).timestamp())
END = int(datetime(2026,9,17,tzinfo=timezone.utc).timestamp())
CLOCK = np.arange(START, END, 21600, dtype=np.int64)
LAGS = (0,300,900)
HORIZONS = (1,12)
MAPS = ('CHRONOLOGY','COUPLING','COMBINED')
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MANIFEST = ROOT/'research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json'

def fail(condition, why):
    if not condition: raise ValueError(why)

def digest(raw): return hashlib.sha256(raw).hexdigest()

def verified_archive(path,expected_digest):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    fail(h.hexdigest()==expected_digest,'ARCHIVE_DIGEST')
    z=zipfile.ZipFile(path)
    if len(z.namelist())!=len(set(z.namelist())):
        z.close();raise ValueError('DUPLICATE_MEMBER')
    return z

def accepted_member(z,expected):
    fail(expected['file']=='raw/'+str(expected['symbol_id'])+'_M5.csv','SOURCE_MEMBER_SCOPE')
    raw=z.read(expected['file']);fail(digest(raw)==expected['series_sha256'],'SERIES_DIGEST')
    return raw

def parse_series(raw, expected, start=START, end=END):
    """No filtering, sorting, deduplication, imputation or fallback."""
    fail(digest(raw)==expected['series_sha256'], 'SERIES_DIGEST')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    fail(reader.fieldnames==['time_utc','open','high','low','close','tick_volume'], 'SOURCE_COLUMNS')
    bars = {}
    previous = start-300
    for row in reader:
        fail(None not in row and all(v is not None for v in row.values()), 'SOURCE_DIMENSIONS')
        dt = datetime.fromisoformat(row['time_utc'].replace('Z','+00:00'))
        fail(dt.tzinfo is not None and dt.utcoffset().total_seconds()==0, 'SOURCE_UTC')
        ts = int(dt.timestamp())
        fail(dt.timestamp()==ts and ts%300==0 and start<=ts<end and ts>previous, 'SOURCE_CHRONOLOGY')
        values = [float(row[k]) for k in ('open','high','low','close','tick_volume')]
        fail(all(math.isfinite(v) for v in values), 'SOURCE_NONFINITE')
        o,h,l,c,v = values
        fail(0<l<=min(o,c)<=max(o,c)<=h and v>=0 and v==int(v), 'SOURCE_OHLCV')
        bars[ts] = dict(timestamp=ts,available_at=ts+300,open=o,high=h,low=l,close=c,tick_volume=int(v))
        previous = ts
    fail(len(bars)==expected['row_count'], 'SOURCE_ROW_COUNT')
    fail(bool(bars), 'EMPTY_SOURCE')
    fail(datetime.fromtimestamp(min(bars),timezone.utc).isoformat().replace('+00:00','Z')==expected['first_timestamp_utc'], 'SOURCE_FIRST')
    fail(datetime.fromtimestamp(max(bars),timezone.utc).isoformat().replace('+00:00','Z')==expected['last_timestamp_utc'], 'SOURCE_LAST')
    return bars

def features(bars, t, lag):
    cutoff = t-lag
    hour = cutoff//3600*3600-3600
    need = set(range(hour,hour+3600,300))|{cutoff-300}
    if not need.issubset(bars): return None, 'FEATURE_INCOMPLETE'
    # As-if receipt shift: available_at is hypothetical bar-close+lag.
    # Evaluate the immutable B at cutoff with unshifted close availability;
    # equivalent to shifted receipt<=t. Late synthetic records still fail.
    selected = [bars[k] for k in sorted(need)]
    b = baseline(cutoff,selected)
    if b is None: return None, 'FEATURE_LATE_OR_INVALID'
    elapsed = [bars[k] for k in range(hour,hour+3600,300)]
    # Translate only timestamps into the fixed witness grid; values unchanged.
    phi = diagnostic_maps([dict(x,timestamp=7200+300*i) for i,x in enumerate(elapsed)])
    if phi[1] is None: return None, 'ZERO_ACTIVITY_COMMON_ABSTENTION'
    return (np.asarray(b,float),np.asarray(phi,float)), 'SUPPORTED'

def response(bars, t, h, lag, observed_until):
    maturity = t+300*h+lag
    fail(observed_until>=maturity, 'LABEL_NOT_MATURE')
    need = range(t-300,t+300*h,300)
    if any(k not in bars for k in need): return None
    return math.log(bars[t+300*(h-1)]['close']/bars[t-300]['close'])

def derive(bars, clocks=CLOCK):
    """Sealed response cache for retrospective simulation, never model input.
    Every label is released to a model/evaluator only through maturity checks.
    """
    b = np.zeros((3,len(clocks),10));phi=np.zeros((3,len(clocks),2))
    feature_ok=np.zeros((3,len(clocks)),bool);reason=np.empty((3,len(clocks)),dtype='U40')
    y=np.zeros((3,2,len(clocks)));label_ok=np.zeros_like(y,dtype=bool)
    for li,lag in enumerate(LAGS):
        for k,t0 in enumerate(clocks):
            t=int(t0);v,why=features(bars,t,lag);reason[li,k]=why
            if v is not None: b[li,k],phi[li,k]=v;feature_ok[li,k]=True
            for hi,h in enumerate(HORIZONS):
                if t+300*h+lag>END: continue
                yy=response(bars,t,h,lag,t+300*h+lag)
                if yy is not None: y[li,hi,k]=yy;label_ok[li,hi,k]=True
    return dict(b=b,phi=phi,feature_ok=feature_ok,reason=reason,y=y,label_ok=label_ok)

def fit_family(t,maturity,ids,b,phi,sealed_y,valid,refit,start):
    fail(np.all(maturity>t),'LABEL_MATURITY_ORDER')
    fail(b.shape==(len(t),10) and phi.shape==(len(t),2),'MODEL_DIMENSIONS')
    # Future labels are replaced with zero BEFORE the inherited fitter sees Y.
    past = valid & (maturity<refit)
    y = np.zeros_like(sealed_y);y[past]=sealed_y[past]
    f = fit_prefix(t,maturity,ids,b,phi,y,past,refit,start)
    if f is None: return None
    ix=f.train_indices
    fail(np.all(maturity[ix]<refit) and np.all(t[ix]+245*60<refit), 'FIT_LOOKAHEAD')
    xx=(np.column_stack([b[ix],phi[ix]])-f.means)/f.sds;xx[:,f.zero]=0
    yy=np.clip((y[ix]-f.ymean)/f.ysd,-8,8)
    coefficients = [solve_ridge(np.column_stack([xx[:,:10],xx[:,10+j]]),yy,f.weights) for j in (0,1)]
    coefficients.append(f.beta_aug)
    return f,coefficients

def forecasts(fit,b,phi):
    f,coef=fit
    pb,_=predict(f,b,phi)
    xx=(np.r_[b,phi]-f.means)/f.sds;xx[f.zero]=0
    xs=[np.r_[1.,xx[:10],xx[10]],np.r_[1.,xx[:10],xx[11]],np.r_[1.,xx]]
    return pb,np.clip([x@beta for x,beta in zip(xs,coef)],-8,8)

def evaluate(caches,ids,clocks=CLOCK,start=START,end=END):
    """All18 comparisons, common family support, fixed identity/calendar mass."""
    n=len(ids);K=len(clocks);fail(n>0 and len(set(ids))==n,'IDENTITIES')
    score_ix=np.flatnonzero(clocks>=start+56*DAY);N=len(score_ix)
    fail(N>0,'SCORE_CALENDAR')
    outputs=[];calendar=[];fit_audits=[]
    times=np.repeat(clocks,n);identity=np.tile(ids,K)
    for li,lag in enumerate(LAGS):
        for hi,h in enumerate(HORIZONS):
            b=np.stack([c['b'][li] for c in caches],axis=1).reshape(K*n,10)
            phi=np.stack([c['phi'][li] for c in caches],axis=1).reshape(K*n,2)
            sealed=np.stack([c['y'][li,hi] for c in caches],axis=1).reshape(-1)
            fok=np.stack([c['feature_ok'][li] for c in caches],axis=1).reshape(-1)
            lok=np.stack([c['label_ok'][li,hi] for c in caches],axis=1).reshape(-1)
            maturity=times+300*h+lag;valid=fok&lok&(maturity<=end)
            gains=np.zeros((K,n,3));supported=np.zeros((K,n),bool)
            absent={'feature':0,'label':0,'fit':0};forecast_hash=hashlib.sha256()
            feature_reasons={}
            fit=None;current=None
            for k in score_ix:
                t=int(clocks[k]);refit=start+56*DAY+((t-start-56*DAY)//(7*DAY))*7*DAY
                if current!=refit:
                    fit=fit_family(times,maturity,identity,b,phi,sealed,valid,refit,start);current=refit
                    if fit is not None:
                        f=fit[0];ix=f.train_indices
                        fit_audits.append({'lag_seconds':lag,'horizon_M5':h,'refit':refit,'training_rows':len(ix),
                          'latest_training_maturity':int(maturity[ix].max()),'latest_training_clock':int(times[ix].max()),
                          'train_indices_sha256':digest(ix.tobytes()),'ymean':f.ymean,'ysd':f.ysd,
                          'identity_weight_totals':{str(i):float(f.weights[identity[ix]==i].sum()) for i in np.unique(identity[ix])}})
                for s in range(n):
                    j=k*n+s
                    if not fok[j]:
                        absent['feature']+=1;why=str(caches[s]['reason'][li,k])
                        feature_reasons[why]=feature_reasons.get(why,0)+1;continue
                    if fit is None: absent['fit']+=1;continue
                    # Forecasts computed and bound before accessing this label.
                    pb,pa=forecasts(fit,b[j],phi[j])
                    forecast_hash.update(np.r_[t,ids[s],pb,pa].astype('<f8').tobytes())
                    if not lok[j] or maturity[j]>end: absent['label']+=1;continue
                    released_at=int(maturity[j]);fail(released_at>t,'FORECAST_LABEL_ORDER')
                    yy=float(np.clip((sealed[j]-fit[0].ymean)/fit[0].ysd,-8,8))
                    gain=((yy-pb)**2-(yy-pa)**2)/256
                    fail(np.isfinite(gain).all() and (np.abs(gain)<=1+1e-14).all(),'SCORE_BOUND')
                    gains[k,s]=gain;supported[k,s]=True
            for mi,name in enumerate(MAPS):
                x=gains[score_ix,:,mi].mean(1);calendar.append(x)
                outputs.append({'comparison':name,'horizon_M5':h,'lag_seconds':lag,
                  'status':'EXPLORATORY_ONLY_NO_FORMAL_REJECTION' if supported[score_ix].any() else 'UNSUPPORTED',
                  'calendar_units':N,'identities':n,'fixed_opportunities':N*n,
                  'paired_supported':int(supported[score_ix].sum()),'abstention':absent,
                  'feature_abstention_reasons':feature_reasons,
                  'mean_bounded_score_gain':float(x.mean()),'calendar_gain':x.tolist(),
                  'identity_gain_fixed_calendar':gains[score_ix,:,mi].mean(0).tolist(),
                  'identity_supported_counts':supported[score_ix].sum(0).tolist(),
                  'forecast_sha256':forecast_hash.hexdigest(),
                  'score_denominator':256,'formal_p_value':None,'formal_rejection':None})
    panel=np.asarray(calendar).T
    fail(len(outputs)==18,'FULL_FAMILY')
    return {'schema':'mxm.exploratory.primary145.report.v1','inference_class':'EXPLORATORY_ONLY_NO_FORMAL_REJECTION',
      'receipt':'UNKNOWN; conditional sensitivity scenarios only','identity_order':list(map(int,ids)),
      'score_clock_utc_epoch':clocks[score_ix].tolist(),'comparisons':outputs,'fit_audits':fit_audits,
      'descriptive_common_calendar_covariance':np.atleast_2d(np.cov(panel,rowvar=False,ddof=0)).tolist(),
      'independent_sample_size_claim':None,'confidence_interval':None,'alpha_allocated':False,
      'economic_or_profit_claim':False,'winner_pruning':False}

def atomic_json(path,obj):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,sort_keys=True,allow_nan=False)+'\n');tmp.replace(path)

def read_production(directory,checkpoint,permit):
    # A capability object is minted only by the signature/HEAD gate.
    from .entrypoint import Permit
    fail(type(permit) is Permit,'SEPARATE_ARM_REQUIRED')
    permit.check()
    m=json.loads(MANIFEST.read_bytes());records=sorted(m['primary_series'],key=lambda x:x['symbol_id'])
    fail(len(records)==145,'PRIMARY145')
    checkpoint=Path(checkpoint);checkpoint.mkdir(parents=True,exist_ok=True)
    # Consume one campaign atomically. Checkpoints preserve completed caches;
    # after a crash this exact ARM cannot restart or reread any source.
    marker=checkpoint/'CONSUMED.json'
    if marker.exists():
        state=json.loads(marker.read_bytes());fail(state['arm_digest']==permit.arm_digest,'CHECKPOINT_ARM')
        raise ValueError('PASS_ALREADY_CONSUMED_NO_REPLAY')
    with marker.open('x') as f:json.dump({'arm_digest':permit.arm_digest,'complete':False},f)
    state={'arm_digest':permit.arm_digest,'complete':False,'caches':{},'parsed_series':0,'parsed_rows':0}
    archive_names={x['sha256']:x['filename'] for x in json.loads((HERE/'RECONCILIATION_AND_CORPUS_V1.json').read_bytes())['archives']}
    archives={}
    try:
        for h,name in archive_names.items():
            permit.check();p=Path(directory)/name
            archives[h]=verified_archive(p,h)
        caches=[]
        for x in records:
            permit.check();raw=accepted_member(archives[x['source_archive_sha256']],x)
            bars=parse_series(raw,x);cache=derive(bars);p=checkpoint/(str(x['symbol_id'])+'.npz')
            with p.with_suffix('.tmp').open('wb') as f:np.savez_compressed(f,**cache)
            p.with_suffix('.tmp').replace(p);state['caches'][str(x['symbol_id'])]=digest(p.read_bytes())
            state['parsed_series']+=1;state['parsed_rows']+=len(bars);atomic_json(marker,state);caches.append(cache)
            del bars,raw
        state['complete']=True;atomic_json(marker,state)
        return caches,[x['symbol_id'] for x in records]
    finally:
        for z in archives.values():z.close()
