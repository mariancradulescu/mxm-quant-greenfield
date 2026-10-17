"""New native B admission delta. No App token or GitHub writer is invoked."""
import copy
import dataclasses
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from research_core_v4.p0_successor_a_20261017 import publisher as accepted_transport
from .lab import git
from . import native as n
from .test_continuity import root
from .continuity import *
from research_core_v4.p0_supersession_20261016.authority import Denied

class NativeAdmission(unittest.TestCase):
    def setUp(self):
        self.p=root();self.p['source_sha']='a'*40
        a={'schema':'mxm.successor-b-access.v1','app_id':5343530,'installation_id':172030470,
           'repository_id':1374181010,'source_branch':n.SOURCE,'source_freeze_ruleset_id':987,
           'private_key_fingerprint':n.KEY_FP,'old_custody_closed_at':1,
           'custody_evidence_sha256':'c'*64,'exclusive_custody_confirmed':True}
        m={'schema':'mxm.owner-critical-manifest.v2','critical_operation':'BOOTSTRAP_AND_DELEGATE',
           'operation_id':'MXM-B-test','source_sha':self.p['source_sha'],
           'policy_sha256':digest(canonical({'root':self.p,'access':a})),
           'audit_reception_sha256':'d'*64,'owner_root_oid':OWNER_ROOT[1],
           'not_before':1000,'expires_at':87400}
        binding=n.GateBinding(42,n.GATE_ID,n.GATE,'a'*40,n.WORKFLOW,digest(canonical(m)))
        self.b={'root':self.p,'access':a,'manifest':m,'binding':dataclasses.asdict(binding)}
        self.run={'id':42,'run_attempt':1,'head_sha':'a'*40,'path':n.WORKFLOW,
                  'repository':{'full_name':'mariancradulescu/mxm-quant-greenfield'}}
        self.reviews=[{'environments':[{'id':n.GATE_ID,'name':n.GATE}],
            'state':'approved','user':{'id':322088485,'type':'User'},
            'comment':'MXM_OWNER_CRITICAL_APPROVAL_V2 sha256='+binding.manifest_sha256}]
        self.env=patch.dict(os.environ,{'GITHUB_SHA':'a'*40});self.env.start();self.addCleanup(self.env.stop)
    def verify(self,b=None,now=4000,initial=False):
        with patch.object(n.GitHubReadOnly,'review_history',return_value=(self.run,self.reviews)):
            return n.verify_bundle(b or self.b,now,initial=initial)
    def test_original_native_review_reused_after_24h(self):
        self.assertEqual(self.verify(now=1000+3*86400)[0],self.p)
        with self.assertRaisesRegex(Denied,'INITIAL_REVIEW_EXPIRED'):self.verify(now=1000+3*86400,initial=True)
    def test_native_review_missing_wrong_actor_or_hash(self):
        for rows in ([],[dict(self.reviews[0],user={'id':1,'type':'User'})],
                     [dict(self.reviews[0],comment='same actor is not approval')]):
            self.reviews=rows
            with self.assertRaises(Denied):self.verify()
    def test_old_custody_ttl_and_exclusive_boundary(self):
        with self.assertRaisesRegex(Denied,'CUSTODY_OR_TTL'):self.verify(now=3600)
        b=copy.deepcopy(self.b);b['access']['exclusive_custody_confirmed']=False
        b['manifest']['policy_sha256']=digest(canonical({'root':b['root'],'access':b['access']}))
        with self.assertRaisesRegex(Denied,'CUSTODY_OR_TTL'):self.verify(b)
    def test_source_and_custody_configuration_bound_to_exact_review(self):
        for field,value in [('source_branch','main'),('private_key_fingerprint','other'),('source_freeze_ruleset_id',988)]:
            b=copy.deepcopy(self.b);b['access'][field]=value
            with self.assertRaisesRegex(Denied,'NATIVE_ROOT_BINDING'):self.verify(b)
        with patch.dict(os.environ,{'GITHUB_SHA':'f'*40}):
            with self.assertRaisesRegex(Denied,'EXECUTION_SOURCE'):self.verify()
    def test_server_exact_acl_and_source(self):
        freeze={'enforcement':'active','conditions':{'ref_name':{'include':['refs/heads/'+n.SOURCE],'exclude':[]}},
                'rules':[{'type':t} for t in ('creation','update','deletion','non_fast_forward')],'bypass_actors':[]}
        acl=copy.deepcopy(freeze);acl['conditions']['ref_name']['include']=[ACTIVE_REF]
        acl['bypass_actors']=[{'actor_id':5343530,'actor_type':'Integration','bypass_mode':'always'}]
        def route(path,*args,**kw):
            if path.endswith('rulesets/987'):return 200,freeze
            if path.endswith('rulesets/25268790'):return 200,acl
            return 200,{'object':{'sha':OWNER_ROOT[1] if path.endswith('1807-v1') else 'a'*40}}
        with patch.object(n,'http',side_effect=route):
            n.verify_server(self.p,self.b['access'],'FIXTURE_NOT_A_TOKEN',exact_acl=True)
            acl['bypass_actors'].append({'actor_id':1,'actor_type':'Integration','bypass_mode':'always'})
            with self.assertRaisesRegex(Denied,'SINGLE_PRINCIPAL'):n.verify_server(self.p,self.b['access'],'FIXTURE_NOT_A_TOKEN',exact_acl=True)
            acl['bypass_actors'].pop();del freeze['bypass_actors']
            with self.assertRaisesRegex(Denied,'SOURCE_BYPASS'):n.verify_server(self.p,self.b['access'],'FIXTURE_NOT_A_TOKEN',exact_acl=True)
    def test_no_key_read_or_token_before_native_admission(self):
        with (patch.dict(os.environ,{'GITHUB_REPOSITORY':'mariancradulescu/mxm-quant-greenfield',
            'GITHUB_REF':'refs/heads/'+n.SOURCE,'GITHUB_RUN_ATTEMPT':'1','GITHUB_JOB':'successor-issuer',
            'B_BUNDLE':canonical(self.b).decode(),'B_COMMAND':'continue'}), patch.object(n,'_app_token') as token,
            patch.object(n.GitHubReadOnly,'review_history',return_value=(self.run,[]))):
            with self.assertRaises(Denied):n.execute()
            token.assert_not_called()
    def test_git_child_environment_has_no_owner_or_app_key(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{
            'MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM':'FIXTURE_OWNER_SECRET',
            'SUCCESSOR_APP_PRIVATE_KEY':'FIXTURE_APP_SECRET'}):
            store=n.NativeStore(pathlib.Path(d)/'repo','FIXTURE_INSTALLATION_TOKEN',self.b)
            self.assertNotIn('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM',store.env)
            self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',store.env)
    def test_native_transport_real_receive_pack_cas_and_cold_read(self):
        with tempfile.TemporaryDirectory() as d:
            remote=pathlib.Path(d)/'isolated.git';remote.mkdir();git(remote,'init','--bare','-q')
            # Explicit test-only module patch, never a runtime environment hook.
            with patch.object(n,'REMOTE',str(remote)),patch.object(accepted_transport,'REMOTE',str(remote)):
                one=n.NativeStore(pathlib.Path(d)/'one','FIXTURE_NOT_A_TOKEN',self.b)
                two=n.NativeStore(pathlib.Path(d)/'two','FIXTURE_NOT_A_TOKEN',self.b)
                self.assertEqual(one.read(),(None,None))
                h=one.cas(None,one.wrap(genesis(self.p)));h,s=two.read()
                renewed=propose(self.p,s['control'],h,4000,'renew')['state']
                one.cas(h,one.wrap(renewed));h,s=two.read()
                a=propose(self.p,s['control'],h,4001,'claim',input_sha256='c'*64,exclusivity_verified=True)['state']
                b=propose(self.p,s['control'],h,4001,'claim',input_sha256='d'*64,exclusivity_verified=True)['state']
                def publish(pair):
                    store,value=pair
                    try:store.cas(h,store.wrap(value));return 'WIN'
                    except Denied:return 'FENCED'
                with ThreadPoolExecutor(2) as pool:
                    results=list(pool.map(publish,[(one,a),(two,b)]))
                self.assertEqual(sorted(results),['FENCED','WIN'])
                cold=n.NativeStore(pathlib.Path(d)/'cold','FIXTURE_NOT_A_TOKEN',self.b)
                h,s=cold.read()
                with self.assertRaisesRegex(Denied,'PENDING_ACK_STOP'):
                    propose(self.p,s['control'],h,87400,'renew')

if __name__=='__main__':unittest.main(verbosity=2)
