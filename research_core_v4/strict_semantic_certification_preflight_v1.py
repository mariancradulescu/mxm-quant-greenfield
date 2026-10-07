"""Exact-head offline certification audit. Tests do not execute the next plan."""
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from research_core_v4 import strict_semantic_certification_v1 as s
from research_core_v4 import master1576_current_state_guard_v5 as g
ROOT=Path(__file__).resolve().parents[1]
def main():
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if os.environ.get('GITHUB_SHA'):s.require(head==os.environ['GITHUB_SHA'],'EXACT_HEAD_DRIFT')
    suite=unittest.defaultTestLoader.loadTestsFromName('tests.test_strict_semantic_certification_v1')
    with patch('socket.socket',side_effect=AssertionError('Offline network forbidden')),patch('urllib.request.urlopen',side_effect=AssertionError('Offline network forbidden')):
        r=unittest.TextTestRunner(verbosity=2).run(suite);builder_reads=[];s.derive_certificates(ROOT,builder_reads);reapplication_reads=[];s.reapply_root(ROOT,reapplication_reads);state=g.validate_root(ROOT)
    record={'schema':'mxm.v4.semantic-certification.exact-head-offline-validation.v1','exact_validated_head':head,'run_id':os.environ.get('GITHUB_RUN_ID'),'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'tests_passed':r.testsRun-len(r.failures)-len(r.errors)-len(r.skipped),'tests_failed':len(r.failures)+len(r.errors),'tests_skipped':len(r.skipped),'builder_read_allowlist':sorted(s.ALLOWED),'actual_builder_reads':builder_reads,'actual_reapplication_reads':reapplication_reads,'certificate_count':11,'functional_sha256':s.HASHES[s.FUNCTIONAL],'historical_outcome_files_read_by_certification':0,'market_rows_used':0,'network_blocked':True,'market_routes':0,'next_discriminator_executed':False,'state':state}
    print('STRICT_SEMANTIC_CERTIFICATION_VALIDATION='+json.dumps(record,sort_keys=True));return 0 if r.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
