"""Regression for the actual split-mount import failure, without real input bytes."""
import json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from research_core_v4 import numeric_environment_v1 as n
ROOT=Path(__file__).resolve().parents[1]
class NumericNamespaceTests(unittest.TestCase):
 def test_control_fixture_absent_from_science_still_uses_science_evaluator(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);science=base/'science';pkg=science/'research_core_v4';pkg.mkdir(parents=True)
   for name in ['__init__.py','response_evaluator_v3.py','frozen_v2_semantics.py']:
    src=ROOT/'research_core_v4'/name
    if src.exists():shutil.copy2(src,pkg/name)
   controls=base/'controls';cp=controls/'research_core_v4';cp.mkdir(parents=True)
   for name in ['numeric_environment_v1.py','runtime_profile_audit_v1.py']:shutil.copy2(ROOT/'research_core_v4'/name,cp/name)
   # A control evaluator must never shadow the frozen scientific package.
   (cp/'response_evaluator_v3.py').write_text("raise AssertionError('CONTROL EVALUATOR SHADOWED SCIENCE')\n")
   code="""import importlib.util,json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
s=importlib.util.spec_from_file_location('numeric_environment_control',sys.argv[2])
n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
a=n.probe();b=n.probe();assert a==b
from research_core_v4 import response_evaluator_v3 as ev
assert Path(ev.__file__).resolve().is_relative_to(Path(sys.argv[1]))
assert not (Path(sys.argv[1])/'research_core_v4/runtime_profile_audit_v1.py').exists()
print(json.dumps({'reproducible':True,'isolated_frozen_evaluator':True}))
"""
   result=subprocess.check_output([sys.executable,'-c',code,str(science),str(cp/'numeric_environment_v1.py')],cwd=base,env={**os.environ,'PYTHONPATH':''},text=True)
   self.assertEqual(json.loads(result),{'reproducible':True,'isolated_frozen_evaluator':True})
 def test_same_science_control_mount_is_rejected_before_launch(self):
  with self.assertRaisesRegex(AssertionError,'distinct'):
   n.container_command(ROOT,ROOT,ROOT,ROOT,ROOT,'--prepare')
 def test_invalid_worker_mode_is_rejected_before_launch(self):
  with self.assertRaisesRegex(AssertionError,'invalid'):
   n.container_command(ROOT,ROOT,ROOT,ROOT,ROOT,'--prepare; --execute')
