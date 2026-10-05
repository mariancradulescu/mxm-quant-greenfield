"""Prospective complete-family null stress and power in statistical units only."""
import json
import numpy as np
from research_core_v4.online_change_v1 import hac_t,require

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
    return {'schema':'mxm.v4.online-change-calibration.v1','null':null,'power':power,'mc_pass':bool(mc),'power_pass':bool(pg),'pass':bool(mc and pg),
            'market_data_used':False,'threshold_retuned':False,'inference_component_pass':bool(mc and pg),'units':'SD of two-week context score; not bps or profit','precision_trials_prospectively_fixed':N}

def normalize(prefix):
    x=prefix[:,:-1];y=prefix[:,1:];mx=x.mean(axis=1);my=y.mean(axis=1)
    phi=np.clip(np.sum((x-mx[:,None])*(y-my[:,None]),axis=1)/np.sum((x-mx[:,None])**2,axis=1),-.95,.95)
    intercept=my-phi*mx;sigma=np.sqrt(np.mean((y-intercept[:,None]-phi[:,None]*x)**2,axis=1))
    return phi,intercept,sigma

def synthetic_path(rng,case,trials,n):
    # Linear finite stable impulse-response filtering with a128clock burn.
    e=rng.normal(size=(trials,n+128))
    if case=='heavy_t5':e=rng.standard_t(5,size=e.shape)/np.sqrt(5/3)
    if case=='heteroscedastic':e*=np.exp(.7*rng.normal(size=e.shape))
    if case in ['AR1_050','AR2_035_020']:
        a,b=(.5,0.) if case=='AR1_050' else (.35,.2)
        kernel=np.zeros(128);kernel[0]=1.
        for k in range(1,128):kernel[k]=a*kernel[k-1]+(b*kernel[k-2] if k>1 else 0.)
        kernel/=np.sqrt(np.sum(kernel*kernel));length=1<<(e.shape[1]+127-1).bit_length()
        e=np.fft.irfft(np.fft.rfft(e,n=length)*np.fft.rfft(kernel,n=length)[None,:],n=length)[:,:e.shape[1]]
    return e[:,128:]

def first_passage(u,d):
    f=d['detector'];hits=[]
    for sign in [1,-1]:
        s=np.cumsum(sign*f['bet']*u-f['bet']**2/2,axis=1)
        floor=np.minimum.accumulate(np.minimum(np.c_[np.zeros(len(s)),s[:,:-1]],0),axis=1)
        crossed=(s-floor)>=f['threshold'];first=np.argmax(crossed,axis=1)+1
        first[~np.any(crossed,axis=1)]=u.shape[1]+1;hits.append(first)
    positive,negative=hits
    return np.minimum(positive,negative),np.where(positive<negative,1,np.where(negative<positive,-1,0))

def sequential_run(d):
    f=d['sequential_calibration'];rng=np.random.default_rng(f['seed']);N=f['trials_per_null_case'];P=f['normalization_clocks'];L=f['campaign_clocks'];null={}
    for case in f['null_cases']:
        k=0
        for start in range(0,N,16):
            count=min(16,N-start);path=synthetic_path(rng,case,count,P+L+1);phi,intercept,sigma=normalize(path[:,:P+1]);future=path[:,P+1:];previous=path[:,P:-1]
            if case=='variance_break':
                path[:,P+1+L//2:]*=2.;future=path[:,P+1:];previous=path[:,P:-1]
            u=np.clip((future-intercept[:,None]-phi[:,None]*previous)/sigma[:,None],-1,1)
            first,direction=first_passage(u,d);k+=int(np.sum(first<=L))
        upper=wilson(k,N,f['simultaneous_wilson_z']);family=min(1.,18*upper[1])
        null[case]={'single_stream_campaign_alarms':k,'trials':N,'single_stream_simultaneous_wilson':upper,'full18_stream_union_upper':family,'pass':family<=f['family_alarm_ceiling']}
        print(json.dumps({'sequential_null_case':case,'family_upper':family}),flush=True)
    power={};deadline=f['change_detection_deadline_clocks']
    for case in f['change_cases']:
        power[case]={str(effect):{str(direction):{'first':[],'detected':[]} for direction in [1,-1]} for effect in f['change_effects_innovation_sd']}
        rho=.5 if case=='AR1_050' else 0.
        response_profile=(1-rho**np.arange(1,deadline+1))/(1-rho)
        for start in range(0,N,16):
            count=min(16,N-start);path=synthetic_path(rng,case,count,P+deadline+1);phi,intercept,sigma=normalize(path[:,:P+1]);future=path[:,P+1:];previous=path[:,P:-1]
            for effect in f['change_effects_innovation_sd']:
                for direction in [1,-1]:
                    shift=direction*effect*sigma[:,None]*response_profile[None,:]
                    previous_shift=np.c_[np.zeros(count),shift[:,:-1]]
                    u=np.clip((future+shift-intercept[:,None]-phi[:,None]*(previous+previous_shift))/sigma[:,None],-1,1)
                    first,detected=first_passage(u,d);cell=power[case][str(effect)][str(direction)]
                    cell['first'].extend(first.tolist());cell['detected'].extend(detected.tolist())
        for cells in power[case].values():
            for direction,cell in list(cells.items()):
                first=np.array(cell['first']);detected=np.array(cell['detected']);success=(first<=deadline)&(detected==int(direction));wrong=(first<=deadline)&(detected==-int(direction));delays=first[success]
                cells[direction]={'detections':int(success.sum()),'wrong_direction':int(wrong.sum()),'trials':N,'power':float(success.mean()),'power_wilson95':wilson(int(success.sum()),N,1.96),'wrong_wilson95':wilson(int(wrong.sum()),N,1.96),'detected_delay_quantiles':np.quantile(delays,[.1,.5,.9]).tolist() if len(delays) else None,'censored':int((first>deadline).sum())}
    ng=all(v['pass'] for v in null.values());pg=all(v['power_wilson95'][0]>=f['change_gate_lower_wilson_min'] and v['wrong_wilson95'][1]<=f['change_gate_direction_error_upper'] for c in power.values() for v in c[str(f['change_gate_effect'])].values())
    return {'null':null,'power':power,'false_alarm_pass':bool(ng),'detection_power_pass':bool(pg),'pass':bool(ng and pg),'campaign_clocks':L,'no_market_data':True,'all_trials_predeclared':True,'threshold_retuned':False}

if __name__=='__main__':
    from pathlib import Path
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    d=json.loads(Path('research_core_v4/state/ONLINE_CHANGE_DESIGN_V1.json').read_bytes())
    result=run(d)
    result['sequential']=sequential_run(d)
    result['pass']=bool(result['pass'] and result['sequential']['pass'])
    Path(a.output).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
