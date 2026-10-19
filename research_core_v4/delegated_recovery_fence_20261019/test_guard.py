import ast,copy,unittest
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
if __name__=='__main__':unittest.main()
