"""Frozen deterministic predictor-only suite; writes RAW only, no interpretation."""
from pathlib import Path
import hashlib,importlib.util,json,subprocess,tempfile,time
import numpy as np
P=Path(__file__).resolve().parent;R=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((P/'PROJECTION_EQUIVALENCE_PLAN_V1.json').read_text())
spec=json.loads((P/'NUMERICAL_KERNEL_SPEC_V1.json').read_text())
assert sha(P/'NUMERICAL_KERNEL_SPEC_V1.json')==plan['numerical_spec_sha256']
for p,s in json.loads((P/'INHERITED_IMMUTABLE_BINDINGS_V1.json').read_text())['bindings'].items():assert sha(R/p)==s,p
module=importlib.util.spec_from_file_location('canonical',R/'research_core_v4/triad_v2/orthogonal_score_v2.py');canonical=importlib.util.module_from_spec(module);module.loader.exec_module(canonical)
fixtures=[];inputs=[]
def add(id,X,D,historical=None):
 X=np.asarray(X,dtype=float);D=np.asarray(D,dtype=float);Z=X/np.sqrt(np.mean(X*X,axis=0))
 row={'id':id,'n':len(X),'X':X.tolist(),'D':D.tolist(),'scaled_singular_values':np.linalg.svd(Z,compute_uv=False).tolist()}
 try:
  f=canonical.current_projection(X,D);row['canonical']={'accepted':True,'normalized':f['normalized'].tolist(),'rms':f['rms'],'orthogonality_error':f['orthogonality_error'],'rank':f['rank']}
 except AssertionError:row['canonical']={'accepted':False}
 if historical is not None:row['historical_frozen_expected']=historical
 fixtures.append(row);inputs.append(str(len(X)));inputs.extend(' '.join(format(float(v),'.17g') for v in [*X[i],D[i]]) for i in range(len(X)))
oldplan=json.loads((R/'research_core_v4/triad_v3/INHERITED_SCIENCE_STATIC_GATE_PLAN_V1.json').read_text());old=json.loads((R/'research_core_v4/triad_v3/INHERITED_PROJECTION_STATIC_RAW_V1.json').read_text())
k=0
for n in oldplan['fixtures']['target_counts']:
 for eps in oldplan['fixtures']['near_collinearity_epsilon']:
  i=np.arange(1,n+1,dtype=float);a=np.sin(i*np.sqrt(2));X=np.column_stack([np.ones(n),a,a+eps*np.cos(i*np.sqrt(3))]);D=np.sin(i*np.sqrt(5));expected=old['fixtures'][k];assert expected['n']==n and expected['epsilon']==eps
  add(f'V3_{k:02d}_n{n}_eps{eps}',X,D,{key:value for key,value in expected.items() if key.startswith('canonical_')});k+=1
assert k==24

def variants(prefix,X,D,names):
 for variant in names:
  A=X.copy();d=D.copy()
  if variant=='reverse_rows':A=A[::-1];d=d[::-1]
  elif variant=='control_signs_1_minus1_minus1':A=A*np.array([1.,-1.,-1.])
  elif variant=='raw_scales_1e-6_1e6_3':A=A*np.array([1e-6,1e6,3.])
  elif variant=='D_sign_flip':d=-d
  elif variant=='D_plus_X_times_0.3_minus0.7_0.2':d=d+X@np.array([.3,-.7,.2])
  elif variant=='leave_last_target_out_if_n_gt5':
   if len(X)<=5:continue
   A=A[:-1];d=d[:-1]
  elif variant!='base':raise ValueError(variant)
  add(prefix+'_'+variant,A,d)
for n in plan['target_counts']:
 i=np.arange(1,n+1,dtype=float);a=np.sin(i*np.sqrt(2));D=np.sin(i*np.sqrt(5))
 for eps in plan['epsilon_grid']:
  X=np.column_stack([np.ones(n),a,a+eps*np.cos(i*np.sqrt(3))]);variants(f'V4_n{n}_eps{eps}',X,D,plan['variants'])
 Q,_=np.linalg.qr(np.column_stack([np.ones(n),a,np.cos(i*np.sqrt(3))]));V,_=np.linalg.qr(np.array([[1.,2.,3.],[2.,-1.,1.],[1.,1.,-1.]]))
 for small in plan['prescribed_spectra']['smallest_raw_singular_values']:
  X=(Q*np.array([np.sqrt(n),np.sqrt(n)/2,small]))@V.T;variants(f'V4_spectrum_n{n}_s{small}',X,D,plan['prescribed_spectra']['variants'])
with tempfile.TemporaryDirectory(prefix='triad_v4_fixture_') as tmp:
 binary=Path(tmp)/'kernel';flags=json.loads((P/'TOOLCHAIN_BINDING_V1.json').read_text())['flags'];command=['g++',*flags,str(P/'canonical_projection_jacobi_v1.cpp'),'-o',str(binary)]
 compile_result=subprocess.run(command,capture_output=True,text=True,check=True);binary_sha=sha(binary)
 t=time.perf_counter();result=subprocess.run([str(binary)],input='\n'.join(inputs)+'\n',text=True,capture_output=True,check=True);elapsed=time.perf_counter()-t
 candidates=[json.loads(line) for line in result.stdout.splitlines()]
assert len(candidates)==len(fixtures)
for row,candidate in zip(fixtures,candidates):row['cpp']=candidate
raw={'schema':'TRIAD_V4_PROJECTION_FIXTURE_RAW_V1','projection_kernel_sha256':sha(P/'canonical_projection_jacobi_v1.cpp'),'spec_sha256':sha(P/'NUMERICAL_KERNEL_SPEC_V1.json'),'plan_sha256':sha(P/'PROJECTION_EQUIVALENCE_PLAN_V1.json'),'runner_sha256':sha(Path(__file__)),'toolchain_sha256':sha(P/'TOOLCHAIN_BINDING_V1.json'),'binary_sha256':binary_sha,'compile_stdout':compile_result.stdout,'compile_stderr':compile_result.stderr,'fixtures':fixtures,'historical_fixture_count':24,'adversarial_fixture_count':len(fixtures)-24,'runtime_seconds':elapsed,'full_null_trials':0,'full_power_trials':0,'real_Y_reads':0,'actual_predictor_audit_count':0,'interpretation':'PENDING_RAW_PERSISTENCE'}
(P/'PROJECTION_FIXTURE_RAW_V1.json').write_text(json.dumps(raw,indent=2,sort_keys=True,allow_nan=False)+'\n');print(json.dumps({'raw_written':True,'fixture_count':len(fixtures),'kernel_sha256':raw['projection_kernel_sha256'],'interpretation':'PENDING_RAW_PERSISTENCE'}))
