"""Prospective daily-gap detector stress, no market prices or response access."""
import json,os,platform
from pathlib import Path
import numpy as np
from research_core_v4.online_change_v1 import require,sha
from research_core_v4.online_change_calibration_v1 import synthetic_path,normalize,wilson

def passage_with_gap(u,d,phase):
    N,L=u.shape;positive=np.zeros(N);negative=np.zeros(N);wait=np.zeros(N,dtype=int)
    first=np.full(N,L+1);direction=np.zeros(N,dtype=int);f=d['detector'];eta=f['bet'];h=f['threshold']
    for j in range(L):
        gap=(phase+j)%288==0;blocked=gap|(wait>0)
        positive[blocked]=negative[blocked]=0.
        wait=np.where(gap,2,np.maximum(0,wait-1))
        positive=np.where(blocked,0.,np.maximum(0.,positive+eta*u[:,j]-eta**2/2))
        negative=np.where(blocked,0.,np.maximum(0.,negative-eta*u[:,j]-eta**2/2))
        hit=(first>L)&((positive>=h)|(negative>=h))
        first[hit]=j+1;direction[hit]=np.where(positive[hit]>=h,1,-1)
    return first,direction

def run(d):
    g=d['gap_power_calibration'];f=d['sequential_calibration'];N=g['trials'];P=f['normalization_clocks'];L=f['change_detection_deadline_clocks'];rng=np.random.default_rng(g['seed']);out={}
    for case in f['change_cases']:
        path=synthetic_path(rng,case,N,P+L+1);phi,b,sigma=normalize(path[:,:P+1]);future=path[:,P+1:];previous=path[:,P:-1]
        rho=.5 if case=='AR1_050' else 0.;profile=(1-rho**np.arange(1,L+1))/(1-rho)
        phase=rng.integers(288,size=N);out[case]={}
        for effect in f['change_effects_innovation_sd']:
            out[case][str(effect)]={}
            for sign in [1,-1]:
                shift=sign*effect*sigma[:,None]*profile[None,:];previous_shift=np.c_[np.zeros(N),shift[:,:-1]]
                u=np.clip((future+shift-b[:,None]-phi[:,None]*(previous+previous_shift))/sigma[:,None],-1,1)
                first,direction=passage_with_gap(u,d,phase);success=(first<=L)&(direction==sign);wrong=(first<=L)&(direction==-sign);delays=first[success]
                out[case][str(effect)][str(sign)]={'detections':int(success.sum()),'trials':N,'power':float(success.mean()),'power_wilson95':wilson(int(success.sum()),N,1.96),'wrong_direction_wilson95':wilson(int(wrong.sum()),N,1.96),'delay_quantiles_detected_only':np.quantile(delays,[.1,.5,.9]).tolist() if len(delays) else None,'censored':int((first>L).sum())}
        print(json.dumps({'gap_case_completed':case}),flush=True)
    gate=all(v['power_wilson95'][0]>=f['change_gate_lower_wilson_min'] and v['wrong_direction_wilson95'][1]<=f['change_gate_direction_error_upper'] for cells in out.values() for v in cells[str(f['change_gate_effect'])].values())
    return {'schema':'mxm.v4.online-change-gap-power.v1','power':out,'pass':bool(gate),'source_binding':json.loads(Path('research_core_v4/state/ONLINE_CHANGE_GAP_POWER_REQUEST_V1.json').read_bytes())['file_sha256'],'source_head':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),'market_data_used':False,'real_response_opened':False,'scientific_threshold_changed':False,'conditional_assumptions':'Uniform onset phase relative to daily288clock cycle,one missing clock then2return-link recovery clocks,zero counters at change onset. Same frozen0.5prefix-SD alternative and1008clock deadline; not proof of arbitrary missingness or economic power.','broker_contacts':0,'historical_requests':0}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();r=json.loads(Path('research_core_v4/state/ONLINE_CHANGE_GAP_POWER_REQUEST_V1.json').read_bytes())
    for f,h in r['file_sha256'].items():require(sha(Path(f).read_bytes())==h,'gap proof exact source '+f)
    require(platform.python_version()=='3.11.16' and np.__version__=='2.4.6','numeric versions');require(os.environ.get('GITHUB_RUN_ATTEMPT')=='1','no repeat')
    d=json.loads(Path('research_core_v4/state/ONLINE_CHANGE_DESIGN_V1.json').read_bytes());Path(a.output).write_text(json.dumps(run(d),sort_keys=True,indent=2)+'\n')
