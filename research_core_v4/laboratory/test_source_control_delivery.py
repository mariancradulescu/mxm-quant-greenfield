"""Artificial native-log controls; never a real App/ACL acceptance claim."""
import json
import os
import unittest
from copy import deepcopy
from unittest.mock import patch
from .common import encoded,LabError
from .custody import verify_native_source_control,atomic_publish
from . import custody
from .test_native_acceptance_v3 import make_fixture,SOURCE,RUN


class SourceControlDelivery(unittest.TestCase):
    def fixture(self):
        route,_,_=make_fixture();original_json=route.json;original_data=route.data
        workflow_path=('.github/workflows/mxm-integrated-p0.yml','9'*40)
        workflow=json.loads(route.storage[workflow_path])
        workflow['jobs']['source-controls']={'steps':[{'name':'Checkout sealed source',
            'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',
            'with':{'ref':SOURCE,'persist-credentials':False}},
            {'run':'python3 -m research_core_v4.laboratory.custody source-controls'}]}
        route.storage[workflow_path]=encoded(workflow)
        route.control_job={'id':77,'name':'source-controls','run_id':RUN,'status':'completed','conclusion':'success',
            'steps':[{'name':'Checkout sealed source','number':2,'status':'completed','conclusion':'success'}]}
        def query(path):
            if path=='git/ref/heads/mxm-remediation-p0-p4-20261015-v1':return {'object':{'sha':'9'*40}}
            if path=='actions/runs/'+str(RUN)+'/attempts/1/jobs?per_page=100':
                rows=original_json(path)['jobs']+[route.control_job]
                return {'jobs':rows,'total_count':len(rows)}
            return original_json(path)
        route.json=query
        policy={'id':3,'enforcement':'active','bypass_actors':[],
            'conditions':{'ref_name':{'include':['refs/heads/mxm-o04-successor-code-integrated-p0-r3'],'exclude':[]}},
            'rules':[{'type':k} for k in ('creation','update','deletion','non_fast_forward')],
            'updated_at':'2026-10-20T12:00:00Z'}
        route.proof={'schema':'mxm.native-source-control.v1','run_id':RUN,'attempt':1,
            'source_sha':SOURCE,'trigger_sha':'9'*40,'source_policies':[policy],
            'writes':0,'orders':0,'economic_outcomes':0}
        route.data=lambda path: (('2026-10-20T12:00:00Z '+SOURCE+'\nMXM_SOURCE_CONTROL '+
            json.dumps(route.proof)+'\n').encode() if path=='actions/jobs/77/logs' else original_data(path))
        observed=deepcopy(policy);observed.pop('bypass_actors')
        return route,observed

    def check(self,route,observed):
        with patch.dict(os.environ,{'GITHUB_RUN_ID':str(RUN),'GITHUB_RUN_ATTEMPT':'1','GITHUB_JOB':'preflight',
             'LAB_SOURCE_SHA':SOURCE,'GITHUB_SHA':'9'*40}):return verify_native_source_control(route,observed)

    def test_independent_successful_same_run_pinned_control_job_admits(self):
        route,observed=self.fixture();self.assertEqual(self.check(route,observed)['bypass_actors'],[])

    def test_old_source_run_trigger_or_attempt_is_not_authority(self):
        for key,value in (('run_id',RUN-1),('attempt',2),('source_sha','1'*40),('trigger_sha','2'*40),('writes',1)):
            route,observed=self.fixture();route.proof[key]=value
            with self.subTest(key=key),self.assertRaises(LabError):self.check(route,observed)

    def test_changed_redacted_policy_or_nonempty_bypass_is_held(self):
        for mode in ('revision','bypass','omitted_bypass','missing_policy','conditions','rules'):
            route,observed=self.fixture();policy=route.proof['source_policies'][0]
            if mode=='revision':observed['updated_at']='2026-10-20T12:00:01Z'
            elif mode=='bypass':policy['bypass_actors']=[{'actor_id':5343530}]
            elif mode=='omitted_bypass':policy.pop('bypass_actors')
            elif mode=='missing_policy':route.proof['source_policies']=[]
            elif mode=='conditions':observed['conditions']['ref_name']['exclude']=['refs/heads/OTHER']
            else:observed['rules'].pop()
            with self.subTest(mode=mode),self.assertRaises(LabError):self.check(route,observed)

    def test_successful_job_label_requires_real_successful_checkout(self):
        for mode in ('failed_job','skipped_checkout','wrong_checkout','missing_record','duplicate_record'):
            route,observed=self.fixture()
            if mode=='failed_job':route.control_job['conclusion']='failure'
            elif mode=='skipped_checkout':route.control_job['steps'][0]['conclusion']='skipped'
            elif mode=='wrong_checkout':
                key=('.github/workflows/mxm-integrated-p0.yml','9'*40);workflow=json.loads(route.storage[key])
                workflow['jobs']['source-controls']['steps'][0]['with']['ref']='1'*40;route.storage[key]=encoded(workflow)
            else:
                original=route.data;record=original('actions/jobs/77/logs')
                route.data=lambda path: (record.split(b'MXM_SOURCE_CONTROL')[0] if mode=='missing_record' else record+record) if path=='actions/jobs/77/logs' else original(path)
            with self.subTest(mode=mode),self.assertRaises(LabError):self.check(route,observed)

    def test_app_control_scope_cannot_publish_any_evidence(self):
        scope={'job':'source-controls','source':SOURCE,'operation':'source-controls'}
        with patch.object(custody,'_NATIVE_WRITER_SCOPE',scope),patch.dict(os.environ,{'GITHUB_JOB':'source-controls','LAB_SOURCE_SHA':SOURCE}),patch.object(custody.subprocess,'run') as run:
            with self.assertRaisesRegex(LabError,'APP_WRITER_SCOPE_REQUIRED'):atomic_publish(object(),'a'*40,{'fake':b'FAKE'},'FAKE')
            run.assert_not_called()


if __name__=='__main__':unittest.main()
