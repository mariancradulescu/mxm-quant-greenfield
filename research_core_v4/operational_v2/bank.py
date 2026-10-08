"""Disjoint finite synthetic banks. The exact unchanged V1 generator/reference
are imported from hash-bound paths. Only the operational rejection cutoff differs.
No market route, broker credentials, raw M5 or economic values are accepted.
"""
import argparse,hashlib,importlib.util,json,pathlib,socket,sys,time
import numpy as np
R=pathlib.Path(__file__).resolve().parents[2];S='research_core_v4/state/'
P=S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_INFERENCE_V2_PROTOCOL_V1.json'
C=S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_INFERENCE_V2_CUTOFF_FREEZE_V1.json'
CAL=S+'STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_INFERENCE_V2_CALIBRATION_RESULT_V1.json'
def canonical(x):return (json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def load(p):return json.loads((R/p).read_bytes())
def seed(protocol_bytes,domain,component,case,blocks):
 assert domain in ['CALIBRATION','CERTIFICATION','POWER']
 return int.from_bytes(hashlib.sha256(protocol_bytes+b'\0'+domain.encode()+b'\0'+component.encode()+b'\0'+case.encode()+b'\0'+str(blocks).encode()).digest(),'big')
def core():
 sys.path.insert(0,str(R/'research_core_v4/operational_v1'))
 import inference as engine
 spec=importlib.util.spec_from_file_location('immutable_v1_certify',R/'research_core_v4/operational_v1/certify.py');gen=importlib.util.module_from_spec(spec);spec.loader.exec_module(gen)
 return engine,gen

def cutoff_selection(cal,z):
 assert len(cal['cells'])==30
 engine,_=core();approved=[]
 for k in range(1,26):
  ok=all(float(engine.wilson(c['complete_lead_counts'][k-1],c['trials'],z)[1])<=.05 for c in cal['cells'])
  if ok:approved.append(k)
 best=max(approved) if approved else None
 return best,(best-1 if best is not None and best>1 else None)

def run_cell(domain,case,blocks):
 pb=(R/P).read_bytes();p=json.loads(pb);assert case in p['null_cases'] and blocks in p['geometry_profiles_week_blocks']
 for path,h in p['invariant_v1_inputs_sha256'].items():assert sha(R/path)==h,path
 v1=load(p['invariant_power_ref']);engine,gen=core()
 innovations_seed=seed(pb,domain,'INNOVATIONS',case,blocks);bank_seed=seed(pb,domain,'MULTIPLIERS','COMMON',blocks)
 rng=np.random.default_rng(innovations_seed);bank=np.random.default_rng(bank_seed).choice([-1.,1.],size=(1023,blocks));N=p['trials_per_case_profile'];z=p['wilson']['z']
 kselected=None;cutoff_hash=None
 if domain=='CERTIFICATION':
  cf=load(C);cal=load(CAL);assert cf['protocol_sha256']==hashlib.sha256(pb).hexdigest();assert cf['calibration_result_sha256']==sha(R/CAL)
  best,kselected=cutoff_selection(cal,z);assert cf['largest_acceptable_k']==best and cf['selected_k']==kselected and kselected is not None
  assert cf['freeze_before_certification'] and cf['retuning_allowed'] is False;cutoff_hash=sha(R/C)
 counts=np.zeros(25,np.int64);sigcounts=np.zeros(25,np.int64);supported=0;witness=hashlib.sha256();start_time=time.monotonic()
 def deny(*args,**kwargs):raise RuntimeError('SYNTHETIC_NO_NETWORK')
 socket.socket=deny;socket.create_connection=deny;socket.getaddrinfo=deny
 for start in range(0,N,16):
  n=min(16,N-start);x,m=gen.generate(v1,case,n,blocks,rng);g=engine.cluster(x,m);ref=engine.bootstrap_max(g,bank)
  _,_,pv,_=engine.decisions(g,ref,np.zeros((n,261)))
  pi=np.rint(pv*1024).astype(np.int64);stable=((g['third']>0).sum(1)>=2)
  min_complete=np.where(g['support']&stable,pi,1025).min(1);min_sig=np.where(g['support'],pi,1025).min(1)
  counts+=(min_complete[:,None]<=np.arange(1,26)[None,:]).sum(0);sigcounts+=(min_sig[:,None]<=np.arange(1,26)[None,:]).sum(0)
  supported+=int(g['support'].all(1).sum());witness.update(g['u'].tobytes());witness.update(ref.tobytes())
 lo,hi=engine.wilson(counts,N,z);slo,shi=engine.wilson(sigcounts,N,z)
 out={'schema':'mxm.operational-v2.synthetic-bank-cell.v1','domain':domain,'case':case,'weekly_calendar_blocks':blocks,'trials':N,'protocol_sha256':hashlib.sha256(pb).hexdigest(),'innovations_seed_hex':format(innovations_seed,'064x'),'multiplier_seed_hex':format(bank_seed,'064x'),'multiplier_bank_sha256':hashlib.sha256(bank.tobytes()).hexdigest(),'complete_lead_counts':counts.tolist(),'complete_lead_wilson_lowers':lo.tolist(),'complete_lead_wilson_uppers':hi.tolist(),'false_significance_counts':sigcounts.tolist(),'false_significance_wilson_uppers':shi.tolist(),'all_leaf_support_trials':supported,'witness_sha256':witness.hexdigest(),'seconds':time.monotonic()-start_time,'real_inputs':0,'broker_requests':0}
 if domain=='CERTIFICATION':out.update({'selected_k':kselected,'alpha_V2':kselected/1024,'cutoff_freeze_sha256':cutoff_hash,'selected_false_complete_leads':int(counts[kselected-1]),'selected_wilson_upper':float(hi[kselected-1]),'selected_false_significance_count':int(sigcounts[kselected-1]),'selected_false_significance_wilson_upper':float(shi[kselected-1]),'pass':bool(hi[kselected-1]<=.05)})
 if domain=='CERTIFICATION':
  for key in ['complete_lead_counts','complete_lead_wilson_lowers','complete_lead_wilson_uppers','false_significance_counts','false_significance_wilson_uppers']:out.pop(key)
  out['selected_wilson_lower']=float(lo[kselected-1])
 return out

def software_checks():
 p=load(P);pb=(R/P).read_bytes();engine,gen=core();v1=load(p['invariant_power_ref']);checks={}
 for case in p['null_cases']:
  for b in p['geometry_profiles_week_blocks']:
   a=seed(pb,'CALIBRATION','INNOVATIONS',case,b);c=seed(pb,'CERTIFICATION','INNOVATIONS',case,b);w=seed(pb,'POWER','INNOVATIONS',case,b);assert len({a,c,w})==3
 checks['all_domain_seeds_disjoint']=True
 x=np.sin(np.arange(2*112*261).reshape(2,112,261)*.117);m=np.ones_like(x,bool);g=engine.cluster(x,m)
 bank=np.where(np.arange(1023*16).reshape(1023,16)%3,1.,-1.);ref=engine.bootstrap_max(g,bank);a=engine.decisions(g,ref,np.zeros((2,261)))
 stable=(g['third']>0).sum(1)>=2;v2=(a[2]<=25/1024)&g['support']&stable
 assert np.array_equal(v2,a[0]);checks['k25_exact_V1_decision_equivalence']=True
 shifted=x+np.pad(np.full((2,112,1),.4),((0,0),(0,0),(0,260)));g2=engine.cluster(shifted,m);ref2=engine.bootstrap_max(g2,bank);assert np.allclose(ref,ref2,atol=1e-8);checks['power_translation_invariant_reference']=True
 checks['score_pipeline_immutable_fixtures']=gen.pipeline_checks(v1)
 assert p['power']==v1['power'] and p['precision']==v1['precision'];checks['power_law_and_precision_exact_V1']=True
 assert len(v1['paid_leaves'])==261 and len(v1['sources'])==5;checks['261_paid_leaves_five_sources']=True
 checks['inference_and_generator_sha256_exact']=all(sha(R/path)==h for path,h in p['invariant_v1_inputs_sha256'].items())
 return checks
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--domain',choices=['CALIBRATION','CERTIFICATION']);a.add_argument('--case');a.add_argument('--blocks',type=int);a.add_argument('--output');a.add_argument('--verify',action='store_true');args=a.parse_args()
 if args.verify:print('SOFTWARE_CHECKS='+json.dumps(software_checks(),sort_keys=True))
 else:
  r=run_cell(args.domain,args.case,args.blocks);pathlib.Path(args.output).write_bytes(canonical(r));print('CELL_RESULT='+json.dumps(r,sort_keys=True),flush=True)
