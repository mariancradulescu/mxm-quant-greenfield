"""One finite machine-readable verification receipt, no broker endpoints."""
import datetime
import hashlib
import json
import os
import pathlib
import socket
import subprocess
import unittest
from unittest.mock import patch
from . import test_acceptance as tests
from . import test_extended as extended
from .safety import canonical,sha,BASE
ROOT=pathlib.Path(__file__).resolve().parents[2];P=pathlib.Path(__file__).parent

class Result(unittest.TextTestResult):
    def __init__(self,*args,**kw):super().__init__(*args,**kw);self.passed=[];self.failed=[]
    def addSuccess(self,test):super().addSuccess(test);self.passed.append(test._testMethodName)
    def addFailure(self,test,err):super().addFailure(test,err);self.failed.append(test._testMethodName)
    def addError(self,test,err):super().addError(test,err);self.failed.append(test._testMethodName)

def main():
    results=[];stopped=False
    # Suites execute sequentially; a failed phase blocks dependent later phases.
    with patch.object(socket,'create_connection',side_effect=RuntimeError('NETWORK_FORBIDDEN_OFFLINE_TEST')):
        for phase in ('P0','P1','P2','P3','P4'):
            if stopped:results.append({'phase':phase,'state':'NOT_RUN_DEPENDENCY_FAILED','passed':[],'failed':[]});continue
            suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(getattr(tests,phase)),unittest.defaultTestLoader.loadTestsFromTestCase(getattr(extended,phase+'More')),unittest.defaultTestLoader.loadTestsFromTestCase(getattr(extended,phase+'Final'))])
            result=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
            results.append({'phase':phase,'state':'PASS' if result.wasSuccessful() else 'FAIL','passed':result.passed,'failed':result.failed});stopped=not result.wasSuccessful()
    passed={name for x in results for name in x['passed']};failed={name for x in results for name in x['failed']}
    contracts=[]
    for c in json.loads((P/'acceptance_contracts.json').read_text()):
        name=tests.MAPPING.get(c['test_id']);status='PASS' if name in passed else 'FAIL' if name in failed else 'NOT_RUN'
        reason=None
        if not name:
            text=(c['oracle']['positive_input_recipe']+' '+c['oracle']['positive_expected_assertions']).lower()
            if any(x in text for x in ('owner','private','historical','acl','signed','independent','44 ','74 ','79 ')):
                status='BLOCKED';reason='Exact native/OWNER historical inventory, independent principal or ACL evidence in this contract has not been recovered; manifest1807 proof alone cannot close it.'
            else:reason='No complete executable witness for this exact contract in this run; related unit tests do not close it.'
        contracts.append({'test_id':c['test_id'],'issue_id':c['issue_id'],'phase':c['phase'],'status':status,'witness':name,'negative_control_executed':name in passed or name in failed,'reason':reason,'independent_acceptance':False})
    sources={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts and p.suffix in ('.py','.json','.yml','.yaml','.cs','.csproj','.proto','.lock') and 'verification' not in p.parts}
    from .control import executable_inventory
    dependency_inventory=executable_inventory(ROOT)
    report={'schema':'MXM_REMEDIATION_P0_P4_FINAL_VERIFICATION_BUNDLE','source_head':os.environ.get('GITHUB_SHA',subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()),'base_head':BASE,'run_id':os.environ.get('GITHUB_RUN_ID'),'job':os.environ.get('GITHUB_JOB'),'attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phases':results,'contracts':contracts,'source_sha256':sources,'dependency_inventory':dependency_inventory,'source_inventory_scope':'CHECKOUT_EXECUTABLE_AND_STRUCTURED_FILES;NOT_PROOF_OF_ALL_DYNAMIC_EXTERNAL_IMPORTS','broker_requests':0,'orders':0,'cloud_deployments':0,'alpha_certified':False,'HARD21':False,'platform_certified':False,'OWNER_VERIFIED':False,'independent_post_remediation_audit':'REQUIRED','scope_caveat':'PASS identifies deterministic synthetic producer witness, not independent signoff or historical corpus impact.'}
    out=ROOT/'verification';out.mkdir(exist_ok=True);(out/'acceptance.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    (out/'digests.json').write_text(json.dumps({'acceptance.json':sha((out/'acceptance.json').read_bytes())},indent=2)+'\n')
    print(json.dumps({'test_methods':len(passed)+len(failed),'passed':len(passed),'failed':len(failed),'contracts':{v:sum(c['status']==v for c in contracts) for v in ('PASS','FAIL','BLOCKED','NOT_RUN')},'alpha_certified':False}))
    if stopped:raise SystemExit(1)
if __name__=='__main__':main()
