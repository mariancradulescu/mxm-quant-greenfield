"""Only the unchanged frozen runner can open the scientific response."""
from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,'/science')
# Explicit file load avoids using current control modules as scientific code.
import importlib.util
spec=importlib.util.spec_from_file_location('numeric_environment_control','/controls/research_core_v4/numeric_environment_v1.py')
env=importlib.util.module_from_spec(spec);spec.loader.exec_module(env)
from research_core_v4 import development_execution_runner_v1 as runner
mode=sys.argv[1];assert mode in ['--prepare','--execute','--probe']
if mode=='--probe':
 print(env.probe());raise SystemExit(0)
report=env.verify()
bundle=runner.pre_response_guards(Path('/raw'))
prepared={'schema':'mxm.v4.prevalidated-frozen-runner.v1','environment':report,'provenance':bundle.provenance,'response_opened':False}
p=Path('/output/prepared.json')
if mode=='--prepare':
 p.write_text(json.dumps(prepared,sort_keys=True)+'\n')
else:
 assert json.loads(p.read_text())==prepared,'prepared bundle/environment changed'
 runner.execute_once(bundle,Path('/output/FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json'))
