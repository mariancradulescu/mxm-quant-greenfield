"""Immutable OS/interpreter + hash-locked NumPy wheel, offline numerical worker."""
from pathlib import Path
import argparse,hashlib,json,os,platform,subprocess,sys,urllib.request
ROOT=Path(__file__).resolve().parents[1]
REL='research_core_v4/runtime/NUMERIC_ENVIRONMENT_V1.json'
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load():return json.loads((ROOT/REL).read_text())
def probe():
 import math,numpy as np
 from research_core_v4 import response_evaluator_v3 as ev
 from research_core_v4.runtime_profile_audit_v1 import synthetic_fixture
 events,norm,raw=synthetic_fixture(3000)
 units=ev.construct_paired_units(events,norm)
 diagnostics=ev.build_nonselection_diagnostics(events,norm,raw)
 rng=np.random.default_rng(20261002)
 a=rng.standard_normal((1023,24)); signs=rng.choice([-1,1],(1023,24))
 # Includes RNG, permutation, maxT-like reductions, Python/libm, and frozen pairing.
 values={'rng_state':rng.bit_generator.state,'sums':np.sum(a,axis=1).tolist(),
  'maxima':np.max(np.abs(signs*a),axis=1).tolist(),'std':np.std(a,axis=1,ddof=1).tolist(),
  'logs':[math.log(1+i/10000) for i in range(1,1000)],'paired':units,'diagnostics':diagnostics}
 raw=json.dumps(values,sort_keys=True,separators=(',',':'),default=str).encode()
 return hashlib.sha256(raw).hexdigest()
def verify():
 import numpy as np
 m=load()
 assert platform.python_version()==m['python_version'] and np.__version__==m['numpy_version']
 assert platform.machine()==m['architecture']
 for k,v in m['environment'].items():assert os.environ.get(k)==v,(k,'environment drift')
 digest=probe();assert m['proof_status']=='BOUND_SYNTHETIC_REFERENCE_PROBE' and digest==m['probe_sha256'],'numerical probe drift/unbound'
 return {'status':'PASS','manifest_sha256':h(ROOT/REL),'image':m['container_image'],'python':platform.python_version(),'numpy':np.__version__,'probe_sha256':digest}
def fetch_wheel(directory):
 m=load();w=m['numpy_wheel'];directory.mkdir(parents=True,exist_ok=True);p=directory/w['filename']
 if not p.exists():
  with urllib.request.urlopen(w['url'],timeout=90) as f,p.open('wb') as out:
   while b:=f.read(1024*1024):out.write(b)
 assert h(p)==w['sha256'],'wheel hash mismatch'
 return p
def container_command(root,science,raw,temporary,wheel_dir,mode):
 m=load();w=wheel_dir/m['numpy_wheel']['filename'];assert h(w)==m['numpy_wheel']['sha256']
 cmd=['docker','run','--rm','--platform','linux/amd64','--user',str(os.getuid())+':'+str(os.getgid()),'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--tmpfs','/tmp:rw,nosuid,nodev,size=512m']
 for k,v in m['environment'].items():cmd+=['-e',k+'='+v]
 for src,dst,access in [(root,'/controls','ro'),(science,'/science','ro'),(raw,'/raw','ro'),(temporary,'/output','rw'),(wheel_dir,'/wheel','ro')]:cmd+=['-v',str(src.resolve())+':'+dst+':'+access]
 cmd += [m['container_image'],'sh','-ec','python -m pip install --disable-pip-version-check --no-index --no-deps --require-hashes --target /tmp/numeric --find-links /wheel -r /controls/research_core_v4/runtime/numeric-requirements-v1.txt >/dev/null; PYTHONPATH=/tmp/numeric:/science python /controls/research_core_v4/numeric_worker_v1.py '+mode]
 return cmd
def main():
 a=argparse.ArgumentParser();a.add_argument('--fetch-wheel',type=Path);a.add_argument('--probe',action='store_true');x=a.parse_args()
 if x.fetch_wheel:print(fetch_wheel(x.fetch_wheel))
 elif x.probe:print(probe())
 else:print(json.dumps(verify(),sort_keys=True))
if __name__=='__main__':main()
