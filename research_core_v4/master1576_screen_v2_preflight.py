"""Runs all required synthetic checks; never supplies a real ARM or private route."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import unittest
from research_core_v4 import master1576_screen_v2 as w
ROOT=Path(__file__).resolve().parents[1]
class Result(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.passed=[]
    def addSuccess(self,test):super().addSuccess(test);self.passed.append(test.id())
def run(output):
    suite=unittest.defaultTestLoader.loadTestsFromName('tests.test_master1576_screen_v2')
    result=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
    report={'schema':'mxm.v4.master1576.qualification-v2.synthetic-preflight.v1','status':'PASS_SYNTHETIC_ONLY_NO_REAL_DECRYPTION' if result.wasSuccessful() else 'FAIL_SYNTHETIC_PREFLIGHT','tests_passed':len(result.passed),'tests_failed':len(result.failures)+len(result.errors),'tests_skipped':len(result.skipped),'tests_total':result.testsRun,'passed_tests':sorted(result.passed),'source_head':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),'job_name':os.environ.get('GITHUB_JOB'),'bindings':{k:{'ref':p,'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for k,p in {'protocol':w.PROTOCOL,'worker':w.WORKER,'tests':'tests/test_master1576_screen_v2.py','runner':'research_core_v4/master1576_screen_v2_preflight.py','campaign_acceptance':w.ACCEPTANCE}.items()},'execution':{'fixture':'Synthetic constant OHLC and volumes across all100 synthetic shards and all1576 accepted identities; separate generated synthetic RSA2048/AES256 cryptographic fixtures. No real encrypted asset downloaded.','real_shards_decrypted':0,'real_screen_executed':False,'broker_contacts':0,'ctrader_secrets_used':False,'new_history_requests':0,'search_budget_use':0,'protected_forward_opened':False,'confirmation_opened':False}}
    Path(output).write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('SYNTHETIC_PREFLIGHT_RESULT='+json.dumps(report,sort_keys=True,separators=(',',':')))
    return 0 if result.wasSuccessful() and not result.skipped else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);raise SystemExit(run(p.parse_args().output))
