"""Frozen causal sequential change evidence; no acquisition or order capability."""
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

def detector_step(positive,negative,u,d):
    f=d['detector'];eta=f['bet'];penalty=eta*eta/2
    positive=max(0.,positive+eta*u-penalty);negative=max(0.,negative-eta*u-penalty)
    state=(positive-negative)/f['threshold']
    alarm=1 if positive>=f['threshold'] else (-1 if negative>=f['threshold'] else 0)
    if alarm: positive=negative=0.
    return positive,negative,float(state),alarm

def fit_normalization(p,d):
    returns=[];pairs=[];hours=[]
    for t in sorted(p):
        if d['training_start']+600<=t<d['normalization_end'] and t-300 in p and t-600 in p:
            r=math.log(p[t]/p[t-300]);previous=math.log(p[t-300]/p[t-600]);pairs.append((previous,r))
        if d['training_start']+3600<=t<d['normalization_end'] and t%3600==0 and all(t-k*300 in p for k in range(13)):
            hours.append(math.log(p[t]/p[t-3600]))
    require(len(pairs)>=d['support']['normalization_clocks_min'],'normalization prefix support')
    x=np.array([a for a,b in pairs]);y=np.array([b for a,b in pairs]);mx=float(x.mean());my=float(y.mean())
    vx=float(np.sum((x-mx)**2));require(vx>0,'singular AR prefix')
    phi=max(-.95,min(.95,float(np.sum((x-mx)*(y-my))/vx)));intercept=my-phi*mx
    sigma=float(np.sqrt(np.mean((y-intercept-phi*x)**2)));sigma_hour=float(np.sqrt(np.mean(np.square(hours))))
    require(sigma>0 and sigma_hour>0 and len(hours)>=100,'singular prefix scale')
    return {'phi':phi,'intercept':intercept,'sigma':sigma,'sigma_hour':sigma_hour,'normalization_clocks':len(pairs)}

def controls(t,u,hour,model):
    phase=2*math.pi*(t%86400)/86400
    return np.array([1.,u,max(-4.,min(4.,hour/model['sigma_hour'])),math.sin(phase),math.cos(phase)])

def state_rows(p,model,d):
    positive=negative=0.;previous=None;last_t=None;out=[];evaluation_reset=False
    # Normalize only with the disjoint first prefix. Walk forward without rewind.
    for t in sorted(p):
        if not d['normalization_end']<=t<d['evaluation_end_exclusive']:continue
        if t>=d['evaluation_start'] and not evaluation_reset:
            positive=negative=0.;evaluation_reset=True
        if t-300 not in p or (last_t is not None and t-last_t!=300):
            positive=negative=0.;previous=None;last_t=t;continue
        r=math.log(p[t]/p[t-300]);last_t=t
        if previous is None:previous=r;continue
        u=max(-1.,min(1.,(r-model['intercept']-model['phi']*previous)/model['sigma']));previous=r
        positive,negative,state,alarm=detector_step(positive,negative,u,d)
        if not all(t-300*k in p for k in range(13)):continue
        hour=math.log(p[t]/p[t-3600]);z=controls(t,u,hour,model)
        out.append({'t':t,'state':state,'z':z.tolist(),'alarm':alarm})
    return out

def fit_prefix(p,d):
    model=fit_normalization(p,d);all_rows=state_rows(p,model,d)
    rows=[r for r in all_rows if d['normalization_end']+3600<=r['t']<=d['training_end']-3600 and all(r['t']+300*k in p for k in range(1,13))]
    require(len(rows)>=d['support']['prefix_clocks_min'],'second disjoint prefix support')
    z=np.array([r['z'] for r in rows]);x=np.array([r['state'] for r in rows]);y=np.array([math.log(p[r['t']+3600]/p[r['t']])/model['sigma_hour'] for r in rows])
    require(np.linalg.matrix_rank(z)==5,'prefix control rank')
    bx=np.linalg.lstsq(z,x,rcond=None)[0];by=np.linalg.lstsq(z,y,rcond=None)[0];sx=float(np.sqrt(np.mean((x-z@bx)**2)))
    require(sx>1e-10,'singular dense change evidence')
    model.update(x_beta=bx.tolist(),y_beta=by.tolist(),x_scale=sx,prefix_clocks=len(rows))
    return model,all_rows

def causal_row(row,model):
    z=np.array(row['z']);x=(row['state']-float(z@model['x_beta']))/model['x_scale']
    return {'t':row['t'],'x':float(x),'baseline_y':float(z@model['y_beta']),'alarm':row['alarm']}

def prepare(series,d):
    require(d['training_end']+3600<d['evaluation_start'],'prefix purge')
    models={}; population={}; report={}; all_ok=True
    for context,ids in sorted(d['memberships'].items()):
        require(set(series[context])==set(ids),'exact scope')
        counts={}; context_blocks=[]
        for sid in ids:
            p=series[context][sid]; model,states=fit_prefix(p,d); models[str(sid)]=model
            rows=[]; weekly=defaultdict(int); possible=0
            for state in states:
                t=state['t']
                if not d['evaluation_start']<=t<d['evaluation_end_exclusive']: continue
                row=causal_row(state,model)
                possible+=1
                # Membership tests only: do not read ANY future price.
                if not all(t+300*k in p for k in range(1,13)): continue
                row.update(sid=sid,context=context,week=(t-d['evaluation_start'])//604800)
                rows.append(row); weekly[row['week']]+=1
            blocks=[b for b in range(21) if weekly[2*b]>=d['support']['per_week_clocks_min'] and weekly[2*b+1]>=d['support']['per_week_clocks_min']]
            retention=len(rows)/max(1,possible)
            ok=len(rows)>=d['support']['per_symbol_clocks_min'] and retention>=d['support']['retention_min']
            counts[str(sid)]={'feature_clocks':possible,'retained_clocks':len(rows),'retention':retention,'blocks':blocks,'prefix_clocks':model['prefix_clocks'],'normalization_clocks':model['normalization_clocks'],'alarms_not_selection':sum(r['alarm']!=0 for r in rows),'pass':ok}
            context_blocks.append(set(blocks)); population[str(sid)]=rows; all_ok=all_ok and ok
        joint=sorted(set.intersection(*context_blocks))
        report[context]={'symbols':counts,'blocks':joint}
    joint=sorted(set.intersection(*(set(v['blocks']) for v in report.values())))
    geometry=len(joint)>=d['support']['joint_blocks_min'] and bool(joint) and joint==list(range(joint[0],joint[-1]+1)) and all(sum(b//7==q for b in joint)>=d['support']['blocks_per_third_min'] for q in range(3))
    support={'schema':'mxm.v4.online-change-support.v1','pass':bool(all_ok and geometry),'contexts':report,'joint_blocks':joint,
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
    return {'schema':'mxm.v4.online-change-raw.v1','blocks':blocks,'context_block_scores':values,'symbol_block_scores':assets,
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
    breadth={c:int(sum(direction*np.mean(v)>0 for v in raw['symbol_block_scores'][c].values())) for c in contexts}
    lead=significant and all(direction*x>0 for a in temporal.values() for x in a) and all(n>=4 for n in breadth.values())
    return {'schema':'mxm.v4.online-change-interpretation.v1','inference':info,'context_order':contexts,'temporal_thirds':temporal,'asset_breadth':breadth,
            'classification':'REPLICATED_INFORMATION_LEAD_COST_UNRESOLVED_DISJOINT_CONFIRMATION_REQUIRED' if lead else 'NO_REPLICATED_INFORMATION_LEAD_SMALL_EFFECTS_LOW_POWER_INCONCLUSIVE',
            'lead':bool(lead),'direction':direction if lead else None,'economic_status':'COST_UNRESOLVED','profit_claimed':False,'economic_null_claimed':False,
            'candidate_frozen_count':0,'candidate_promotion_authorized':False,'confirmation_opened':False,'protected_forward_opened':False}
