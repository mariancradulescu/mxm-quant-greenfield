"""Offline architecture tests: disposable local Git, no real asset or private key."""
import argparse
import json
import os
from pathlib import Path
import unittest
from research_core_v4 import master1576_screen_v2_real_launcher_v1 as l
ROOT=Path(__file__).resolve().parents[1]
class Result(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.passed=[]
    def addSuccess(self,test):super().addSuccess(test);self.passed.append(test.id())
def run(output):
    suite=unittest.defaultTestLoader.loadTestsFromName('tests.test_master1576_real_execution_architecture_v1')
    r=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
    paths={'architecture':l.ARCH,'launcher':l.LAUNCHER,'workflow':l.WORKFLOW,'tests':'tests/test_master1576_real_execution_architecture_v1.py','runner':'research_core_v4/master1576_real_execution_architecture_preflight_v1.py','protocol':l.w.PROTOCOL,'worker':l.w.WORKER,'accepted_preflight':l.w.PREFLIGHT,'campaign_acceptance':l.w.ACCEPTANCE}
    report={'schema':'mxm.v4.master1576.qualification-v2.execution-architecture-synthetic-preflight.v1','status':'PASS_SYNTHETIC_ONLY_NO_REAL_AUTHORIZATION' if r.wasSuccessful() else 'FAIL_SYNTHETIC_PREFLIGHT','tests_passed':len(r.passed),'tests_failed':len(r.failures)+len(r.errors),'tests_skipped':len(r.skipped),'tests_total':r.testsRun,'passed_tests':sorted(r.passed),'source_head':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),'job_name':os.environ.get('GITHUB_JOB'),'bindings':{k:{'ref':p,'sha256':l.w.sha(l.raw(ROOT,p))} for k,p in paths.items()},'execution':{'fixture':'Real disposable local Git commits; fake GitHub metadata/claim/publication provider. Actual frozen verify_arm invoked with synthetic ls-remote only. Synthetic reducer uses fabricated constant OHLC; completion counts fabricated for publication control testing. No real shard read.','real_authorization_created':False,'real_private_key_secret_used':False,'real_asset_downloaded':False,'real_shard_decrypted':False,'real_screen_executed':False,'real_result_published':False,'broker_contacts':0,'new_history_requests':0,'search_budget_use':0,'protected_forward_opened':False,'confirmation_opened':False}}
    Path(output).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print('EXECUTION_ARCHITECTURE_PREFLIGHT_RESULT='+json.dumps(report,sort_keys=True,separators=(',',':')))
    return 0 if r.wasSuccessful() and not r.skipped else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);raise SystemExit(run(p.parse_args().output))
