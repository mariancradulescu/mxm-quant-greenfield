"""Only the unchanged frozen runner can open the scientific response."""
from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,'/science')
# Explicit file load avoids using current control modules as scientific code.
import importlib.util
spec=importlib.util.spec_from_file_location('numeric_environment_control','/controls/research_core_v4/numeric_environment_v1.py')
env=importlib.util.module_from_spec(spec);spec.loader.exec_module(env)
from research_core_v4 import development_execution_runner_v1 as runner
from research_core_v4 import frozen_v2_semantics as semantics
# No control directory is added to the scientific package search path.
for module in (runner,runner.ev,semantics):
 assert Path(module.__file__).resolve().is_relative_to(Path('/science')),'scientific import outside frozen mount'
expected={'development_execution_runner_v1.py':'cebcf2ad4f88e40d575cb46ffc14e0862107b47a84260a15b3310f075af4f79d',
 'response_evaluator_v3.py':'bb846fb3bbbe567c53587a6c22b344ffe39af7129db5e9a4a39c77026f3ade2a',
 'frozen_v2_semantics.py':'0a7bda1afe5cbe79373ee833e9d09febc08721d1826d94435f74d900f74f26ed'}
for name,want in expected.items():
 assert hashlib.sha256((Path('/science/research_core_v4')/name).read_bytes()).hexdigest()==want,'frozen module byte drift'

mode=sys.argv[1];assert mode in ['--prepare','--execute','--probe']
if mode=='--probe':
 print(env.probe());raise SystemExit(0)
report=env.verify()
# Guard the real-input preparation dynamically without editing frozen sources.
# Synthetic numeric probe has already completed before this guard is enabled.
forbidden={runner.execute_once.__code__,runner.ev._evaluate_prevalidated_development_core.__code__,
 runner.ev._responses_for_events.__code__,runner.ev.response_for_event.__code__}
response_calls=0
def guard(frame,event,arg):
 global response_calls
 if event=='call' and frame.f_code in forbidden:
  response_calls+=1
  raise PermissionError('real response entry attempted during pre-response preparation')
sys.setprofile(guard)
try:
 bundle=runner.pre_response_guards(Path('/raw'))
finally:
 sys.setprofile(None)
assert response_calls==0 and runner.RESPONSE_OPENING_STARTED is False

prepared={'schema':'mxm.v4.prevalidated-frozen-runner.v1','environment':report,'provenance':bundle.provenance,'response_opened':False,'pre_response_guard':{'forbidden_response_calls':response_calls,'scientific_imports_from_frozen_mount':True}}
p=Path('/output/prepared.json')
if mode=='--prepare':
 p.write_text(json.dumps(prepared,sort_keys=True)+'\n')
else:
 assert json.loads(p.read_text())==prepared,'prepared bundle/environment changed'
 runner.execute_once(bundle,Path('/output/FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json'))
