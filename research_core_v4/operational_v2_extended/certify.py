"""Fixed-k15 extended finite-envelope certification; immutable V2 science."""
import argparse,hashlib,json,pathlib,sys,socket,time
import numpy as np
R=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(R/'research_core_v4/operational_v2'))
from bank import core,canonical,sha
S='research_core_v4/state/'
P=S+'STRICT_PREOUTCOME_OPERATIONAL_V2_EXTENDED_DOMAIN_CERTIFICATION_PROTOCOL_V1.json'
M=S+'STRICT_PREOUTCOME_OPERATIONAL_V2_EXTENDED_DOMAIN_SEED_MANIFEST_V1.json'
def seed(h,domain,component,case):
 return int.from_bytes(hashlib.sha256(h.encode()+b'\0'+domain.encode()+b'\0'+component.encode()+b'\0'+case.encode()).digest(),'big')
def verify():
 p=json.loads((R/P).read_bytes());m=json.loads((R/M).read_bytes());h=sha(R/P)
 for path,digest in p['immutable_files_sha256'].items():assert sha(R/path)==digest,path
 assert m['protocol_sha256']==h and p['selected_k']==15 and p['alpha_V2']==15/1024 and p['wilson_z']==4.669289888046892
 assert len(p['null_cases'])==10 and p['profiles']==[24,28] and p['trials_per_cell']==16384 and p['bootstrap_draws']==1023
 values=[]
 for profile in p['profiles']:
  domain='EXTENDED_CERTIFICATION_'+str(profile)
  for case in ['COMMON']+p['null_cases']:
   component='MULTIPLIERS' if case=='COMMON' else 'INNOVATIONS';v=seed(h,domain,component,case);assert m['seeds'][str(profile)][component][case]==format(v,'064x');values.append(v)
 assert len(set(values))==len(values) and not set(values)&set(int(x,16) for x in m['prior_seed_hex'])
 engine,gen=core();v1=json.loads((R/p['invariant_power_ref']).read_bytes());old=json.loads((R/p['existing_certificate_ref']).read_bytes())
 uppers=[float(engine.wilson(c['selected_false_complete_leads'],c['trials'],p['wilson_z'])[1]) for c in old['cells']];assert max(uppers)<=.05
 z=p['wilson_z'];assert z/(2*np.sqrt(p['trials_per_cell']+z*z))<=.02
 checks={'fixed_k15':True,'all_immutable_files_exact':True,'all22_new_seed_values_disjoint':True,'prior30_reexpressed_max_upper':max(uppers),'new_z_exact':True,'halfwidth':z/(2*np.sqrt(p['trials_per_cell']+z*z)),'prior_stage6_unchanged':True}
 # Exact old engine versus the frozen rank/support/stability decision at k15.
 rng=np.random.default_rng(17);x,mk=gen.generate(v1,'AR050',2,24,rng);g=engine.cluster(x,mk);bank=np.random.default_rng(19).choice([-1.,1.],size=(1023,24));ref=engine.bootstrap_max(g,bank);_,_,pv,t=engine.decisions(g,ref,np.zeros((2,261)));brute=(1+(ref[:,:,None]>=t[:,None,:]).sum(1))/1024;assert np.array_equal(pv,brute)
 checks['exact_rank_full261_support_stability_fixture']=True
 return p,checks

def run(profile,case,out):
 p,checks=verify();assert profile in p['profiles'] and case in p['null_cases'];engine,gen=core();v1=json.loads((R/p['invariant_power_ref']).read_bytes());h=sha(R/P);domain='EXTENDED_CERTIFICATION_'+str(profile)
 ss=seed(h,domain,'INNOVATIONS',case);bs=seed(h,domain,'MULTIPLIERS','COMMON');rng=np.random.default_rng(ss);bank=np.random.default_rng(bs).choice([-1.,1.],size=(1023,profile));N=p['trials_per_cell'];counts=np.zeros(2,np.int64);supported=0;witness=hashlib.sha256();begin=time.monotonic()
 def deny(*a,**k):raise RuntimeError('SYNTHETIC_NO_NETWORK_OR_BROKER')
 socket.socket=deny;socket.create_connection=deny;socket.getaddrinfo=deny
 for start in range(0,N,16):
  n=min(16,N-start);x,m=gen.generate(v1,case,n,profile,rng);g=engine.cluster(x,m);ref=engine.bootstrap_max(g,bank);_,_,pv,_=engine.decisions(g,ref,np.zeros((n,261)))
  sig=(pv<=15/1024)&g['support'];lead=sig&((g['third']>0).sum(1)>=2);counts+=np.array([lead.any(1).sum(),sig.any(1).sum()],np.int64);supported+=int(g['support'].all(1).sum());witness.update(g['u'].tobytes());witness.update(ref.tobytes())
 lo,hi=engine.wilson(counts,N,p['wilson_z'])
 result={'schema':'mxm.operational-v2.extended-fixed-cutoff-null-cell.v1','domain':domain,'protocol_sha256':h,'seed_manifest_sha256':sha(R/M),'case':case,'weekly_calendar_blocks':profile,'trials':N,'selected_k':15,'alpha_V2':15/1024,'wilson_z':p['wilson_z'],'confidence_family_size':16543,'innovations_seed_hex':format(ss,'064x'),'multiplier_seed_hex':format(bs,'064x'),'multiplier_bank_sha256':hashlib.sha256(bank.tobytes()).hexdigest(),'false_complete_lead_count':int(counts[0]),'false_complete_lead_rate':float(counts[0]/N),'simultaneous_wilson_lower':float(lo[0]),'simultaneous_wilson_upper':float(hi[0]),'false_significance_count':int(counts[1]),'false_significance_upper':float(hi[1]),'all_leaf_support_trials':supported,'witness_sha256':witness.hexdigest(),'pass':bool(hi[0]<=.05),'checks':checks,'seconds':time.monotonic()-begin,'broker_requests':0,'real_inputs':0,'orders':0,'calibration_bank_created':False}
 pathlib.Path(out).write_bytes(canonical(result));print('EXTENDED_CELL_RESULT='+json.dumps(result,sort_keys=True),flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--profile',type=int);a.add_argument('--case');a.add_argument('--output');a.add_argument('--verify',action='store_true');args=a.parse_args()
 if args.verify:print(json.dumps(verify()[1],sort_keys=True))
 else:run(args.profile,args.case,args.output)
