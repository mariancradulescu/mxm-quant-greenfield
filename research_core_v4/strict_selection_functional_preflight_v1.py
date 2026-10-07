"""Exact-head offline selection functional validation, no acquisition or scientific response."""
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from research_core_v4 import strict_selection_functional_v1 as f
from research_core_v4 import master1576_current_state_guard_v4 as g
ROOT=Path(__file__).resolve().parents[1]
def main():
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if os.environ.get('GITHUB_SHA'):f.require(head==os.environ['GITHUB_SHA'],'EXACT_HEAD_DRIFT')
    suite=unittest.defaultTestLoader.loadTestsFromName('tests.test_strict_selection_functional_v1')
    with patch('socket.socket',side_effect=AssertionError('Offline network forbidden')),patch('urllib.request.urlopen',side_effect=AssertionError('Offline network forbidden')):
        r=unittest.TextTestRunner(verbosity=2).run(suite);seen=[];f.build_root(ROOT,seen);state=g.validate_root(ROOT)
    record={'schema':'mxm.v4.strict-selection-functional.exact-head-offline-validation.v1','exact_validated_head':head,'run_id':os.environ.get('GITHUB_RUN_ID'),'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'tests_passed':r.testsRun-len(r.failures)-len(r.errors)-len(r.skipped),'tests_failed':len(r.failures)+len(r.errors),'tests_skipped':len(r.skipped),'selection_read_allowlist':sorted(f.ALLOWLIST),'actual_selection_reads':seen,'historical_outcome_files_read_by_selection':0,'network_blocked':True,'market_routes':0,'state':state}
    print('STRICT_SELECTION_FUNCTIONAL_VALIDATION='+json.dumps(record,sort_keys=True));return 0 if r.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
