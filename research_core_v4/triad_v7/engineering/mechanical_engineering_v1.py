"""Only mechanical slices. Never call trial, aggregate_case or case interpreter."""
import json,hashlib,time,resource,platform,os,sys,copy
from pathlib import Path
import numpy as np
from execution_candidate_v1 import reference as w,PreparedScores
import sharding_candidate_v1 as sh
P=Path(__file__).resolve().parent
M=json.loads((P.parent/'TRIAL_MANIFEST_V1.json').read_text());PLAN=json.loads((P/'ENGINEERING_TEST_PLAN_V1.json').read_text())
assert not (P.parent/'EXECUTION_ARM_V1.json').exists()
for path,digest in PLAN['bindings'].items():assert w.sha(w.R/path)==digest
G=w.load_geometry();project=w.Projection(P.parent/'projection_bridge_v1.so');SEED=PLAN['engineering_seed']
def digest_array(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def exact(a,b):
 assert a.keys()==b.keys()
 for k in a:assert np.array_equal(a[k],b[k],equal_nan=True),k
class Trace:
 def __init__(self):self.h=hashlib.sha256();self.n=0
 def __call__(self,X,D):
  f=project(X,D);self.n+=1
  for a in (X,D,f['normalized']):self.h.update(np.ascontiguousarray(a).tobytes())
  self.h.update(w.canonical({'candidate':f['candidate'],'support':f['support']}));return f

def sliced(day):
 g=dict(G);g['causal']=G['causal'][day:day+1];g['complete']=G['complete'][day:day+1];return g
first=int(np.flatnonzero(G['complete'].all(axis=(1,2,3)))[0])
report={'schema':'TRIAD_V7_ENGINEERING_MECHANICAL_RAW_V1','plan_sha256':w.sha(P/'ENGINEERING_TEST_PLAN_V1.json'),'complete_statistical_trials_executed':0,'null_Monte_Carlo_trials':0,'power_Monte_Carlo_trials':0,'real_response_openings':0,'future_Y_reads':0,'broker_contacts':0,'new_acquisition':0,'candidate_frozen_count':0,'orders':0,'fixtures':[]}
start=time.perf_counter();projections=0
for case in M['null_cases']:
 rng1=np.random.Generator(np.random.PCG64(SEED+2*case['id']));rng2=np.random.Generator(np.random.PCG64(SEED+2*case['id']+1))
 base,states=w.base_paths(G,case,rng1,rng2)
 # Reproducibility and unchanged RNG implementation, no certification seeds.
 b2,s2=w.base_paths(G,case,np.random.Generator(np.random.PCG64(SEED+2*case['id'])),np.random.Generator(np.random.PCG64(SEED+2*case['id']+1)))
 assert np.array_equal(base,b2) and np.array_equal(states,s2)
 for day in [0,105,209,first]:
  g=sliced(day);engine=PreparedScores(g);c=dict(case);c['rho_before']=case['rho_before'] if day<105 else case['rho_after']
  cells=M['partial_nulls']+M['power_cells'] if day==first else M['partial_nulls']
  for cell in cells:
   a,b=Trace(),Trace();x=w.scores(g,base[day:day+1],c,cell['delta'],a);y=engine.scores(base[day:day+1],c,cell['delta'],b)
   exact(x,y);assert a.n==b.n and a.h.digest()==b.h.digest();projections+=a.n
  report['fixtures'].append({'case_id':case['id'],'original_day':day,'cells_compared':len(cells),'bit_exact_X_D_full_leaveout_certificates_scores_masks':True})
 print('mechanical case',case['id'],'PASS',flush=True)
report['parity_seconds']=time.perf_counter()-start;report['paired_projection_comparisons']=projections
report['full_trial_trace_equivalence']='NOT_ESTABLISHED: one-day slices do not exercise complete 210-day execution/control-plane/raw trial rows'
report['no_changed_scientific_decisions_in_mechanical_slices']=True
report['sharding']={};mh=w.sha(P.parent/'TRIAL_MANIFEST_V1.json')
for phase in ['null','power']:
 for case_id in M['execution_policy'][phase+'_case_order']:
  layout=sh.layout(M,phase,case_id);indices=[i for s in layout for i in range(s['start'],s['stop'])];assert indices==list(range(M[phase+'_trials_per_case']))
  cells=M['partial_nulls'] if phase=='null' else M['power_cells'];parts=[]
  for s in layout:
   n=s['stop']-s['start'];parts.append({**s,'manifest_sha256':mh,'complete':True,'numerical_failures':0,'cells':{c['id']:{**{f:(n if f=='supported' else 0) for f in sh.FIELDS},'per_leaf_lead':[0]*12} for c in cells}})
  t=time.perf_counter();forward=sh.merge(M,phase,case_id,parts);reverse=sh.merge(M,phase,case_id,parts[::-1]);merge_seconds=time.perf_counter()-t
  assert forward==reverse
  for bad in [parts[:-1],parts+parts[:1]]:
   try:sh.merge(M,phase,case_id,bad)
   except AssertionError:pass
   else:raise AssertionError('bad shard set accepted')
  report['sharding'][f'{phase}_{case_id}']={'shards':len(layout),'indices':len(indices),'no_duplicate_no_omission':True,'merge_order_independent':True,'missing_duplicate_rejected':True,'manufactured_count_merge_seconds_two_orders':merge_seconds,'transport_bytes':len(sh.canonical(parts))}
# Inference is the exact same reference function; this is a deterministic
# artificial score fixture, never a DGP certification draw or result estimate.
x=np.arange(210)[:,None];l=np.arange(12)[None,:]
valid=G['complete'].sum(axis=1).reshape(210,12)>=4
daily=np.sin((x+1)*(l+1)*.071)+.3*np.cos(x*.133+l)
loo=np.tile(daily[:,:4,None],(1,1,44)).transpose(0,2,1)
o={'daily':np.where(valid,daily,np.nan),'valid':valid,'loo':loo}
t=time.perf_counter()
for _ in range(20): w.infer(G,o)
report['inference_seconds_per_call']=(time.perf_counter()-t)/20
bench=[]
for cid in [0,16]:
 case=M['null_cases'][cid];rng1=np.random.Generator(np.random.PCG64(SEED+2*cid));rng2=np.random.Generator(np.random.PCG64(SEED+2*cid+1));t=time.perf_counter();base,states=w.base_paths(G,case,rng1,rng2);generation=time.perf_counter()-t
 # All actual days are scored, in separate one-day fixtures. Never infer
 # generated scores or aggregate a calibration trial. No scientific outputs.
 g=sliced(first);c=dict(case);c['rho_before']=case['rho_before'] if first<105 else case['rho_after'];t=time.perf_counter();engine=PreparedScores(g);setup=time.perf_counter()-t
 a=Trace();t=time.perf_counter();w.scores(g,base[first:first+1],c,[.1,-.1,.1],a);ref=time.perf_counter()-t
 b=Trace();t=time.perf_counter();engine.scores(base[first:first+1],c,[.1,-.1,.1],b);opt=time.perf_counter()-t
 assert a.h.digest()==b.h.digest()
 bench.append({'case_id':cid,'original_day':first,'reference_one_day_seconds':ref,'candidate_one_day_seconds':opt,'speedup':ref/opt,'projection_calls':b.n,'projections_per_second':b.n/opt,'day_scores_per_second':1/opt,'topology_setup_one_day_seconds':setup,'base_generation_210day_seconds':generation,'trace_digest_only':b.h.hexdigest()})
report['benchmark']=bench
report['runtime_environment']={'platform':platform.platform(),'python':sys.version,'numpy':np.__version__,'logical_cpu_count':os.cpu_count(),'affinity':sorted(os.sched_getaffinity(0)),'cpu_quota':Path('/sys/fs/cgroup/cpu.max').read_text().strip(),'memory_limit':Path('/sys/fs/cgroup/memory.max').read_text().strip(),'peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'BLAS_threads':os.environ.get('OPENBLAS_NUM_THREADS')}
report['available_durable_campaign_infrastructure_demonstrated']=False
report['complete_optimized_execution_path_benchmark']='NOT_ESTABLISHED: no complete campaign worker/dispatcher certified; only mechanical day-score path measured'
(P/'MECHANICAL_ENGINEERING_RAW_V1.json').write_bytes(w.canonical(report))
print('mechanical complete; NO statistical trials',flush=True)
