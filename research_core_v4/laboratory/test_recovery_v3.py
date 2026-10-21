"""Artificial watchdog metadata and token lifecycle; never native reception."""
import contextlib
import os
import unittest
from unittest.mock import patch
from .common import LabError
from . import recovery_v3 as recovery,custody

class R3ObserverTests(unittest.TestCase):
    def jobs(self,claim='failure',fence='skipped',worker='skipped'):
        return [{'id':i+1,'run_id':22,'name':name,'status':'completed','conclusion':result}
            for i,(name,result) in enumerate([('preflight','success'),('segment-intent',claim),
                ('execution-fence',fence),('investigation',worker),('durable-archive','skipped')])]

    def native(self,status='completed'):
        return {'id':22,'path':recovery.engine.WF,'head_branch':recovery.custody_branch(),
            'run_attempt':1,'status':status,'head_sha':'a'*40}

    def test_only_native_terminal_preexposure_failure_is_recoverable(self):
        state={'pending':{'run_id':22,'phase':'PRE_EXPOSURE'}}
        self.assertEqual(recovery.predecessor(state,self.native(),self.jobs()),'RECOVER_PRE_EXPOSURE')
        self.assertEqual(recovery.predecessor(state,self.native('in_progress'),self.jobs()),'WAIT_ACTIVE_NATIVE_RUN')
        for jobs in (self.jobs(fence='success'),self.jobs(worker='failure'),self.jobs(claim='success')):
            self.assertEqual(recovery.predecessor(state,self.native(),jobs),'HOLD_AMBIGUOUS_EXPOSURE')
        with self.assertRaises(LabError):recovery.predecessor(state,self.native(),self.jobs()+self.jobs()[:1])

    def test_wrong_predecessor_branch_attempt_or_workflow_is_not_authority(self):
        for field,value in [('head_branch','main'),('run_attempt',2),('path','OTHER')]:
            run=self.native();run[field]=value
            with self.subTest(field=field),self.assertRaises(LabError):
                recovery.predecessor({'pending':{'phase':'PRE_EXPOSURE'}},run,self.jobs())

    def test_controlled_fault_flag_requires_exact_native_job_log(self):
        from types import SimpleNamespace
        for flag in ('0','1'):
            route=SimpleNamespace(data=lambda p:('2026-10-21T04:00:00Z   LAB_FAULT_BEFORE_FENCE: '+flag+'\n').encode())
            self.assertEqual(recovery.controlled_fault(route,22,self.jobs()),flag=='1')
        for log in (b'',b'LAB_FAULT_BEFORE_FENCE: 0\n',b'2026-10-21T04:00:00Z LAB_FAULT_BEFORE_FENCE: 0\n'*2):
            with self.subTest(log=log),self.assertRaises(LabError):
                recovery.controlled_fault(SimpleNamespace(data=lambda p:log),22,self.jobs())

    def test_closed_or_foreign_state_cannot_bootstrap_or_dispatch(self):
        for state,initial in [({'source_sha':'b'*40},False),({'source_sha':recovery.ENGINE,'pending':None,'safe_stop':True},False),({},True)]:
            with patch.object(recovery.engine,'current',return_value='a'*40), \
                 patch.object(recovery.engine,'state_at',return_value=(state,initial)), \
                 patch.object(recovery.engine,'dispatch_once') as dispatch:
                self.assertEqual(recovery.observe(object())['dispatches'],0);dispatch.assert_not_called()

    def test_wrong_native_context_rejects_before_code_or_key_access(self):
        with patch.dict(os.environ,{},clear=True),patch.object(recovery.subprocess,'check_output') as process:
            with self.assertRaises(LabError):recovery.context(object())
            process.assert_not_called()

    def exercise_scope(self,fail):
        events=[]
        @contextlib.contextmanager
        def token(value):
            self.assertEqual(value,'ARTIFICIAL_EXISTING_KEY');events.append('mint')
            try:yield 'ARTIFICIAL_APP_TOKEN'
            finally:events.append('revoke')
        env={'GH_TOKEN':'ARTIFICIAL_NATIVE_ACTIONS_TOKEN','SUCCESSOR_APP_PRIVATE_KEY':'ARTIFICIAL_EXISTING_KEY',
             'R3_CONTROL_WITNESS':'{}','GITHUB_JOB':'ordinary-recovery','LAB_SOURCE_SHA':recovery.ENGINE}
        with patch.dict(os.environ,env,clear=True),patch.object(recovery,'context',return_value={'fixture':True}), \
             patch('research_core_v4.p0_successor_a_20261017.issuer._app_token',side_effect=token), \
             patch('research_core_v4.laboratory.operational_acceptance.verify_effective_controls'), \
             patch.object(recovery.runtime,'file_at',return_value=b'ARTIFICIAL'), \
             patch.object(recovery.engine,'current',return_value='a'*40), \
             patch.object(recovery,'bytes_digest',return_value=recovery.ORIGINAL_PUBLIC):
            def work():
                with recovery.observer_scope(object()):
                    self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',os.environ)
                    self.assertEqual(custody._NATIVE_WRITER_SCOPE['source'],recovery.ENGINE)
                    self.assertEqual(custody._NATIVE_WRITER_SCOPE['job'],'ordinary-recovery')
                    self.assertEqual(os.environ['GH_TOKEN'],'ARTIFICIAL_NATIVE_ACTIONS_TOKEN')
                    if fail:raise RuntimeError('ARTIFICIAL_FAILURE')
            if fail:
                with self.assertRaises(RuntimeError):work()
            else:work()
            self.assertIsNone(custody._NATIVE_WRITER_SCOPE)
            self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',os.environ)
        self.assertEqual(events,['mint','revoke'])

    def test_existing_app_scope_is_revoked_and_cleared_after_success(self):self.exercise_scope(False)
    def test_existing_app_scope_is_revoked_and_cleared_after_failure(self):self.exercise_scope(True)

    def test_generated_existing_watchdog_has_no_native_write_or_custody_authority(self):
        workflow=recovery.build_workflow('a'*40);job=workflow['jobs']['ordinary-recovery']
        self.assertEqual(job['permissions'],{'contents':'read','actions':'write'})
        self.assertEqual(job['environment'],'mxm-p0-successor-issuer-v1')
        self.assertFalse(workflow['concurrency']['cancel-in-progress'])
        self.assertEqual(workflow['concurrency']['queue'],'max')
        self.assertEqual(job['steps'][0]['with'],{'ref':'a'*40,'persist-credentials':False})
        keys=set(job['steps'][-1]['env'])
        self.assertNotIn('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM',keys)
        self.assertFalse(any(k.startswith('CTRADER_') for k in keys))

if __name__=='__main__':unittest.main()
