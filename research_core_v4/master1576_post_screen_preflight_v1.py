"""Exact-head offline accounting and unresolved-duration validation; no secrets."""
import json
import os
from pathlib import Path
import unittest
from research_core_v4 import master1576_post_screen_v1 as p
class Result(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.passed=[]
    def addSuccess(self,t):super().addSuccess(t);self.passed.append(t.id())
def main():
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromName(name) for name in ['tests.test_master1576_post_screen_v1','tests.test_master1576_current_state_guard_v1']])
    r=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
    root=Path(__file__).resolve().parents[1]
    out={'status':'PASS_EXACT_HEAD_OFFLINE' if r.wasSuccessful() else 'FAIL_EXACT_HEAD_OFFLINE','source_head':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),'job_name':os.environ.get('GITHUB_JOB'),'tests_passed':len(r.passed),'tests_failed':len(r.failures)+len(r.errors),'tests_skipped':len(r.skipped),'passed_tests':sorted(r.passed),'bindings':{path:p.bind(root,path) for path in [p.ACCEPT,p.SUMMARY,p.ROSTER,p.DESIGN,p.POWER,p.S+'MASTER1576_V2_POST_SCREEN_CANONICAL_CURRENT_STATE_REPAIR_AUTHORITY_V1.json','research_core_v4/master1576_current_state_guard_v1.py','tests/test_master1576_current_state_guard_v1.py','.github/workflows/master1576-post-screen-offline.yml',p.S+'V4_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json']},'duration_selected':False,'power_explicitly_blocked':True,'real_shard_redecryptions':0,'broker_contacts':0,'new_history_requests':0,'search_budget_use':0,'protected_forward_opened':False,'confirmation_opened':False}
    print('POST_SCREEN_OFFLINE_RESULT='+json.dumps(out,sort_keys=True,separators=(',',':')));return 0 if r.wasSuccessful() and not r.skipped else 1
if __name__=='__main__':raise SystemExit(main())
