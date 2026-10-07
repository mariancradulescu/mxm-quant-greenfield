"""Exact-head offline validation only; no broker, secret or market-data execution."""
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from research_core_v4 import master1576_current_state_guard_v2 as g
ROOT=Path(__file__).resolve().parents[1]
def main():
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if os.environ.get('GITHUB_SHA'):g.require(head==os.environ['GITHUB_SHA'],'EXACT_HEAD_DRIFT')
    loader=unittest.TestLoader();suite=loader.loadTestsFromName('tests.test_project_wide_reselection_v1')
    # Historical accounting suite retains its bytes; the superseded current-state assertion is replaced by V2.
    from tests.test_master1576_post_screen_v1 import PostScreenTests
    for name in loader.getTestCaseNames(PostScreenTests):
        if name!='test_20_canonical_state_authority_next_and_budget':suite.addTest(PostScreenTests(name))
    with patch('socket.socket',side_effect=AssertionError('Offline network forbidden')),patch('urllib.request.urlopen',side_effect=AssertionError('Offline network forbidden')):
        result=unittest.TextTestRunner(verbosity=2).run(suite)
    record={'schema':'mxm.v4.project-wide-reselection.exact-head-offline-validation.v1','exact_validated_head':head,'run_id':os.environ.get('GITHUB_RUN_ID'),'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'tests_passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),'tests_failed':len(result.failures)+len(result.errors),'tests_skipped':len(result.skipped),'offline_network_blocked':True,'market_execution_routes':0,'result':g.validate_root(ROOT)}
    print('PROJECT_WIDE_RESELECTION_VALIDATION='+json.dumps(record,sort_keys=True))
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
