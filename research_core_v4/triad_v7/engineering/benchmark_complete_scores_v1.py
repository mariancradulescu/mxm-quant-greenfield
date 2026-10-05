"""Full-calendar score-path microbenchmark; no statistical trial or inference.
Separate engineering PCG64 seeds; generated scores never reach infer/lead gates.
"""
import json,time,resource,os,platform
from pathlib import Path
import numpy as np
from execution_candidate_v1 import reference as w,PreparedScores
P=Path(__file__).resolve().parent;plan=json.loads((P/'FULL_SCORE_BENCHMARK_PLAN_V1.json').read_text())
for p,h in plan['bindings'].items():assert w.sha(w.R/p)==h
assert not (P.parent/'EXECUTION_ARM_V1.json').exists()
m=json.loads((P.parent/'TRIAL_MANIFEST_V1.json').read_text());g=w.load_geometry();projection=w.Projection(P.parent/'projection_bridge_v1.so')
class Count:
 def __init__(self):self.n=0
 def __call__(self,X,D):self.n+=1;return projection(X,D)
results=[]
for cid in plan['case_ids']:
 case=m['null_cases'][cid];s=plan['engineering_seed']+2*cid
 t=time.perf_counter();base,states=w.base_paths(g,case,np.random.Generator(np.random.PCG64(s)),np.random.Generator(np.random.PCG64(s+1)));gen=time.perf_counter()-t
 t=time.perf_counter();engine=PreparedScores(g);setup=time.perf_counter()-t
 a=Count();t=time.perf_counter();x=w.scores(g,base,case,plan['fixture_delta'],a);ref=time.perf_counter()-t
 b=Count();t=time.perf_counter();y=engine.scores(base,case,plan['fixture_delta'],b);opt=time.perf_counter()-t
 for k in x:assert np.array_equal(x[k],y[k],equal_nan=True)
 assert a.n==b.n
 # Generated daily/leaveout scores are discarded, never infer/reject/lead.
 results.append({'case_id':cid,'original_calendar_days':210,'reference_seconds':ref,'candidate_seconds':opt,'speedup':ref/opt,'projection_calls':b.n,'projection_calls_per_second':b.n/opt,'complete_scores_calls_per_second':1/opt,'topology_setup_seconds':setup,'base_generation_seconds':gen,'daily_leaveout_valid_bit_exact':True})
 print('full-calendar mechanical benchmark',cid,'PASS',flush=True)
out={'schema':'TRIAD_V7_FULL_SCORE_MECHANICAL_BENCHMARK_RAW_V1','plan_sha256':w.sha(P/'FULL_SCORE_BENCHMARK_PLAN_V1.json'),'results':results,'environment':{'platform':platform.platform(),'cpu_quota':Path('/sys/fs/cgroup/cpu.max').read_text().strip(),'memory_limit':Path('/sys/fs/cgroup/memory.max').read_text().strip(),'peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'BLAS_threads':os.environ.get('OPENBLAS_NUM_THREADS')},'limitations':['Complete scores path measured; not complete campaign worker/shard dispatcher','No empirical null/power outcomes or inference on generated scores','No certified full-trial raw-row parity or durable machine execution demonstrated'],'null_Monte_Carlo_trials':0,'power_Monte_Carlo_trials':0,'real_response_openings':0,'future_Y_reads':0,'broker_contacts':0,'new_acquisition':0,'candidate_frozen_count':0,'orders':0}
(P/'FULL_SCORE_BENCHMARK_RAW_V1.json').write_bytes(w.canonical(out))
