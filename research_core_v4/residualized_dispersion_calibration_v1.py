"""Frozen complete-family stress calibration, extraction invariants and power."""
import json
import numpy as np
from research_core_v4 import residualized_dispersion_v1 as v

def wilson(k,n,z):
    p=k/n;den=1+z*z/n;center=(p+z*z/(2*n))/den;width=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [float(center-width),float(center+width)]

def generate(rng,case,N,n):
    x=rng.normal(size=(N,2,n+100))
    if case in ['AR025','AR050']:
        rho=.25 if case=='AR025' else .5
        for t in range(1,n+100):x[:,:,t]=rho*x[:,:,t-1]+np.sqrt(1-rho*rho)*x[:,:,t]
    elif case=='heavy_t5':x=rng.standard_t(5,size=x.shape)/np.sqrt(5/3)
    elif case=='median_centered_skew':x=rng.exponential(size=x.shape)-np.log(2)
    elif case=='heteroscedastic':x*=np.exp(.7*rng.normal(size=(N,1,n+100)))
    elif case=='shared_factor':x=.4*x+np.sqrt(.84)*rng.normal(size=(N,1,n+100))
    elif case=='variance_ramp':x*=np.linspace(.5,2,n+100)
    elif case!='normal':raise ValueError(case)
    return x[:,:,-n:]

def inference_run(d):
    f=d['inference'];rng=np.random.default_rng(f['seed']);N=f['null_calibration_trials_per_case'];null={}
    for n in f['calibration_block_counts']:
        for case in f['null_cases']:
            x=generate(rng,case,N,n);k=int(v.family_rejections(x,d).sum());ci=wilson(k,N,f['simultaneous_wilson_z'])
            null[f'{n}:{case}']={'family_rejections':k,'trials':N,'rate':k/N,'simultaneous_wilson':ci,'critical_count':v.critical_count(n,f['family_alpha'])}
    blocks=list(range(2,20));power={}
    for case in ['normal','AR025','AR050']:
        base=generate(rng,case,N,len(blocks));dev=rng.normal(size=(N,2,6,len(blocks)));dev-=dev.mean(axis=2,keepdims=True);power[case]={}
        for effect in f['power_effects_block_sd']:
            power[case][str(effect)]={}
            for direction in [1,-1]:
                x=base+direction*effect;assets=x[:,:,None,:]+dev;k=int(v.complete_lead(x,assets,blocks,d).sum())
                power[case][str(effect)][str(direction)]={'complete_leads':k,'trials':N,'rate':k/N,'wilson95':wilson(k,N,1.96)}
    mc=all(x['simultaneous_wilson'][1]<=f['alpha_ceiling'] for x in null.values())
    pg=all(power[c][str(f['power_gate_effect'])][str(s)]['wilson95'][0]>=f['power_gate_lower_wilson_min'] for c in f['power_gate_cases'] for s in [1,-1])
    return {'null':null,'power':power,'error_control_pass':bool(mc),'power_pass':bool(pg),'pass':bool(mc and pg),'all_trials_prospectively_fixed':True,'units':'two-week score SD; not bps/profit','inference_assumptions':'Exact independent zero-median signs reference; empirical finite stress certification only, not arbitrary temporal dependence.'}

def feature_run(d):
    f=d['feature_calibration'];rng=np.random.default_rng(f['seed']);N=f['trials_per_case'];P=f['prefix_clocks'];L=f['evaluation_clocks'];report={}
    dd=dict(d);dd.update(training_start=0,normalization_end=(P+13)*300,training_end=(2*P+13)*300,evaluation_start=(2*P+40)*300,evaluation_end_exclusive=(2*P+40+L)*300);dd['support']=dict(d['support'],normalization_clocks_min=1000,prefix_clocks_min=1000)
    T=2*P+40+L;times=np.arange(13,T)*300
    for case in f['cases']:
        failures=[];max_orth=0.;max_energy=0.;gap_test_count=0
        for trial in range(N):
            common=rng.normal(size=(T,1));own=rng.standard_t(5,size=(T,6))/np.sqrt(5/3) if case=='heavy_t5_shared_factor' else rng.normal(size=(T,6))
            rr=(.7*common+np.sqrt(.51)*own)*.001
            if case=='AR050_shared_factor':
                for j in range(1,T):rr[j]=.5*rr[j-1]+np.sqrt(.75)*rr[j]
            logs=np.cumsum(rr,axis=0);r=logs[13:]-logs[1:T-12];tt=times.copy()
            if case=='daily_gap_shared_factor':
                # Different member missing on alternating days; full current-hour panel excludes all13 affected clocks.
                missing=set(range(288,T,288));keep=np.array([not any(int(t)//300-k in missing for k in range(13)) for t in tt]);r=r[keep];tt=tt[keep];gap_test_count+=len(missing)
            try:
                m=v.fit_panel_normalization(tt,r,dd);inter,z,disp=v.features(tt,r,m);ii=(tt>=dd['normalization_end']+3600)&(tt<=dd['training_end']-3600)
                v.require(ii.sum()>=1000,'synthetic prefix support')
                for sid in range(6):
                    zz=z[ii,sid];v.require(np.linalg.matrix_rank(zz)==7,'synthetic rank');b=np.linalg.lstsq(zz,inter[ii,sid],rcond=None)[0];res=inter[ii,sid]-zz@b
                    orth=float(np.max(np.abs(zz.T@res))/(max(1.,np.linalg.norm(zz)*np.linalg.norm(res))));max_orth=max(max_orth,orth);v.require(orth<=1e-8,'projection orthogonality')
                g=np.clip((r-m['alpha']-np.array(m['beta'])*v.factor_returns(r))/m['sigma'],-4,4)
                energy=float(np.max(np.abs(disp*disp-np.maximum((np.sum(g*g,axis=1,keepdims=True)-g*g)/5,0))));max_energy=max(max_energy,energy);v.require(energy<=1e-12,'energy identity')
                # Modify future panel values only: frozen normalization and all prior features invariant.
                cutoff=dd['evaluation_start']+300*L//2;changed=r.copy();changed[tt>cutoff]+=10
                i2,z2,_=v.features(tt,changed,m);prior=tt<=cutoff;v.require(np.array_equal(inter[prior],i2[prior]) and np.array_equal(z[prior],z2[prior]),'future leakage')
                m2=v.fit_panel_normalization(tt,changed,dd);v.require(v.canonical(m)==v.canonical(m2),'future normalization leak')
            except ValueError as e:failures.append({'trial':trial,'reason':str(e)})
        report[case]={'trials':N,'failures':failures,'pass':not failures,'max_relative_orthogonality_error':max_orth,'max_energy_identity_error':max_energy,'synthetic_gap_positions_checked':gap_test_count}
        print(json.dumps({'feature_case':case,'pass':not failures,'failures':len(failures)}),flush=True)
    return {'cases':report,'pass':all(c['pass'] for c in report.values()),'market_data_used':False,'feature_power_claimed':False,'smaller_synthetic_prefix_is_invariant_test_only_not_real_support_relaxation':True}

def run(d):
    i=inference_run(d);f=feature_run(d)
    return {'schema':'mxm.v4.dispersion-calibration.v1','inference':i,'feature_integrity':f,'pass':bool(i['pass'] and f['pass']),'market_data_used':False,'seed_reselected':False,'scientific_law_retuned':False}

if __name__=='__main__':
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    import os
    from tools.residualized_dispersion_preoutcome import binding,environment,network_fence
    request=binding();network_fence();d=json.loads(Path('research_core_v4/state/RESIDUALIZED_DISPERSION_DESIGN_V1.json').read_bytes());result=run(d)
    result.update(trigger_head=os.environ['GITHUB_SHA'],run_id=int(os.environ['GITHUB_RUN_ID']),source_binding=request['file_sha256'],environment=environment(),real_response_opened=False,broker_contacts=0,historical_requests=0)
    Path(a.output).write_bytes(v.canonical(result)+b'\n')
