"""Complete predictor-only oracle audit; writes raw certificate observations only."""
from pathlib import Path
import json,gzip,hashlib,subprocess,tempfile,time,concurrent.futures,os
import numpy as np
from high_precision_projection_oracle_v1 import oracle
from one_sided_numerical_certificate_v1 import certify
from build_actual_predictor_geometry_v1 import build,input_hash
P=Path(__file__).resolve().parent;R=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def objhash(o):return hashlib.sha256(json.dumps(o,separators=(',',':'),sort_keys=True).encode()).hexdigest()
def compact_number(v):
 if v is None:return None
 return format(float(v),'.18e')
def evaluate(item):
 key,X,D,c=item;a=oracle(X,D,100);b=oracle(X,D,160);cert=certify(X,D,c,a,b)
 raw={'input_sha256':key,'oracle100_sha256':objhash(a),'oracle160_sha256':objhash(b),'production_sha256':objhash(c),'oracle100_status':a['status'],'oracle160_status':b['status'],'oracle100_internal_certificate':a.get('internal_certificate_pass',a['status']=='MATHEMATICAL_SCALE_REJECTED'),'oracle160_internal_certificate':b.get('internal_certificate_pass',b['status']=='MATHEMATICAL_SCALE_REJECTED'),'oracle100_rank':a.get('rank'),'oracle160_rank':b.get('rank'),'oracle100_retained':a.get('retained'),'oracle160_retained':b.get('retained'),'oracle100_singular':[compact_number(x) for x in a.get('singular_values',[])],'oracle160_singular':[compact_number(x) for x in b.get('singular_values',[])],'oracle100_RMS':compact_number(a.get('residual_RMS')),'oracle160_RMS':compact_number(b.get('residual_RMS')),'oracle100_eigen_error':compact_number(a.get('eigen_backward_error')),'oracle160_eigen_error':compact_number(b.get('eigen_backward_error')),'observed_certificate':cert}
 # All frozen checks above used full180-digit arithmetic; diagnostic storage rounding never changes decision.
 for name in ['cross_precision_singular_relative','cross_precision_RMS_relative','cross_precision_normalized_abs','max_singular_discrepancy','normalized_RD_error','RMS_abs_error']:
  if name in cert:cert[name]=compact_number(cert[name])
 return raw
if __name__=='__main__':
 assert json.loads((P/'FIXTURE_GATE_SUMMARY_V1.json').read_text())['all_pass']
 for path,s in json.loads((P/'INHERITED_IMMUTABLE_BINDINGS_V1.json').read_text())['bindings'].items():assert sha(R/path)==s,path
 start=time.perf_counter();inputs,masks,design=build();print(json.dumps({'phase':'INPUTS_BUILT','geometries':inputs['total_geometries'],'full_cohort':inputs['full_cohort_geometries']}),flush=True)
 with tempfile.TemporaryDirectory(prefix='triad_v6_actual_') as tmp:
  binary=Path(tmp)/'candidate';flags=json.loads((P/'ORACLE_TOOLCHAIN_BINDING_V1.json').read_text())['candidate_compile_flags'];subprocess.run(['g++',*flags,str(R/'research_core_v4/triad_v4/canonical_projection_jacobi_v1.cpp'),'-o',str(binary)],check=True,capture_output=True)
  result=subprocess.run([str(binary)],input=(P/'actual_predictor_kernel_input.tmp').read_text(),capture_output=True,text=True,check=True);cpp=[json.loads(line) for line in result.stdout.splitlines()]
 assert len(cpp)==inputs['total_geometries'];unique={};mapping=[]
 for g,c in zip(inputs['geometries'],cpp):
  f=inputs['full_clock_geometries'][g['full_index']];keep=[i for i,t in enumerate(f['targets']) if t!=g['excluded_target']];X=[f['X'][i] for i in keep];D=[f['D'][i] for i in keep];key=input_hash(X,D);assert key==g['input_sha256'];mapping.append(key)
  if key in unique:assert unique[key][3]==c
  else:unique[key]=(key,X,D,c)
 print(json.dumps({'phase':'ORACLE_START','unique_binary64_geometries':len(unique),'requested_geometries':len(mapping),'worker_processes':4}),flush=True)
 measurements=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
  for i,record in enumerate(pool.map(evaluate,unique.values(),chunksize=32)):
   measurements.append(record)
   if (i+1)%1000==0:print(json.dumps({'phase':'ORACLE_PROGRESS','completed_unique':i+1,'total_unique':len(unique),'elapsed_seconds':time.perf_counter()-start,'support_interpretation':'NOT_PERFORMED'}),flush=True)
 raw={'schema':'TRIAD_V6_ACTUAL_PREDICTOR_ORACLE_RAW_V1','input_geometry_gzip_sha256':sha(P/'ACTUAL_CAUSAL_INPUT_GEOMETRY_V1.json.gz'),'oracle_source_sha256':sha(P/'high_precision_projection_oracle_v1.py'),'support_certificate_source_sha256':sha(P/'one_sided_numerical_certificate_v1.py'),'builder_sha256':sha(P/'build_actual_predictor_geometry_v1.py'),'audit_source_sha256':sha(Path(__file__)),'projection_kernel_sha256':sha(R/'research_core_v4/triad_v4/canonical_projection_jacobi_v1.cpp'),'requested_geometries':len(mapping),'unique_geometries':len(unique),'requested_to_exact_input_hash':mapping,'measurements':measurements,'elapsed_seconds':time.perf_counter()-start,'interpretation':'PENDING_DURABLE_RAW_PERSISTENCE','future_Y_reads':0,'future_real_signed_response_computations':0,'real_response_openings':0,'full_null_trials':0,'full_power_trials':0}
 payload=(json.dumps(raw,separators=(',',':'),sort_keys=True)+'\n').encode();(P/'ACTUAL_PREDICTOR_ORACLE_RAW_V1.json.gz').write_bytes(gzip.compress(payload,mtime=0));print(json.dumps({'raw_written':True,'raw_gzip_bytes':(P/'ACTUAL_PREDICTOR_ORACLE_RAW_V1.json.gz').stat().st_size,'elapsed_seconds':raw['elapsed_seconds'],'support_interpretation':'NOT_PERFORMED'}),flush=True)
