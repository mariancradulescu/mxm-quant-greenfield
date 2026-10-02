from __future__ import annotations
import argparse,csv,json,base64,hashlib,io,lzma
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
from pathlib import Path
import numpy as np
try:
    from research_core_v4 import response_evaluator_v3 as ev
    from research_core_v4.frozen_v2_semantics import paired_arm_hierarchical_mean, select_leaf_index
except ModuleNotFoundError:
    import response_evaluator_v3 as ev
    from frozen_v2_semantics import paired_arm_hierarchical_mean, select_leaf_index

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
    manifest=json.loads((root/"SUPPORT_V2_CALIBRATION_GEOMETRY_MANIFEST_V1.json").read_text(encoding="utf-8"))
    encoded="".join((root/p).read_text(encoding="ascii").strip() for p in manifest["transport"]["base64_parts"])
    compressed=base64.b64decode(encoded,validate=True)
    if hashlib.sha256(compressed).hexdigest()!=manifest["transport"]["decoded_xz_sha256"]:
        raise ValueError("support V2 compact transport hash mismatch")
    raw=lzma.decompress(compressed)
    if raw[:4]!=b"SPV4":raise ValueError("support V2 compact transport magic")
    pos=4;out=[]
    fields=["context","symbol","symbol_id","week_key","signal_direction","vol_state","full","baseline","full_h3","baseline_h3","full_h6","baseline_h6","full_h12","baseline_h12","full_h48","baseline_h48"]
    for c in CONTEXTS:
        cfg=manifest["contexts"][c];n=int.from_bytes(raw[pos:pos+2],"little");pos+=2
        if n!=cfg["data_rows"]:raise ValueError("support V2 compact row count "+c)
        rows=[];symbols=cfg["symbols"];ids={k:int(v) for k,v in cfg["symbol_ids"].items()}
        for _ in range(n):
            b=raw[pos:pos+14];pos+=14
            if len(b)!=14:raise ValueError("support V2 compact truncation")
            si,wi,db,sb,*vals=b
            if si>=len(symbols) or wi>52 or db not in (0,1) or sb not in (0,1):raise ValueError("support V2 compact field")
            dt=DEV_ANCHOR+timedelta(weeks=wi);iso=dt.isocalendar();wk=f"{iso.year}-W{iso.week:02d}"
            row={"context":c,"symbol":symbols[si],"symbol_id":str(ids[symbols[si]]),"week_key":wk,"signal_direction":str(1 if db else -1),"vol_state":"HIGH" if sb else "LOW"}
            row.update({k:str(v) for k,v in zip(fields[6:],vals)});rows.append(row)
        buf=io.StringIO(newline="");w=csv.DictWriter(buf,fieldnames=fields,lineterminator="\n");w.writeheader();w.writerows(rows)
        data=buf.getvalue().encode()
        if hashlib.sha256(data).hexdigest()!=cfg["source_csv_sha256"]:
            raise ValueError("support V2 decoded CSV hash mismatch "+c)
        out.extend(rows)
    if pos!=len(raw):raise ValueError("support V2 compact trailing bytes")
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

def vectorized_context_test(block_sets,P,seed,leaf_meta):
    R=block_sets[0][1].shape[0];rng=np.random.default_rng(seed);maxid=max(int(ids.max()) for ids,_ in block_sets);signs=rng.choice(np.array([-1.,1.]),size=(P,maxid+1));maxperm=np.full((R,P),-np.inf);obs=[]
    for ids,X in block_sets:
        n=X.shape[1];m=X.mean(1);sd=X.std(1,ddof=1);ot=np.divide(m,sd/np.sqrt(n),out=np.zeros_like(m),where=sd>0);obs.append(ot);S=signs[:,ids];pm=X@S.T/n;ss=(X*X).sum(1)[:,None];var=np.maximum((ss-n*pm*pm)/(n-1),1e-15);pt=pm/np.sqrt(var/n);maxperm=np.maximum(maxperm,pt)
    obs=np.stack(obs,1);p=np.stack([(1+(maxperm>=obs[:,j,None]).sum(1))/(P+1) for j in range(obs.shape[1])],1)
    sel=np.asarray([select_leaf_index(p[r],obs[r],leaf_meta) for r in range(R)],int)
    family=p[np.arange(R),sel]
    prod=ev.local_shared_maxT([(ids,X[0]) for ids,X in block_sets],P,seed,leaf_meta)
    if prod["selected_index"]!=int(sel[0]) or abs(prod["family_p"]-float(family[0]))>1e-12:
        raise AssertionError("calibration/production selector or maxT mismatch")
    return family,sel

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
        leaf_meta=[(state,h) for state in STATES for h in HORIZONS]
        fam[:,ci],sels[:,ci]=vectorized_context_test(block_sets,P,seed+1000+ci,leaf_meta)
        for r in range(R):
            j=sels[r,ci];sv=symsets[j][r];qv=qsets[j][r];den=np.abs(sv).sum();gates[r,ci]=((sv>0).sum()>=3 and (qv>0).sum()>=3 and den>0 and np.max(np.abs(sv))/den<=.5 and fullctx[j][r]>0)
    rej=holm_matrix(fam);lead=rej&gates
    return {"global_any":float(lead.any(1).mean()),"active_context":float(lead[:,active_ctx].mean()),"per_context":[float(lead[:,i].mean()) for i in range(3)],"holm_any":float(rej.any(1).mean())}

def _full_arm_weighting_parity_check(geoms):
    g=geoms[(CONTEXTS[0],STATES[0],HORIZONS[0])]
    values=np.linspace(-.25,.75,len(g.units))
    units=[
        ev.PairedUnit(g.context,u.symbol,u.week_key,u.direction,g.state,g.horizon,float(values[i]),0.0)
        for i,u in enumerate(g.units)
    ]
    production=paired_arm_hierarchical_mean(units,"FULL",4)
    calibration=float(values@g.Mcontext)
    if production is None or abs(production-calibration)>1e-12:
        raise AssertionError("production/calibration full-arm weighting mismatch")
    return {"production":production,"calibration":calibration,"abs_diff":abs(production-calibration)}


def _interp_mde(grid,power,target):
    for i,(x,y) in enumerate(zip(grid,power)):
        if y>=target:
            if i==0:return x
            x0,y0=grid[i-1],power[i-1]
            return x if y==y0 else x0+(target-y0)*(x-x0)/(y-y0)
    return ">0.20"


def full_report(geoms):
    neg={}
    noise_map={"symmetric_zero_mean":"normal","fat_tailed_t5_zero_mean":"fat","skewed_zero_mean":"skew","heteroskedastic_zero_mean":"hetero","common_factor_zero_mean":"common"}
    for i,(name,noise) in enumerate(noise_map.items()):
        neg[name]=simulate(geoms,1500,0,noise=noise,P=1023,seed=500+i)
    grid=[.04,.06,.08,.10,.12,.15,.20]
    patterns=("6_OF_6","5_OF_6","4_OF_6","3_OF_6","HETEROGENEOUS","ONE_OPPOSITE","TWO_OPPOSITE")
    power={}
    state_power={}
    mde={}
    for ci,ctx in enumerate(CONTEXTS):
        power[ctx]={};mde[ctx]={}
        for pi,pat in enumerate(patterns):
            vals=[]
            for gi,effect in enumerate(grid):
                vals.append(simulate(geoms,300,effect,pattern=pat,state_scenario="BOTH",noise="normal",P=1023,seed=10000+ci*1000+pi*100+gi,active_ctx=ci)["active_context"])
            power[ctx][pat]=vals
            mde[ctx][pat]={"p50":_interp_mde(grid,vals,.50),"p80":_interp_mde(grid,vals,.80),"p90":_interp_mde(grid,vals,.90)}
        state_power[ctx]={}
        for si,scenario in enumerate(("LOW_ONLY","HIGH_ONLY")):
            vals=[]
            for gi,effect in enumerate(grid):
                vals.append(simulate(geoms,300,effect,pattern="6_OF_6",state_scenario=scenario,noise="normal",P=1023,seed=20000+ci*1000+si*100+gi,active_ctx=ci)["active_context"])
            state_power[ctx][scenario]={"power":vals,"mde":{"p50":_interp_mde(grid,vals,.50),"p80":_interp_mde(grid,vals,.80),"p90":_interp_mde(grid,vals,.90)}}
    return {
        "market_responses_used":False,
        "support_rows":sum(1 for _ in load_rows(Path("research_core_v4/support"))),
        "permutations":1023,
        "seed":20261002,
        "selector_rule":"MIN_ADJUSTED_P_THEN_MAX_OBSERVED_T_THEN_SHORTEST_HORIZON_THEN_LOW_BEFORE_HIGH",
        "full_arm_gate":"PAIRED_SUPPORT_EQUAL_DIRECTION_EQUAL_SYMBOL_MEAN_VALID_CONTEXT_WEEKS_GT_ZERO",
        "selector_exact_tiecheck":{
            "leaf_meta":[["LOW",48],["HIGH",3],["LOW",3]],
            "adjusted_p":[.01,.01,.01],
            "observed_t":[2.,2.,2.],
            "selected_index":select_leaf_index([.01,.01,.01],[2.,2.,2.],[("LOW",48),("HIGH",3),("LOW",3)]),
            "expected_index":2,
            "pass":select_leaf_index([.01,.01,.01],[2.,2.,2.],[("LOW",48),("HIGH",3),("LOW",3)])==2
        },
        "full_arm_weighting_parity":_full_arm_weighting_parity_check(geoms),
        "negative_controls":neg,
        "effect_grid_standardized":grid,
        "power_patterns":power,
        "state_specific_power":state_power,
        "standardized_mde":mde,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--support-root",type=Path,default=Path("research_core_v4/support"))
    ap.add_argument("--smoke",action="store_true")
    ap.add_argument("--full",action="store_true")
    ap.add_argument("--output",type=Path)
    a=ap.parse_args()
    rows=load_rows(a.support_root);g=all_geometries(rows)
    if a.full:
        result=full_report(g)
    else:
        R=100 if a.smoke else 300;P=127 if a.smoke else 1023
        result={
            "market_responses_used":False,"support_rows":len(rows),"P":P,
            "selector_tiecheck":select_leaf_index([.01,.01,.01],[2.,2.,2.],[("LOW",48),("HIGH",3),("LOW",3)]),
            "full_arm_weighting_parity":_full_arm_weighting_parity_check(g),
            "negative":simulate(g,R,0,noise="normal",P=P,seed=11),
            "positive":simulate(g,R,.08,pattern="4_OF_6",state_scenario="HIGH_ONLY",P=P,seed=12)
        }
    txt=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if a.output:a.output.write_text(txt,encoding="utf-8")
    else:print(txt,end="")
if __name__=="__main__":main()
