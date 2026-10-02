from __future__ import annotations
import argparse,csv,json
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
try:
    from research_core_v4 import response_evaluator_v2 as ev
except ModuleNotFoundError:
    import response_evaluator_v2 as ev

CONTEXTS=("FX_SPOT","SPOT_CRYPTO","US_EQUITY_EXTENDED_HOURS");STATES=("LOW","HIGH");HORIZONS=(3,6,12,48)
HSHAPE=np.array([.5,1.,.75,.4]);DEV_ANCHOR=datetime(2025,9,15,tzinfo=timezone.utc)
PATTERNS={"6_OF_6":np.ones(6),"5_OF_6":np.array([1,1,1,1,1,0.]),"4_OF_6":np.array([1,1,1,1,0,0.]),"3_OF_6":np.array([1,1,1,0,0,0.]),"HETEROGENEOUS":np.array([1.5,1.25,1,.75,.5,.25]),"ONE_OPPOSITE":np.array([1,1,1,1,1,-.5]),"TWO_OPPOSITE":np.array([1,1,1,1,-.5,-.5])}

@dataclass
class Unit:
    symbol:str;week_key:str;week_index:int;direction:int;nf:int;nb:int
@dataclass
class LeafGeometry:
    context:str;state:str;horizon:int;symbols:list[str];units:list[Unit];valid_weeks:list[int];block_ids:np.ndarray;Mblock:np.ndarray;Msymbol:np.ndarray;Mquarter:np.ndarray;Mcontext:np.ndarray

def load_rows(root:Path):
    out=[]
    for c in CONTEXTS:
        with (root/f"V4_SUPPORT_COUNTS_{c}_V1.csv").open(newline="",encoding="utf-8") as f:out.extend(list(csv.DictReader(f)))
    return out

def build_geometry(rows,ctx,state,h):
    fkey=f"full_h{h}";bkey=f"baseline_h{h}";raw=[r for r in rows if r["context"]==ctx and r["vol_state"]==state and int(r[fkey])>0 and int(r[bkey])>0]
    symbols=sorted({r["symbol"] for r in raw});units=[Unit(r["symbol"],r["week_key"],ev.week_index(r["week_key"],DEV_ANCHOR),int(r["signal_direction"]),int(r[fkey]),int(r[bkey])) for r in raw];U=len(units)
    sw_keys=sorted({(u.symbol,u.week_index) for u in units});sw_index={k:i for i,k in enumerate(sw_keys)};Psw=np.zeros((len(sw_keys),U));groups={k:[] for k in sw_keys}
    for i,u in enumerate(units):groups[(u.symbol,u.week_index)].append(i)
    for k,ixs in groups.items():Psw[sw_index[k],ixs]=1/len(ixs)
    valid_weeks=[];week_rows=[]
    for wk in sorted({w for _,w in sw_keys}):
        ixs=[sw_index[k] for k in sw_keys if k[1]==wk]
        if len(ixs)>=4:
            row=np.zeros(len(sw_keys));row[ixs]=1/len(ixs);week_rows.append(row);valid_weeks.append(wk)
    Mweek=np.vstack(week_rows)@Psw;wi={w:i for i,w in enumerate(valid_weeks)};Mb=[];bids=[]
    for bi in range(27):
        if 2*bi in wi and 2*bi+1 in wi:Mb.append((Mweek[wi[2*bi]]+Mweek[wi[2*bi+1]])/2);bids.append(bi)
    Ms=[]
    for sym in symbols:
        ixs=[sw_index[k] for k in sw_keys if k[0]==sym];row=np.zeros(len(sw_keys));row[ixs]=1/len(ixs);Ms.append(row@Psw)
    Mq=[]
    for q in range(4):
        ixs=[i for i,w in enumerate(valid_weeks) if min(3,w*4//53)==q];Mq.append(Mweek[ixs].mean(0))
    return LeafGeometry(ctx,state,h,symbols,units,valid_weeks,np.array(bids,int),np.vstack(Mb),np.vstack(Ms),np.vstack(Mq),Mweek.mean(0))

def all_geometries(rows):return {(c,s,h):build_geometry(rows,c,s,h) for c in CONTEXTS for s in STATES for h in HORIZONS}

def arm_noise(rng,R,g,kind):
    nf=np.array([u.nf for u in g.units],float);nb=np.array([u.nb for u in g.units],float);U=len(g.units)
    if kind=="fat":
        f=rng.standard_t(5,(R,U))/np.sqrt(5/3)/np.sqrt(nf);b=rng.standard_t(5,(R,U))/np.sqrt(5/3)/np.sqrt(nb)
    elif kind=="skew":
        sig=.8;mu=np.exp(sig*sig/2);var=(np.exp(sig*sig)-1)*np.exp(sig*sig);f=(rng.lognormal(0,sig,(R,U))-mu)/np.sqrt(var)/np.sqrt(nf);b=(rng.lognormal(0,sig,(R,U))-mu)/np.sqrt(var)/np.sqrt(nb)
    else:f=rng.normal(size=(R,U))/np.sqrt(nf);b=rng.normal(size=(R,U))/np.sqrt(nb)
    if kind=="hetero":
        sm={s:i for i,s in enumerate(g.symbols)};sc=np.array([.6,.8,1.,1.2,1.5,1.8])[[sm[u.symbol] for u in g.units]];f*=sc;b*=sc
    if kind=="common":
        cf=rng.normal(size=(R,53));cb=rng.normal(size=(R,53));w=np.array([u.week_index for u in g.units]);f=.55*f+.835*cf[:,w]/np.sqrt(nf);b=.55*b+.835*cb[:,w]/np.sqrt(nb)
    return f,b

def vectorized_context_test(block_sets,P,seed):
    R=block_sets[0][1].shape[0];rng=np.random.default_rng(seed);maxid=max(int(ids.max()) for ids,_ in block_sets);signs=rng.choice(np.array([-1.,1.]),size=(P,maxid+1));maxperm=np.full((R,P),-np.inf);obs=[]
    for ids,X in block_sets:
        n=X.shape[1];m=X.mean(1);sd=X.std(1,ddof=1);ot=np.divide(m,sd/np.sqrt(n),out=np.zeros_like(m),where=sd>0);obs.append(ot);S=signs[:,ids];pm=X@S.T/n;ss=(X*X).sum(1)[:,None];var=np.maximum((ss-n*pm*pm)/(n-1),1e-15);pt=pm/np.sqrt(var/n);maxperm=np.maximum(maxperm,pt)
    obs=np.stack(obs,1);p=np.stack([(1+(maxperm>=obs[:,j,None]).sum(1))/(P+1) for j in range(obs.shape[1])],1);sel=p.argmin(1)
    prod=ev.local_shared_maxT([(ids,X[0]) for ids,X in block_sets],P,seed)
    if abs(prod["family_p"]-float(p[0,sel[0]]))>1e-12:raise AssertionError("calibration/production maxT mismatch")
    return p.min(1),sel

def holm_matrix(p):
    out=np.zeros_like(p,dtype=bool)
    for r in range(len(p)):out[r]=ev.holm_reject(p[r])
    return out

def simulate(geoms,R,effect=0.,pattern="6_OF_6",state_scenario="BOTH",noise="normal",P=1023,seed=1,active_ctx=0):
    rng=np.random.default_rng(seed);fam=np.zeros((R,3));sels=np.zeros((R,3),int);gates=np.zeros((R,3),bool)
    for ci,ctx in enumerate(CONTEXTS):
        block_sets=[];symsets=[];qsets=[];fullctx=[]
        for state in STATES:
            sm=0.
            if ci==active_ctx:sm=1. if state_scenario=="BOTH" else (1. if state_scenario==f"{state}_ONLY" else 0.)
            for hi,h in enumerate(HORIZONS):
                g=geoms[(ctx,state,h)];f,b=arm_noise(rng,R,g,noise);sidx={s:i for i,s in enumerate(g.symbols)};ids=np.array([sidx[u.symbol] for u in g.units]);f+=effect*PATTERNS[pattern][ids]*HSHAPE[hi]*sm;d=f-b;block_sets.append((g.block_ids,d@g.Mblock.T));symsets.append(d@g.Msymbol.T);qsets.append(d@g.Mquarter.T);fullctx.append(f@g.Mcontext)
        fam[:,ci],sels[:,ci]=vectorized_context_test(block_sets,P,seed+1000+ci)
        for r in range(R):
            j=sels[r,ci];sv=symsets[j][r];qv=qsets[j][r];den=np.abs(sv).sum();gates[r,ci]=((sv>0).sum()>=3 and (qv>0).sum()>=3 and den>0 and np.max(np.abs(sv))/den<=.5 and fullctx[j][r]>0)
    rej=holm_matrix(fam);lead=rej&gates
    return {"global_any":float(lead.any(1).mean()),"active_context":float(lead[:,active_ctx].mean()),"per_context":[float(lead[:,i].mean()) for i in range(3)],"holm_any":float(rej.any(1).mean())}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--support-root",type=Path,default=Path("research_core_v4/support"));ap.add_argument("--smoke",action="store_true");ap.add_argument("--output",type=Path);a=ap.parse_args();rows=load_rows(a.support_root);g=all_geometries(rows);R=100 if a.smoke else 1000;P=127 if a.smoke else 1023
    result={"market_responses_used":False,"support_rows":len(rows),"P":P,"negative":simulate(g,R,0,noise="normal",P=P,seed=11),"positive":simulate(g,R,.08,pattern="4_OF_6",state_scenario="HIGH_ONLY",P=P,seed=12)}
    txt=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if a.output:a.output.write_text(txt,encoding="utf-8")
    else:print(txt,end="")
if __name__=="__main__":main()
