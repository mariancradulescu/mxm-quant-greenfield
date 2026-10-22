"""Artificial adversarial registry fixtures; never native acceptance evidence."""
import json,unittest,urllib.error
from copy import deepcopy
from unittest.mock import patch
from . import certificate_registry as c
from .common import encoded,bytes_digest,LabError
from .custody import build_certifier_workflow

SOURCE='a'*40;ISSUER='b'*40;TRIGGER='c'*40;PARENT='d'*40;COMMIT='e'*40
TARGET=123;ISSUANCE=456;JOB=789

def fixture():
    path=c.certificate_path(SOURCE,TARGET)
    record={'schema':c.SCHEMA,'path':path,
        'gate':{'source_sha':SOURCE,'run_id':TARGET,'evidence_oid':PARENT},
        'issuer':{'source_sha':ISSUER,'trigger_sha':TRIGGER,'run_id':ISSUANCE,'job_id':JOB}}
    class Route:
        def __init__(self):
            self.record=deepcopy(record);self.native={'id':ISSUANCE,'path':c.CERTIFIER_WORKFLOW,
                'head_branch':'main','head_sha':TRIGGER,'event':'workflow_dispatch','run_attempt':1,
                'status':'completed','conclusion':'success'}
            self.job={'id':JOB,'run_id':ISSUANCE,'name':'certify-v3','status':'completed','conclusion':'success',
                'steps':[{'name':'Run actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',
                          'status':'completed','conclusion':'success'}]}
            self.workflow=build_certifier_workflow(ISSUER);self.status='added';self.log_origin=ISSUER
            self.commit_parent=PARENT;self.omit_log=False;self.bypass=[];self.native_hash=None
        def data(self,path):
            if path=='actions/jobs/'+str(JOB)+'/logs':
                rec={'path':self.record['path'],'sha256':self.native_hash or bytes_digest(encoded(self.record)),
                     'target_run_id':TARGET,'certificate_commit':COMMIT}
                return ('2026-10-21T00:00:00Z [command]/usr/bin/git log -1 --format=%H\n'
                        '2026-10-21T00:00:01Z '+self.log_origin+'\n'+
                        'MXM_CERTIFIER_SOURCE_CONTROL '+json.dumps({'source_sha':ISSUER,'run_id':ISSUANCE,
                            'policies':[self.json('rulesets/99')]})+'\n'+
                        ('' if self.omit_log else 'MXM_CERTIFICATE_ISSUED '+json.dumps(rec)+'\n')).encode()
            raise KeyError(path)
        def json(self,path):
            if path=='actions/runs/'+str(ISSUANCE):return self.native
            if path=='actions/runs/'+str(ISSUANCE)+'/attempts/1/jobs?per_page=100':return {'jobs':[self.job],'total_count':1}
            if path=='git/ref/heads/'+c.CERTIFIER_BRANCH:return {'object':{'sha':ISSUER}}
            if path=='rules/branches/'+c.CERTIFIER_BRANCH:return [{'type':'update','ruleset_id':99}]
            if path=='rulesets/99':return {'enforcement':'active','bypass_actors':self.bypass,
                'conditions':{'ref_name':{'include':['refs/heads/'+c.CERTIFIER_BRANCH],'exclude':[]}},
                'rules':[{'type':t} for t in ('creation','update','deletion','non_fast_forward')]}
            if path=='commits/'+COMMIT:return {'parents':[{'sha':self.commit_parent}],
                'files':[{'filename':self.record['path'],'status':self.status}]}
            if path.startswith('branches/'):return {'protected':True}
            raise KeyError(path)
        def file(self,route,path,ref):
            if path==c.CERTIFIER_WORKFLOW and ref==TRIGGER:return encoded(self.workflow)
            if path==record['path'] and ref in (COMMIT,PARENT):return encoded(self.record)
            raise KeyError((path,ref))
    return Route(),record

class CertificateRegistryTests(unittest.TestCase):
    def verify(self,route):
        with patch('research_core_v4.laboratory.runtime.file_at',side_effect=route.file),\
             patch('research_core_v4.laboratory.operational_acceptance.verify_operational_acceptance') as full:
            result=c.verify_registered_certificate(route,COMMIT,SOURCE,TARGET)
            full.assert_called_once_with(route,route.record['gate'],SOURCE,{'main':True,
                'mxm-remediation-p0-p4-20261015-v1':True})
            return result
    def test_source_and_execution_identities_do_not_collide_with_r6_or_each_other(self):
        paths={c.certificate_path(SOURCE,TARGET),c.certificate_path(SOURCE,TARGET+1),
               c.certificate_path('f'*40,TARGET),c.LEGACY_CERT}
        self.assertEqual(len(paths),4)
        for value in (True,0,-1,'123'):
            with self.subTest(value=value),self.assertRaises(LabError):c.certificate_path(SOURCE,value)
        with self.assertRaises(LabError):c.certificate_path('../'+SOURCE,TARGET)
    def test_complete_native_origin_required_before_full_gate_consumer(self):
        route,record=fixture();self.assertEqual(self.verify(route),record['gate'])
    def test_forged_source_run_or_path_even_with_rehashed_payload_refused(self):
        for key,value in (('path',c.LEGACY_CERT),('source_sha','f'*40),('run_id',TARGET+1)):
            route,_=fixture()
            if key=='path':route.record[key]=value
            else:route.record['gate'][key]=value
            with self.subTest(key=key),self.assertRaises(LabError):self.verify(route)
    def test_native_failure_inflight_rerun_wrong_workflow_or_trigger_refused(self):
        for key,value in (('conclusion','failure'),('status','in_progress'),('run_attempt',2),
                          ('path','.github/workflows/forged.yml'),('head_sha','f'*40),('head_branch','other')):
            route,_=fixture();route.native[key]=value
            with self.subTest(key=key),self.assertRaises(LabError):self.verify(route)
    def test_issuer_job_checkout_provenance_and_log_hash_are_not_favorable_flags(self):
        for kind in ('job','checkout','log','hash','workflow','bypass'):
            route,_=fixture()
            if kind=='job':route.job['run_id']=TARGET
            if kind=='checkout':route.log_origin='f'*40
            if kind=='log':route.omit_log=True
            if kind=='hash':route.native_hash='0'*64
            if kind=='workflow':route.workflow['jobs']['certify-v3']['steps'][0]['with']['persist-credentials']=True
            if kind=='bypass':route.bypass=[{'actor_type':'Integration','actor_id':1,'bypass_mode':'always'}]
            with self.subTest(kind=kind),self.assertRaises(LabError):self.verify(route)
    def test_replacement_and_unrelated_native_commit_refused(self):
        for field,value in (('status','modified'),('commit_parent','f'*40)):
            route,_=fixture();setattr(route,field,value)
            with self.subTest(field=field),self.assertRaises(LabError):self.verify(route)
    def test_redacted_live_actors_need_exact_native_seal_revision(self):
        route,_=fixture();policy=route.json('rulesets/99');policy.update(id=99,updated_at='2026-10-21T00:00:00Z')
        native=deepcopy(policy);del policy['bypass_actors']
        original=route.json
        def get(path):return policy if path=='rulesets/99' else original(path)
        route.json=get
        with self.assertRaises(LabError):c.verify_certifier_seal(route,ISSUER)
        c.verify_certifier_seal(route,ISSUER,{'policies':[native]})
        policy['updated_at']='2026-10-21T00:01:00Z'
        with self.assertRaises(LabError):c.verify_certifier_seal(route,ISSUER,{'policies':[native]})
    def test_collision_no_overwrite_and_only_404_means_absent(self):
        route,record=fixture();path=record['path']
        with patch('research_core_v4.laboratory.runtime.file_at',return_value=encoded(record)):
            self.assertTrue(c.existing_record(route,PARENT,path,record))
            forged=deepcopy(record);forged['gate']['run_id']+=1
            with self.assertRaisesRegex(LabError,'COLLISION'):c.existing_record(route,PARENT,path,forged)
        for code in (404,403,500):
            error=urllib.error.HTTPError('https://api.github.com/',code,'test',{},None)
            with patch('research_core_v4.laboratory.runtime.file_at',side_effect=error):
                if code==404:self.assertFalse(c.existing_record(route,PARENT,path,record))
                else:
                    with self.assertRaises(urllib.error.HTTPError):c.existing_record(route,PARENT,path,record)

if __name__=='__main__':unittest.main()
