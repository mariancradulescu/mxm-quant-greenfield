"""Existing-App delivery contracts only; fake token, no GitHub or secret calls."""
import contextlib
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from .common import LabError
from . import custody

SOURCE='a'*40;TRIGGER='b'*40


class WriterDelivery(unittest.TestCase):
    def test_prepared_workflow_reuses_dag_and_separates_credentials(self):
        import yaml
        root=Path(__file__).resolve().parents[2]
        original=yaml.safe_load((root/'docs/laboratory-completion/20261020/R3_EXISTING_OPERATIONAL_DAG_BASELINE.yml').read_bytes())
        workflow=custody.build_native_workflow(SOURCE,original)
        self.assertIn('workflow_dispatch',workflow['on'])
        self.assertEqual(len(workflow['jobs']),11)
        self.assertEqual(workflow['jobs']['preflight']['needs'],'source-controls')
        for name,job in workflow['jobs'].items():
            self.assertEqual(job['permissions']['contents'],'read')
            self.assertEqual(job['steps'][0]['with'],{'ref':SOURCE,'persist-credentials':False})
            writer=name in custody.WRITER_JOBS.values()
            self.assertEqual(job['environment'],'mxm-p0-successor-issuer-v1' if writer else 'mxm-r3-custody-v1')
            envs=[step.get('env',{}) for step in job['steps']]
            self.assertEqual(any('SUCCESSOR_APP_PRIVATE_KEY' in e for e in envs),writer)
            self.assertFalse(any(any(k.startswith('CTRADER_') for k in e) for e in envs))
        certifier=custody.build_certifier_workflow(SOURCE)
        self.assertEqual(certifier['jobs']['certify-v3']['permissions']['contents'],'read')
        self.assertEqual(certifier['on']['workflow_run']['types'],['completed'])

    def test_every_prepared_operational_job_passes_independent_code_provenance(self):
        import yaml
        from .attest_v3 import native_checkout_provenance
        from .common import encoded
        baseline=Path(__file__).resolve().parents[2]/'docs/laboratory-completion/20261020/R3_EXISTING_OPERATIONAL_DAG_BASELINE.yml'
        workflow=custody.build_native_workflow(SOURCE,yaml.safe_load(baseline.read_bytes()))
        jobs={name:i+100 for i,name in enumerate(workflow['jobs'])}
        route=SimpleNamespace(json=lambda path:{'total_count':len(jobs),'jobs':[
            {'id':ident,'name':name,'steps':[{'name':'Run '+workflow['jobs'][name]['steps'][0]['uses'],
              'status':'completed','conclusion':'success','number':2}]} for name,ident in jobs.items()]},
            data=lambda path:('2026-10-20T12:00:00Z '+SOURCE+'\n').encode())
        with patch('research_core_v4.laboratory.runtime.file_at',return_value=encoded(workflow)):
            proof=native_checkout_provenance(route,123,SOURCE,TRIGGER,jobs)
        self.assertEqual(set(proof['jobs']),set(jobs))

    def environment(self):
        return {'GITHUB_REPOSITORY':'mariancradulescu/mxm-quant-greenfield','GITHUB_JOB':'segment-intent',
            'GITHUB_REF_NAME':'mxm-remediation-p0-p4-20261015-v1','GITHUB_RUN_ATTEMPT':'1',
            'GITHUB_EVENT_NAME':'workflow_dispatch','LAB_INTEGRATED_PROTOCOL':'v2','LAB_SOURCE_SHA':SOURCE,
            'GITHUB_SHA':TRIGGER,'GITHUB_WORKFLOW_SHA':TRIGGER,
            'GITHUB_WORKFLOW_REF':'mariancradulescu/mxm-quant-greenfield/.github/workflows/mxm-integrated-p0.yml@refs/heads/mxm-remediation-p0-p4-20261015-v1',
            'GH_TOKEN':'ARTIFICIAL_NATIVE_READ_TOKEN'}

    def test_native_github_token_alone_cannot_publish(self):
        with patch.dict(os.environ,self.environment(),clear=True),patch.object(custody.subprocess,'run') as process:
            with self.assertRaisesRegex(LabError,'APP_WRITER_SCOPE_REQUIRED'):
                custody.atomic_publish(object(),'c'*40,{'test':b'ARTIFICIAL'},'ARTIFICIAL')
            process.assert_not_called()

    def test_wrong_job_ref_attempt_or_workflow_is_refused_before_credentials(self):
        for key,value in (('GITHUB_JOB','investigation'),('GITHUB_REF_NAME','main'),
            ('GITHUB_RUN_ATTEMPT','2'),('GITHUB_WORKFLOW_SHA','c'*40),
            ('GITHUB_REPOSITORY','OTHER/OTHER'),('GITHUB_EVENT_NAME','pull_request')):
            env=self.environment();env[key]=value
            with self.subTest(key=key),patch.dict(os.environ,env,clear=True):
                with self.assertRaises(LabError):custody.writer_metadata('claim')

    def test_no_owner_or_broker_key_may_enter_writer_context(self):
        for key in ('R3_CUSTODY_PRIVATE_KEY_PEM','CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_SECRET'):
            env=self.environment();env[key]='ARTIFICIAL_FORBIDDEN'
            with self.subTest(key=key),patch.dict(os.environ,env,clear=True):
                with self.assertRaisesRegex(LabError,'NO_DECRYPTION_OR_BROKER_KEYS'):
                    custody.writer_metadata('claim')

    def exercise(self,fail=False):
        env=self.environment();env['SUCCESSOR_APP_PRIVATE_KEY']='ARTIFICIAL_KEY'
        lifecycle=[]
        @contextlib.contextmanager
        def token(value):
            self.assertEqual(value,'ARTIFICIAL_KEY');lifecycle.append('mint')
            try:yield 'ARTIFICIAL_APP_WRITE_TOKEN'
            finally:lifecycle.append('revoke')
        def workload():
            self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',os.environ)
            self.assertEqual(os.environ['GH_TOKEN'],'ARTIFICIAL_NATIVE_READ_TOKEN')
            self.assertEqual(custody._NATIVE_WRITER_SCOPE['token'],'ARTIFICIAL_APP_WRITE_TOKEN')
            if fail:raise RuntimeError('ARTIFICIAL_FAILURE')
            return 'ARTIFICIAL_ONLY'
        with patch.dict(os.environ,env,clear=True),patch('research_core_v4.laboratory.runtime.anchors'), \
             patch('research_core_v4.laboratory.integrated.definition',return_value=({'mode':'TECHNICAL_NONOUTCOME','economic_release':False},'ref','path')), \
             patch.object(custody.subprocess,'check_output',return_value=SOURCE+'\n'), \
             patch.object(custody.subprocess,'run',return_value=SimpleNamespace(returncode=0)), \
             patch('research_core_v4.p0_successor_a_20261017.issuer._app_token',side_effect=token), \
             patch('research_core_v4.laboratory.operational_acceptance.verify_effective_controls'), \
             patch('research_core_v4.remediation_p0_p4_20261015.rest29_v3.GetOnly.json',return_value={'object':{'sha':TRIGGER}}), \
             patch('research_core_v4.laboratory.integrated.claim',side_effect=workload):
            if fail:
                with self.assertRaisesRegex(RuntimeError,'ARTIFICIAL_FAILURE'):custody.run_native_writer('claim')
            else:self.assertEqual(custody.run_native_writer('claim'),'ARTIFICIAL_ONLY')
            self.assertIsNone(custody._NATIVE_WRITER_SCOPE)
            self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',os.environ)
            self.assertEqual(os.environ['GH_TOKEN'],'ARTIFICIAL_NATIVE_READ_TOKEN')
        self.assertEqual(lifecycle,['mint','revoke'])

    def test_scoped_mint_use_revoke_keeps_key_and_token_out_of_workload_environment(self):self.exercise()
    def test_failure_clears_scope_and_revokes_without_retry(self):self.exercise(True)


if __name__=='__main__':unittest.main()
