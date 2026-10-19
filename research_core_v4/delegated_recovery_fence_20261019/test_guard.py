import ast,base64,copy,io,json,os,unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path
from .guard import admit
SOURCE='a'*40;BRANCH='SEALED';WORKFLOW='.github/workflows/sealed.yml'
class NativeIssuerFence(unittest.TestCase):
    def setUp(self):
        self.state={'done':[{'run_id':17}]}
        self.run={'id':17,'head_sha':SOURCE,'head_branch':BRANCH,'path':WORKFLOW,'run_attempt':1,'conclusion':'success'}
        self.jobs=[{'id':9,'run_id':17,'name':'delegated-issuer','status':'completed','conclusion':'success'}]
    def call(self):return admit(self.state,self.run,self.jobs,SOURCE,BRANCH,WORKFLOW)
    def test_native_issuer_success_is_required(self):self.assertEqual(self.call(),'ADMITTED')
    def test_task_commit_before_revocation_failure_cannot_continue(self):
        for outcome in ('failure','cancelled','timed_out','skipped',None):
            self.jobs[0]['conclusion']=outcome
            self.assertEqual(self.call(),'PREVIOUS_ISSUER_FAILED_STOP')
    def test_in_progress_after_git_completion_waits(self):
        self.jobs[0]['status']='in_progress';self.assertEqual(self.call(),'PREVIOUS_ISSUER_NOT_TERMINAL_WAIT')
    def test_cancelled_handoff_after_successful_issuer_is_not_a_fabricated_failure(self):
        self.run['conclusion']='cancelled';self.assertEqual(self.call(),'ADMITTED')
    def test_foreign_source_or_retried_workload_stops(self):
        for key,value in [('id',18),('head_sha','f'*40),('head_branch','other'),('path','other'),('run_attempt',2)]:
            old=self.run[key];self.run[key]=value;self.assertEqual(self.call(),'PREVIOUS_WORKLOAD_IDENTITY_STOP');self.run[key]=old
    def test_missing_duplicate_or_foreign_issuer_stops(self):
        original=copy.deepcopy(self.jobs)
        for jobs in ([],original+original,[{**original[0],'run_id':18}]):
            self.jobs=jobs;self.assertEqual(self.call(),'PREVIOUS_ISSUER_IDENTITY_STOP')
    def test_crash_immediately_after_migration_no_first_task_stops(self):
        self.state={'done':[]};self.assertEqual(self.call(),'NO_FIRST_ISSUER_RECEIPT_STOP')
    def test_embedded_guard_is_byte_identical_and_no_secrets_bound(self):
        root=Path(__file__).resolve().parents[2]
        text=(root/'.github/workflows/mxm-delegated-bc-recovery.yml').read_text()
        embedded=text.split('          # BEGIN_NATIVE_ISSUER_GUARD\n',1)[1].split('          # END_NATIVE_ISSUER_GUARD',1)[0]
        embedded='\n'.join(line[10:] for line in embedded.rstrip().split('\n'))+'\n'
        expected=(Path(__file__).with_name('guard.py')).read_text().split('def admit(',1)[1]
        self.assertEqual(embedded,'def admit('+expected)
        self.assertNotIn('secrets.',text);self.assertNotIn('contents: write',text)

class EndToEndRecoveryFence(unittest.TestCase):
    def execute(self,outcome='success',move=False):
        from research_core_v4.delegated_campaign_20261019 import watch,control as c
        state=c.genesis(SOURCE,1000);state=c.propose(state,SOURCE,'b'*40,1001,'renew')
        state=c.propose(state,SOURCE,'b'*40,1001,'claim',run_id=17)
        state=c.propose(state,SOURCE,'b'*40,1002,'complete',run_id=17,result_sha256='c'*64,checkpoint_sha256='d'*64)
        calls=[];reads=0
        def http(path,token,method='GET',body=None):
            nonlocal reads
            calls.append((path,method,body))
            if 'contents/state.json?' in path:
                reads+=1
                return 200,{'size':2000,'encoding':'base64','sha':('2' if move and reads>=3 else '1')*40,
                    'content':base64.b64encode(c.canonical(state)).decode()}
            if 'git/ref' in path:return 200,{'object':{'sha':SOURCE}}
            if '/jobs?' in path:return 200,{'jobs':[{'run_id':17,'name':'delegated-issuer','status':'completed','conclusion':outcome}]}
            if path.endswith('actions/runs/17'):return 200,{'id':17,'head_sha':SOURCE,'head_branch':c.SOURCE,'path':c.WORKFLOW,'run_attempt':1}
            if 'actions/runs?' in path:return 200,{'workflow_runs':[]}
            if method=='POST':return 204,None
            raise AssertionError(path)
        root=Path(__file__).resolve().parents[2]
        yaml=(root/'.github/workflows/mxm-delegated-bc-recovery.yml').read_text()
        program=yaml.split("          python3 - <<'PY'\n",1)[1].split('          PY',1)[0]
        program='\n'.join(line[10:] for line in program.rstrip().split('\n'))+'\n'
        env={'GITHUB_REPOSITORY':'mariancradulescu/mxm-quant-greenfield','GITHUB_REF_NAME':'main',
            'GITHUB_RUN_ATTEMPT':'1','GITHUB_JOB':'ordinary-recovery','BC_EXPECTED_SOURCE_SHA':SOURCE,'GH_TOKEN':'FIXTURE'}
        with patch.dict(os.environ,env,clear=True),patch.object(watch,'http',http),redirect_stdout(io.StringIO()) as output:
            try:exec(compile(program,'<actual-embedded-recovery>','exec'),{})
            except SystemExit as error:
                if error.code not in (0,None,'RECOVERY_STATE_CHANGED_NO_DISPATCH'):raise
        return calls,output.getvalue()
    def test_actual_wrapper_dispatches_after_native_success_only(self):
        calls,output=self.execute()
        self.assertEqual(sum(c[1]=='POST' for c in calls),1)
        self.assertIn('PREVIOUS_ISSUER_NATIVE_SUCCESS_VERIFIED',output)
        self.assertIn('ORDINARY_CONTINUATION_DISPATCHED',output)
    def test_actual_wrapper_never_dispatches_after_revocation_failure_case(self):
        calls,output=self.execute(outcome='failure')
        self.assertFalse(any(c[1]=='POST' for c in calls));self.assertIn('PREVIOUS_ISSUER_FAILED_STOP',output)
    def test_checkpoint_change_between_admission_and_dispatch_stops(self):
        calls,output=self.execute(move=True)
        self.assertFalse(any(c[1]=='POST' for c in calls))

if __name__=='__main__':unittest.main()
