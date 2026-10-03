"""Synthetic-only prospective multiplicity scaffolding; never reads quote inputs.

Generates fictional weekly spread-net summaries. Rejection sensitivity ignores
the full temporal/window/concentration lead gates and is explicitly an upper
bound on full-gate power. Real support/noise/exclusion calibration remains blocked.
"""
import argparse,hashlib,json,math,platform
from datetime import date
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
DESIGN=ROOT/'research_core_v4/state/NEXT_QUOTE_SEQUENCE_DESIGN_V1.json'

def holm(p):
    p=np.asarray(p,float);out=np.zeros_like(p,dtype=bool)
    for r in range(len(p)):
        for rank,j in enumerate(np.argsort(p[r],kind='stable')):
            if p[r,j]<=.05/(p.shape[1]-rank):out[r,j]=True
            else:break
    return out

def family_test(x,signs):
    """x = synthetic replicate x symbol x cell x sampled ISO week."""
    n=x.shape[-1];mean=x.mean(-1);ss=(x*x).sum(-1)
    se=np.sqrt(np.maximum((ss-n*mean*mean)/(n-1)/n,1e-15));obs=mean/se
    pm=x@signs.T/n
    ps=np.sqrt(np.maximum((ss[...,None]-n*pm*pm)/(n-1)/n,1e-15))
    mx=(pm/ps).max(axis=2)
    adjusted=np.stack([(1+(mx>=obs[:,:,k,None]).sum(-1))/(len(signs)+1) for k in range(x.shape[2])],axis=2)
    family=adjusted.min(-1)
    return family,holm(family),adjusted

def wilson(k,n):
    z=1.959963984540054;p=k/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.,mid-half),min(1.,mid+half)]

def simulate(replicates=300):
    d=json.loads(DESIGN.read_bytes());weeks=sorted({date.fromisoformat(x).isocalendar()[:2] for x in d['calendar']['dates_utc']});g=len(weeks)
    rng=np.random.default_rng(20261003);signs=rng.choice(np.array([-1.,1.]),size=(4999,g))
    rows=[]
    cases=[(s,0.,0) for s in ['GAUSSIAN','FAT_TAIL_T5','COMMON_FACTOR','DATE_REGIME_WITHIN_WEEK','UNEQUAL_SYMBOL_NOISE','NEGATIVE_SPREAD_DRIFT']]
    cases += [('POWER',effect,active) for active in (1,3,5) for effect in (.25,.5,.75,1.,1.5)]
    for case_no,(stress,effect,active) in enumerate(cases):
        crng=np.random.default_rng(20261003+100*case_no);hits=0;activehits=0
        for offset in range(0,replicates,10):
            r=min(10,replicates-offset)
            base=crng.normal(size=(r,5,12,g))
            if stress=='FAT_TAIL_T5':base=crng.standard_t(5,size=base.shape)/np.sqrt(5/3)
            if stress in ('COMMON_FACTOR','DATE_REGIME_WITHIN_WEEK'):
                # Same ISO-week shock shared across all sampled dates and cells.
                factor=crng.normal(size=(r,1,1,g));base=.6*base+.8*factor
            if stress=='UNEQUAL_SYMBOL_NOISE':base*=np.array([.5,.75,1.,1.5,2.])[None,:,None,None]
            # Cell order L x threshold x orientation x horizon. Two orientations
            # use exact opposite latent directional components plus common costs.
            x=np.empty((r,5,24,g));k=0;b=0
            for lookback in range(2):
                for threshold in range(2):
                    for orientation in (1,-1):
                        for horizon in range(3):
                            bi=lookback*6+threshold*3+horizon
                            x[:,:,k,:]=orientation*base[:,:,bi,:];k+=1
            if stress=='NEGATIVE_SPREAD_DRIFT':x-=.15
            if active:
                # Prospectively chosen one continuation leaf, never selected
                # from a simulation's best realized cell. Costs are not invented.
                x[:,:active,0,:]+=effect
            fam,rejects,_=family_test(x,signs)
            hits+=int(rejects.any(axis=1).sum())
            if active:activehits+=int(rejects[:,:active].any(axis=1).sum())
        rows.append({'scenario':stress,'injected_active_symbols':active,'synthetic_effect_week_noise_SD':effect,
            'replicates':replicates,'any_symbol_Holm_rejections':hits,'any_reject_fraction':hits/replicates,
            'wilson_95_interval_any_reject':wilson(hits,replicates),
            'active_symbol_any_reject_fraction':activehits/replicates if active else None,
            'full_development_lead_power_measured':False})
    null=[r for r in rows if r['injected_active_symbols']==0]
    return {'schema':'mxm.research-core-v4.quote-sequence-synthetic-calibration.v1',
        'status':'SYNTHETIC_INFERENCE_SCAFFOLD_ONLY_REAL_GEOMETRY_AND_FULL_GATE_POWER_UNTESTED',
        'design_sha256':hashlib.sha256(DESIGN.read_bytes()).hexdigest(),'seed':20261003,'resamples':4999,
        'replicates_per_scenario':replicates,'synthetic_sampled_iso_weeks':g,'symbol_families':5,'cells_per_family':24,
        'environment':{'python':platform.python_version(),'numpy':np.__version__,'immutable_market_worker_certified':False},
        'synthetic_scenarios':rows,'all_null_any_reject_fractions_le_0_07':all(r['any_reject_fraction']<=.07 for r in null),
        'power_interpretation':'Multiplicity rejection sensitivity only, upper bound on full lead power because temporal/window/concentration gates are not simulated. No empirical-market bps MDE, equivalence or exclusion claim.',
        'real_inputs_read':0,'market_responses_read_or_computed':0,'broker_calls':0,
        'production_calibration_accepted':False,'new_response_execution_ready':False}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--replicates',type=int,default=300);ap.add_argument('--output',required=True);a=ap.parse_args()
    if a.replicates!=300:raise SystemExit('Prospective proof fixes 300 replicates; no outcome-dependent override')
    result=simulate(a.replicates);Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'synthetic_only':True,'scenarios':len(result['synthetic_scenarios']),'replicates':a.replicates,'null_stress_flag':result['all_null_any_reject_fractions_le_0_07']}))
