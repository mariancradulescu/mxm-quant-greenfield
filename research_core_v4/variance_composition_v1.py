"""Frozen dense variance concentration; no acquisition or order capability."""
import csv, hashlib, json, math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import numpy as np

def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(x): return hashlib.sha256(x).hexdigest()
def require(x,m):
    if not x: raise ValueError(m)
def read_series(path):
    out={}
    with Path(path).open() as f:
        for r in csv.DictReader(f):
            t=int(datetime.fromisoformat(r['time_utc'].replace('Z','+00:00')).timestamp())+300
            p=float(r['close']); require(t%300==0 and t not in out and p>0 and math.isfinite(p),'invalid M5')
            out[t]=p
    require(list(out)==sorted(out),'chronology'); return out

def feature(p,t):
    # Only the 13 already completed closes are accessed; all 12 increments exist.
    if not all(t-300*k in p for k in range(13)): return None
    r=np.diff(np.log([p[t-300*k] for k in range(12,-1,-1)]))
    rv=float(r@r)
    if rv<=0: return None
    q=float(np.sum(r**4)/(rv*rv)); c=float(np.sign(r[-1]))
    return q,c,rv

def controls(t,c,rv,model):
    a=2*math.pi*(t%86400)/86400
    # Bound only the nuisance volatility amplitude, never select an event.
    v=max(-4.,min(4.,math.log(rv/model['median_rv'])))
    return np.array([1.,c,c*v,c*math.sin(a),c*math.cos(a)])

def fit_prefix(p,d):
    rows=[]
    for t in sorted(p):
        if d['training_start']+3600<=t<=d['training_end']-3600:
            f=feature(p,t)
            if f is not None and all(t+300*k in p for k in range(1,13)): rows.append((t,f))
    require(len(rows)>=d['support']['prefix_clocks_min'],'prefix support')
    model={'median_rv':float(np.median([f[2] for t,f in rows])),
           'q_mean':float(np.mean([f[0] for t,f in rows]))}
    # Fixed response scale from disjoint prefix own hourly returns only.
    hourly=[math.log(p[t+3600]/p[t]) for t,f in rows if t%3600==0]
    require(len(hourly)>=100,'prefix hourly scale support')
    model['sigma_hour']=float(np.sqrt(np.mean(np.square(hourly))))
    require(model['sigma_hour']>0,'prefix singular response scale')
    z=np.stack([controls(t,f[1],f[2],model) for t,f in rows])
    raw=np.array([f[1]*(f[0]-model['q_mean']) for t,f in rows])
    y=np.array([math.log(p[t+3600]/p[t])/model['sigma_hour'] for t,f in rows])
    require(np.linalg.matrix_rank(z)==5,'prefix nuisance rank')
    bx=np.linalg.lstsq(z,raw,rcond=None)[0]; by=np.linalg.lstsq(z,y,rcond=None)[0]
    sx=float(np.sqrt(np.mean((raw-z@bx)**2)))
    require(sx>1e-10,'singular variance interaction')
    model.update(x_beta=bx.tolist(),y_beta=by.tolist(),x_scale=sx,prefix_clocks=len(rows))
    return model

def causal_row(p,t,model):
    f=feature(p,t)
    if f is None: return None
    q,c,rv=f; z=controls(t,c,rv,model)
    x=(c*(q-model['q_mean'])-float(z@model['x_beta']))/model['x_scale']
    return {'t':t,'x':float(x),'baseline_y':float(z@model['y_beta'])}

def prepare(series,d):
    require(d['training_end']+3600<d['evaluation_start'],'prefix purge')
    models={}; population={}; report={}; all_ok=True
    for context,ids in sorted(d['memberships'].items()):
        require(set(series[context])==set(ids),'exact scope')
        counts={}; context_blocks=[]
        for sid in ids:
            p=series[context][sid]; model=fit_prefix(p,d); models[str(sid)]=model
            rows=[]; weekly=defaultdict(int); possible=0
            for t in sorted(p):
                if not d['evaluation_start']<=t<d['evaluation_end_exclusive']: continue
                row=causal_row(p,t,model)
                if row is None: continue
                possible+=1
                # Membership tests only: do not read ANY future price.
                if not all(t+300*k in p for k in range(1,13)): continue
                row.update(sid=sid,context=context,week=(t-d['evaluation_start'])//604800)
                rows.append(row); weekly[row['week']]+=1
            blocks=[b for b in range(21) if weekly[2*b]>=d['support']['per_week_clocks_min'] and weekly[2*b+1]>=d['support']['per_week_clocks_min']]
            retention=len(rows)/max(1,possible)
            ok=len(rows)>=d['support']['per_symbol_clocks_min'] and retention>=d['support']['retention_min']
            counts[str(sid)]={'feature_clocks':possible,'retained_clocks':len(rows),'retention':retention,'blocks':blocks,'prefix_clocks':model['prefix_clocks'],'pass':ok}
            context_blocks.append(set(blocks)); population[str(sid)]=rows; all_ok=all_ok and ok
        joint=sorted(set.intersection(*context_blocks))
        report[context]={'symbols':counts,'blocks':joint}
    joint=sorted(set.intersection(*(set(v['blocks']) for v in report.values())))
    geometry=len(joint)>=d['support']['joint_blocks_min'] and bool(joint) and joint==list(range(joint[0],joint[-1]+1)) and all(sum(b//7==q for b in joint)>=d['support']['blocks_per_third_min'] for q in range(3))
    support={'schema':'mxm.v4.variance-composition-support.v1','pass':bool(all_ok and geometry),'contexts':report,'joint_blocks':joint,
             'population_sha256':sha(canonical(population)),'models_sha256':sha(canonical(models)),
             'models':models,'real_response_opened':False,'broker_contacts':0,'historical_requests':0}
    return support,population

def response(row,p,model):
    t=row['t']; y=math.log(p[t+3600]/p[t])/model['sigma_hour']
    return row['x']*(y-row['baseline_y'])

def raw_result(series,d,support,population,authorized=False):
    require(authorized is True or d.get('synthetic_only') is True,'REAL_RESPONSE_NOT_AUTHORIZED')
    require(support['pass'],'support denied')
    blocks=support['joint_blocks']; values={}; assets={}
    for c,ids in sorted(d['memberships'].items()):
        symbols={}
        for sid in ids:
            byweek=defaultdict(list)
            for row in population[str(sid)]:
                if row['week']//2 in blocks: byweek[row['week']].append(response(row,series[c][sid],support['models'][str(sid)]))
            symbols[str(sid)]=[float(np.mean([np.mean(byweek[2*b]),np.mean(byweek[2*b+1])])) for b in blocks]
        values[c]=np.mean(list(symbols.values()),axis=0).tolist(); assets[c]=symbols
    return {'schema':'mxm.v4.variance-composition-raw.v1','blocks':blocks,'context_block_scores':values,'symbol_block_scores':assets,
            'design_sha256':sha(canonical(d)),'population_sha256':support['population_sha256'],
            'response_opened':True,'profit_claimed':False,'broker_contacts':0,'historical_requests':0}

def hac_t(v):
    v=np.asarray(v,dtype=float); n=v.shape[-1]; mu=np.mean(v,axis=-1); x=v-mu[...,None]
    g=np.mean(x*x,axis=-1)
    for lag in (1,2): g+=2*(1-lag/3)*np.sum(x[...,lag:]*x[...,:-lag],axis=-1)/n
    se=np.sqrt(np.maximum(g,1e-30)/n)
    return mu/se

def infer(v,d,seed=None):
    v=np.asarray(v,dtype=float); n=v.shape[-1]
    require(v.shape==(3,n) and n>=d['support']['joint_blocks_min'],'inference geometry')
    ts=hac_t(v)
    return {'t':ts.tolist(),'absolute_t_cutoff':d['inference']['absolute_t_cutoff'],'means':v.mean(axis=-1).tolist(),
            'pvalues_claimed':False,'calibration':'prospectively frozen full-family synthetic precision gate'}

def interpret(raw,d):
    contexts=sorted(d['memberships']); v=np.array([raw['context_block_scores'][c] for c in contexts])
    info=infer(v,d); signs=np.sign(info['means']); direction=int(signs[0])
    significant=bool(direction!=0 and np.all(signs==direction) and np.all(np.abs(info['t'])>=d['inference']['absolute_t_cutoff']))
    temporal={c:[float(np.mean([x for b,x in zip(raw['blocks'],raw['context_block_scores'][c]) if b//7==q])) for q in range(3)] for c in contexts}
    breadth={c:sum(direction*np.mean(v)>0 for v in raw['symbol_block_scores'][c].values()) for c in contexts}
    lead=significant and all(direction*x>0 for a in temporal.values() for x in a) and all(n>=4 for n in breadth.values())
    return {'schema':'mxm.v4.variance-composition-interpretation.v1','inference':info,'context_order':contexts,'temporal_thirds':temporal,'asset_breadth':breadth,
            'classification':'REPLICATED_INFORMATION_LEAD_COST_UNRESOLVED_DISJOINT_CONFIRMATION_REQUIRED' if lead else 'NO_REPLICATED_INFORMATION_LEAD_SMALL_EFFECTS_LOW_POWER_INCONCLUSIVE',
            'lead':bool(lead),'direction':direction if lead else None,'economic_status':'COST_UNRESOLVED','profit_claimed':False,'economic_null_claimed':False,
            'candidate_frozen_count':0,'candidate_promotion_authorized':False,'confirmation_opened':False,'protected_forward_opened':False}
