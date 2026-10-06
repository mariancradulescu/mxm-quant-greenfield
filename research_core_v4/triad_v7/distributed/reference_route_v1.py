"""Compute/transport wrapper only; frozen V7 scientific functions authoritative.
Engineering fixtures never use certification seeds. No market input interface.
"""
from pathlib import Path
import sys,os,json,hashlib,socket,multiprocessing as mp,time,resource,math
import numpy as np,scipy
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P.parent))
import stochastic_worker_v1 as w
import control_plane_v1 as c
import support_semantics_wrapper_v1 as s
FIELDS=('false_significance','false_lead','any_nonnull_lead','all_nonnull_leads','supported')
def digest(b):return hashlib.sha256(b).hexdigest()
def fence():c.fence()
def runtime():
 assert sys.version.split()[0]=='3.12.14' and np.__version__=='2.3.5' and scipy.__version__=='1.17.0'
 for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:assert os.environ.get(key)=='1'
 affinity=len(os.sched_getaffinity(0));n=min(4,os.cpu_count() or 1,affinity)
 return {'python':sys.version.split()[0],'numpy':np.__version__,'scipy':scipy.__version__,'cpu_count':os.cpu_count(),'affinity_cpus':affinity,'processes':n,'RAM_bytes':os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES'),'peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
def manifest():
 plan=json.loads((P/'PREARM_PLAN_V1.json').read_text())
 # Preserve the exact preexisting engineering RNG namespace; the historical
 # plan remains byte-identical even though its original execution files are
 # prospectively superseded by this reconciliation layer.
 assert w.sha(P/'PREARM_PLAN_V1.json')=='23511ae4d94d14299e6a209e5974b2b9aa9024504fd130e1337516894652aa7f'
 authority=json.loads((P/'SUPPORT_SEMANTICS_RECONCILIATION_AUTHORITY_V1.json').read_text())
 assert authority['classification']=='PREOUTCOME_IMPLEMENTATION_CONTRACT_INCONSISTENCY_CORRECTION_NOT_SCIENTIFIC_RETUNING'
 assert w.sha(P/'support_semantics_wrapper_v1.py')==authority['frozen_bindings']['support_semantics_wrapper_sha256']
 forensic=json.loads((P/'EXACT_FAILED_FIXTURE_FORENSIC_V1.json').read_text())
 assert forensic['failure_preserved'] and forensic['reason']=='CANDIDATE_FAIL_CLOSED'
 assert forensic['trial_context']=={'case_id':9,'configuration_id':'G10_ONLY','configuration_name':None,'delta':[0.5,0,0],'engineering_trial_index':0,'phase':'null'}
 m,a=c.preflight();assert w.sha(w.P/'TRIAL_MANIFEST_V1.json')=='7904af615cef0d5002370d45160733bd84e72a9d2599ee52de126b0560854b3a'
 assert w.sha(w.P/'stochastic_worker_v1.py')=='af0cd192adc19478686198082f190b69585dab4d29df9e6835d1f7cf6a3c6de6'
 assert w.sha(w.P/'control_plane_v1.py')=='d60ca6214553621f5122e44ec8f648592240ef91763b8b6c9a1eebbd6f975f03'
 return m

def ranges(start,stop,count):return [(start+(stop-start)*i//count,start+(stop-start)*(i+1)//count) for i in range(count)]
def layout():return ranges(0,8192,20)
def empty(cells):return {x['id']:{**{f:0 for f in FIELDS},'per_leaf_lead':[0]*12} for x in cells}
def add(out,rows):
 for row in rows:
  ct=out[row['cell_id']]
  for f in FIELDS:ct[f]+=int(row['support'] if f=='supported' else row[f])
  ct['per_leaf_lead']=[a+int(b) for a,b in zip(ct['per_leaf_lead'],row['per_leaf_lead'])]
def sum_counts(parts,cells):
 out=empty(cells)
 for p in parts:
  assert set(p)==set(out)
  for cid in out:
   assert set(p[cid])==set(out[cid]) and len(p[cid]['per_leaf_lead'])==12
   for f in FIELDS:assert type(p[cid][f]) is int;out[cid][f]+=p[cid][f]
   for i,v in enumerate(p[cid]['per_leaf_lead']):assert type(v) is int;out[cid]['per_leaf_lead'][i]+=v
 return out
class Trace:
 def __init__(self):self.h={};self.n={}
 def array(self,key,a):
  a=np.ascontiguousarray(a);h=self.h.setdefault(key,hashlib.sha256());h.update(str((a.shape,a.dtype.str)).encode());h.update(a.tobytes());self.n[key]=self.n.get(key,0)+1
 def obj(self,key,o):
  h=self.h.setdefault(key,hashlib.sha256());h.update(w.canonical(o));self.n[key]=self.n.get(key,0)+1
 def result(self):return {k:{'sha256':h.hexdigest(),'records':self.n[k]} for k,h in self.h.items()}
class RecordedRNG:
 def __init__(self,rng,trace,key):self.rng=rng;self.trace=trace;self.key=key
 def standard_normal(self,*args,**kw):
  a=self.rng.standard_normal(*args,**kw)
  if self.trace:self.trace.array(self.key+'_normal',a)
  return a
 def chisquare(self,*args,**kw):
  a=self.rng.chisquare(*args,**kw)
  if self.trace:self.trace.array(self.key+'_chisquare',a)
  return a

def engineering_one(task):
 case,phase,index,traced=task;runtime();fence();m=manifest();assert not (w.P/'EXECUTION_ARM_V1.json').exists()
 if phase=='power':m=dict(m);m['power_cells']=[m['power_cells'][x] for x in [2,11,56]]
 t=Trace() if traced else None;namespace=w.sha(P/'PREARM_PLAN_V1.json')
 def gen(man,mode,cid,idx,stream):
  assert mode==phase and cid==case and idx==index
  material=f'MXM_TRIAD_V7_DISTRIBUTED_ENGINEERING|{namespace}|{phase}|{case}|{index}|{stream}'
  seed=int.from_bytes(hashlib.sha256(material.encode()).digest()[:16],'little')
  return RecordedRNG(np.random.Generator(np.random.PCG64(seed)),t,stream)
 w.generator=gen
 def no_arm(*args):assert not (w.P/'EXECUTION_ARM_V1.json').exists()
 w.require_execution_arm=no_arm
 oldbase=w.base_paths;oldfits=w.clock_fits;oldscores=w.scores;oldinfer=w.infer
 if traced:
  def base(*args,**kw):
   b,s=oldbase(*args,**kw);t.array('base',b);t.array('states',s);return b,s
  def fits(*args,**kw):
   f=oldfits(*args,**kw)
   if f is not None:
    t.array('X',f['X']);t.array('D',f['D']);t.array('full_projection',f['full']['normalized']);t.obj('full_certificate',{'candidate':f['full']['candidate'],'support':f['full']['support']})
    for target,(keep,fit) in f['loo'].items():
     t.array('leaveout_keep',keep);t.array('leaveout_projection',fit['normalized']);t.obj('leaveout_certificate',{'target':target,'candidate':fit['candidate'],'support':fit['support']})
   return f
  source=(w.P/'stochastic_worker_v1.py').read_text().splitlines();injected_line=next(i+1 for i,line in enumerate(source) if 'sums=np.zeros(12)' in line)
  def hook(frame,event,arg):
   if frame.f_code is oldscores.__code__:
    if event=='line' and frame.f_lineno==injected_line:t.array('injected_day_path',frame.f_locals['path'])
    return hook
   return None
  def scores(*args,**kw):
   sys.settrace(hook)
   try:o=oldscores(*args,**kw)
   finally:sys.settrace(None)
   for key,a in o.items():t.array(key,a)
   return o
  def infer(*args,**kw):
   def profile(frame,event,arg):
    if frame.f_code is oldinfer.__code__ and event=='return':
     for key in ['blocks','obs','maximum','p','reject','lead']:t.array(key,frame.f_locals[key])
   sys.setprofile(profile)
   try:o=oldinfer(*args,**kw)
   finally:sys.setprofile(None)
   return o
  w.base_paths=base;w.clock_fits=fits;w.scores=scores;w.infer=infer
 started=time.perf_counter()
 try:
  rows,sem=s.trial(m,w.load_geometry(),w.Projection(w.P/'projection_bridge_v1.so'),phase,case,index,verify_supported_path=(traced and index==0))
  counts=empty(m['partial_nulls'] if phase=='null' else m['power_cells']);add(counts,rows)
  return {'index':index,'rows_sha256':digest(w.canonical(rows)),'trace':t.result() if t else None,'manufactured_engineering_counts':counts,'support_semantics':sem,'seconds':time.perf_counter()-started,'peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
 finally:
  w.base_paths=oldbase;w.clock_fits=oldfits;w.scores=oldscores;w.infer=oldinfer

def pool_map(fn,tasks,processes):
 # spawn prevents inherited generator/trace overrides. Completion order ignored.
 pool=mp.get_context('spawn').Pool(processes)
 try:out=pool.map(fn,tasks);pool.close();pool.join();return out
 except BaseException:pool.terminate();pool.join();raise

def engineering_case(case):
 env=runtime();m=manifest();phases=['null']+(['power'] if case in [0,13,15,16] else []);evidence=[]
 for phase in phases:
  tasks=[(case,phase,i,True) for i in range(env['processes'])]
  # Serial reference route and process route both call unchanged scientific
  # functions. Only engineering RNG/ARM adapters are installed, never persisted
  # in scientific source or available in certification processes.
  serial=[engineering_one(t) for t in tasks];parallel=pool_map(engineering_one,tasks,env['processes'])
  for a,b in zip(serial,parallel):
   assert a['index']==b['index'] and a['trace']==b['trace'] and a['rows_sha256']==b['rows_sha256'] and a['manufactured_engineering_counts']==b['manufactured_engineering_counts'] and a['support_semantics']==b['support_semantics']
  cells=m['partial_nulls'] if phase=='null' else [m['power_cells'][x] for x in [2,11,56]]
  assert sum_counts([x['manufactured_engineering_counts'] for x in serial],cells)==sum_counts([x['manufactured_engineering_counts'] for x in parallel[::-1]],cells)
  parity=serial[0]['support_semantics'].get('supported_path_parity');assert parity and parity['all_accounted']
  evidence.append({'phase_fixture':phase,'complete_210day_fixtures':len(tasks),'trace':serial[0]['trace'],'serial_distributed_bit_exact':True,'all_raw_row_digests_match':True,'integer_merge_order_independent':True,'support_semantics':[x['support_semantics'] for x in serial],'supported_path_bit_parity':parity})
 # Untraced same full-trial route for actual process-throughput measurement.
 tasks=[(case,'null',100+i,False) for i in range(env['processes'])]
 t0=time.perf_counter();serial=[engineering_one(t) for t in tasks];serial_wall=time.perf_counter()-t0
 t0=time.perf_counter();parallel=pool_map(engineering_one,tasks,env['processes']);parallel_wall=time.perf_counter()-t0
 assert [x['rows_sha256'] for x in serial]==[x['rows_sha256'] for x in parallel]
 out={'schema':'TRIAD_V7_DISTRIBUTED_PREARM_CASE_RAW_V1','case_id':case,'environment':env,'evidence':evidence,'benchmark':{'engineering_complete_trial_count':len(tasks),'serial_wall_seconds':serial_wall,'four_process_wall_seconds':parallel_wall,'aggregate_trials_per_second':len(tasks)/parallel_wall,'process_scaling_efficiency':serial_wall/(env['processes']*parallel_wall),'per_process_trial_seconds':[x['seconds'] for x in parallel],'peak_worker_RSS_KiB':max(x['peak_RSS_KiB'] for x in parallel)},'source_head':os.environ['GITHUB_SHA'],'workflow_run_id':os.environ['GITHUB_RUN_ID'],'null_Monte_Carlo_trials':0,'power_Monte_Carlo_trials':0,'real_response_openings':0,'future_Y_reads':0,'broker_contacts':0,'new_acquisition':0,'candidate_frozen_count':0,'orders':0,'certification_seed_usage':False,'scientific_inference_from_engineering_fixtures':False,'ARM_present':False}
 return out

def check_shards(parts):
 expected=layout();by={}
 for p in parts:
  i=p['shard_id'];assert type(i) is int and 0<=i<20 and i not in by;by[i]=p
 assert set(by)==set(range(20)),'MISSING_SHARD'
 for i,(a,b) in enumerate(expected):assert (by[i]['start'],by[i]['stop'],by[i]['trials'])==(a,b,b-a)
 return [by[i] for i in range(20)]
def mechanical_partition():
 m=manifest();parts=[]
 for i,(a,b) in enumerate(layout()):
  processes=ranges(a,b,4);indices=[v for start,stop in processes for v in range(start,stop)];assert indices==list(range(a,b))
  cells=empty(m['partial_nulls'])
  for ct in cells.values():ct['supported']=b-a
  parts.append({'shard_id':i,'start':a,'stop':b,'trials':b-a,'cells':cells})
 assert [v for p in check_shards(parts) for v in range(p['start'],p['stop'])]==list(range(8192))
 assert sum_counts([p['cells'] for p in parts],m['partial_nulls'])==sum_counts([p['cells'] for p in parts[::-1]],m['partial_nulls'])
 for bad in [parts[:-1],parts+parts[:1]]:
  try:check_shards(bad)
  except AssertionError:pass
  else:raise AssertionError('INVALID_SHARD_SET_ACCEPTED')
 return {'twenty_shards':layout(),'four_process_ranges_all_exact':True,'all_8192_indices_once':True,'merge_order_independent':True,'duplicate_missing_rejected':True,'partial_interpretation_entrypoint':False,'shard_process_runner_run_ID_never_enters_seed':True}
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('mode',choices=['engineering']);a.add_argument('--case',type=int,required=True);a.add_argument('--output',required=True);a.add_argument('--fixture-id',type=int,required=True);z=a.parse_args()
 assert int(os.environ.get('GITHUB_RUN_ATTEMPT','1'))==1
 out=engineering_case(z.case);out['fixture_id']=z.fixture_id;out['partition']=mechanical_partition();Path(z.output).write_bytes(w.canonical(out))
 print('PREARM_COMPLETE_REFERENCE_ROUTE_BIT_EXACT_NO_CERTIFICATION_TRIALS',flush=True)
