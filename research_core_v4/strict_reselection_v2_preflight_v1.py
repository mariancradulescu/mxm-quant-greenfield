"""Exact-head offline firewall and canonical-state audit; no scientific execution."""
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from research_core_v4 import strict_reselection_v2 as b
from research_core_v4 import master1576_current_state_guard_v3 as g
ROOT=Path(__file__).resolve().parents[1]
def main():
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if os.environ.get('GITHUB_SHA'):b.require(head==os.environ['GITHUB_SHA'],'EXACT_HEAD_DRIFT')
    suite=unittest.defaultTestLoader.loadTestsFromName('tests.test_strict_reselection_v2')
    with patch('socket.socket',side_effect=AssertionError('Offline network forbidden')),patch('urllib.request.urlopen',side_effect=AssertionError('Offline network forbidden')):
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        projection_reads=[];selection_reads=[];b.project_root(ROOT,projection_reads);b.build_root(ROOT,selection_reads);state=g.validate_root(ROOT)
    record={'schema':'mxm.v4.strict-reselection-v2.exact-head-offline-validation.v1','exact_validated_head':head,'run_id':os.environ.get('GITHUB_RUN_ID'),'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'tests_passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),'tests_failed':len(result.failures)+len(result.errors),'tests_skipped':len(result.skipped),'projection_reads':sorted(projection_reads),'selection_reads':selection_reads,'network_blocked':True,'market_routes':0,'canonical_state':state}
    print('STRICT_RESELECTION_V2_VALIDATION='+json.dumps(record,sort_keys=True));return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
