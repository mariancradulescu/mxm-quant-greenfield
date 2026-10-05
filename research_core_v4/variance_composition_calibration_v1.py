"""Prospective complete-family null stress and power in statistical units only."""
import json
import numpy as np
from research_core_v4.variance_composition_v1 import hac_t,require

def wilson(k,n,z):
    p=k/n; den=1+z*z/n; center=(p+z*z/(2*n))/den
    width=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [float(center-width),float(center+width)]

def generate(rng,case,trials,n):
    x=rng.normal(size=(trials,3,n+100))
    if case in ('AR025','AR050'):
        rho=.25 if case=='AR025' else .5
        for t in range(1,n+100): x[:,:,t]=rho*x[:,:,t-1]+np.sqrt(1-rho*rho)*x[:,:,t]
    elif case=='heavy_t5': x=rng.standard_t(5,size=x.shape)/np.sqrt(5/3)
    elif case=='skew_centered': x=(rng.chisquare(3,size=x.shape)-3)/np.sqrt(6)
    elif case=='heteroscedastic': x*=np.exp(.7*rng.normal(size=(trials,1,n+100)))
    elif case=='shared_factor': x=.3*x+np.sqrt(.91)*rng.normal(size=(trials,1,n+100))
    elif case=='variance_ramp': x*=np.linspace(.5,2,n+100)
    elif case!='normal': raise ValueError(case)
    return x[:,:,-n:]

def complete_lead(x,assets,blocks,cutoff):
    means=x.mean(axis=-1); signs=np.sign(means); direction=signs[:,0]
    ok=np.all(signs==direction[:,None],axis=1)&(direction!=0)&np.all(np.abs(hac_t(x))>=cutoff,axis=1)
    for q in range(3):
        ii=np.array([b//7==q for b in blocks]);require(ii.sum()>=5,'calibrated temporal geometry')
        ok&=np.all(direction[:,None]*x[:,:,ii].mean(axis=-1)>0,axis=1)
    ok&=np.all(np.sum(direction[:,None,None]*assets.mean(axis=-1)>0,axis=2)>=4,axis=1)
    return ok

def run(d):
    f=d['inference'];rng=np.random.default_rng(f['seed']);N=f['null_calibration_trials_per_case'];null={}
    for n in f['calibration_block_counts']:
        for case in f['null_cases']:
            x=generate(rng,case,N,n); k=int(np.sum(np.any(np.abs(hac_t(x))>=f['absolute_t_cutoff'],axis=1)))
            null[f'{n}:{case}']={'family_rejections':k,'trials':N,'rate':k/N,'simultaneous_wilson':wilson(k,N,f['simultaneous_wilson_z'])}
    # Exactly the weakest supported contiguous geometry: blocks2..19 has6 per third.
    blocks=list(range(2,20));n=len(blocks);power={}
    for case in ('normal','AR025','AR050'):
        power[case]={}
        base=generate(rng,case,N,n)
        # Correlated symbols whose average is EXACTLY the generated context vector.
        deviations=rng.normal(size=(N,3,6,n));deviations-=deviations.mean(axis=2,keepdims=True)
        for delta in f['power_effects_block_sd']:
            x=base+delta; assets=x[:,:,None,:]+deviations
            k=int(complete_lead(x,assets,blocks,f['absolute_t_cutoff']).sum())
            power[case][str(delta)]={'complete_leads':k,'trials':N,'rate':k/N,'wilson95':wilson(k,N,1.96)}
    mc=all(x['simultaneous_wilson'][1]<=f['alpha_ceiling'] for x in null.values())
    pg=all(power[c][str(f['power_gate_effect'])]['wilson95'][0]>=f['power_gate_lower_wilson_min'] for c in f['power_gate_cases'])
    return {'schema':'mxm.v4.variance-composition-calibration.v1','null':null,'power':power,'mc_pass':bool(mc),'power_pass':bool(pg),'pass':bool(mc and pg),
            'market_data_used':False,'threshold_retuned':False,'units':'SD of two-week context score; not bps or profit','precision_trials_prospectively_fixed':N}

if __name__=='__main__':
    from pathlib import Path
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    d=json.loads(Path('research_core_v4/state/VARIANCE_COMPOSITION_DESIGN_V1.json').read_bytes())
    Path(a.output).write_text(json.dumps(run(d),sort_keys=True,indent=2)+'\n')
