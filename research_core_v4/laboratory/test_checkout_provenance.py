"""Independent verifier mutations; artificial GitHub fixtures only."""
import json
import unittest
from .common import encoded
from .test_native_acceptance_v3 import make_fixture,SOURCE,JOB_NAMES
from . import test_native_acceptance_v3 as protocol_fixture

WF='.github/workflows/mxm-integrated-p0.yml'
TRIGGER='9'*40
CHECKOUT='actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683'


class CheckoutProvenance(unittest.TestCase):
    def fixture(self):
        route,gate,_=make_fixture()
        # The original fixture models native jobs but had no source material.
        if (WF,TRIGGER) not in route.storage:
            route.storage[(WF,TRIGGER)]=encoded({'env':{'LAB_SOURCE_SHA':SOURCE,'LAB_INTEGRATED_PROTOCOL':'v2'},
                'jobs':{name:{'steps':[{'name':'Checkout sealed source','uses':CHECKOUT,
                    'with':{'ref':SOURCE,'persist-credentials':False}}]} for name in JOB_NAMES}})
        return route,gate

    def verify(self,route,gate):
        return protocol_fixture.IndependentNativeV3ContractTests().verify(route,gate)

    def test_wrong_checkout_in_one_native_job_is_rejected(self):
        route,gate=self.fixture();value=json.loads(route.storage[(WF,TRIGGER)])
        value['jobs']['investigation']['steps'][0]['with']['ref']='1'*40
        route.storage[(WF,TRIGGER)]=encoded(value)
        with self.assertRaises(Exception):self.verify(route,gate)

    def test_conditional_or_credential_retaining_checkout_is_rejected(self):
        for mode in ('skip','credentials','second'):
            route,gate=self.fixture();value=json.loads(route.storage[(WF,TRIGGER)])
            step=value['jobs']['investigation']['steps'][0]
            if mode=='skip':step['if']='false'
            if mode=='credentials':step['with']['persist-credentials']=True
            if mode=='second':value['jobs']['investigation']['steps'].append(dict(step))
            route.storage[(WF,TRIGGER)]=encoded(value)
            with self.subTest(mode=mode),self.assertRaises(Exception):self.verify(route,gate)

    def test_missing_or_wrong_actual_checkout_log_is_rejected(self):
        for value in (b'',b'2026-10-20T12:00:00Z '+b'1'*40+b'\n'):
            route,gate=self.fixture();original=route.data
            route.data=lambda path: value if path=='actions/jobs/103/logs' else original(path)
            with self.subTest(value=value),self.assertRaises(Exception):self.verify(route,gate)

    def test_source_or_protocol_environment_mismatch_is_rejected(self):
        for key,value in (('LAB_SOURCE_SHA','1'*40),('LAB_INTEGRATED_PROTOCOL','v1')):
            route,gate=self.fixture();workflow=json.loads(route.storage[(WF,TRIGGER)])
            workflow['env'][key]=value;route.storage[(WF,TRIGGER)]=encoded(workflow)
            with self.subTest(key=key),self.assertRaises(Exception):self.verify(route,gate)

    def test_job_import_or_working_directory_override_is_rejected(self):
        for mode in ('source','python','directory','repository','path','action','run'):
            route,gate=self.fixture();workflow=json.loads(route.storage[(WF,TRIGGER)])
            job=workflow['jobs']['investigation']
            if mode=='source':job['env']={'LAB_SOURCE_SHA':'1'*40}
            if mode=='python':job['env']={'PYTHONPATH':'verification/integrated-p0-input'}
            if mode=='directory':job['defaults']={'run':{'working-directory':'verification/integrated-p0-input'}}
            if mode=='repository':job['steps'][0]['with']['repository']='OTHER/OTHER'
            if mode=='path':job['steps'][0]['with']['path']='elsewhere'
            if mode=='action':job['steps'].append({'uses':'UNTRUSTED/UNTRUSTED@main'})
            if mode=='run':job['steps'].append({'run':'python3 -c "print(\"FORGED_CHECKOUT\")"'})
            route.storage[(WF,TRIGGER)]=encoded(workflow)
            with self.subTest(mode=mode),self.assertRaises(Exception):self.verify(route,gate)


if __name__=='__main__':unittest.main()
