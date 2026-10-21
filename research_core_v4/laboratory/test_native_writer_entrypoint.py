"""Run the real -m entry point with a keyless canonical-module sentinel."""
import subprocess
import sys
import unittest
from pathlib import Path

class NativeWriterEntrypoint(unittest.TestCase):
    def test_cli_uses_same_module_scope_as_imported_publishers_and_guards(self):
        script='''import runpy,sys
from research_core_v4.laboratory import custody
sentinel=object()
custody._NATIVE_WRITER_SCOPE=sentinel
def canonical(operation):
    assert operation=='source-controls'
    assert custody._NATIVE_WRITER_SCOPE is sentinel
    print('CANONICAL_WRITER_SCOPE_USED')
custody.run_native_writer=canonical
sys.argv=['custody','source-controls']
runpy.run_module('research_core_v4.laboratory.custody',run_name='__main__')
'''
        result=subprocess.run([sys.executable,'-c',script],
            cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('CANONICAL_WRITER_SCOPE_USED',result.stdout)

if __name__=='__main__':unittest.main()
