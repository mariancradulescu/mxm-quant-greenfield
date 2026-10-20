"""Independent P0-17 producer/consumer protocol and negative controls.

All objects in this module are artificial protocol fixtures. Passing tests
NEVER means that an actual native v3 job or encrypted market archive ran.
"""
import unittest
from copy import deepcopy
from unittest.mock import patch
from .common import digest,encoded
from .protocol import ORIGINAL_PUBLIC
from .attest_v3 import (proof_paths,build_issuer,validate_cold_artifact,
                        validate_negative_artifact)
from .evidence_v3 import native_adapter_attestation
from .operational_acceptance import verify_operational_acceptance,BRANCH,EXEC,CODE

RUN=24681357
SOURCE='f'*40
CHECKPOINT='a'*40
HEAD='b'*40
HISTORIC=39322312307
JOB_NAMES=('preflight','segment-intent','execution-fence','investigation',
           'durable-archive','cold-readback','fault-probes','attest-v3')
NEG_NAMES=('segment-intent','execution-fence','investigation')

class ArtificialRoute:
    def __init__(self):
        self.run_ok=True
        self.main_protected=True
        self.missing_job=None
        self.storage={}
        self.current_head=HEAD
        self.divergent=False
        self.divergent_ack=False
    def data(self,path):
        if path in ['actions/jobs/'+str(100+i)+'/logs' for i in range(len(JOB_NAMES))]+['actions/jobs/90/logs','actions/jobs/91/logs']:
            prefix=('2026-10-20T12:00:00Z '+SOURCE+'\n').encode()
            return prefix+(b'\n'.join(b'MXM_CAS_RESULT '+encoded(x) for x in self.cas_writers)
                           if path=='actions/jobs/106/logs' else b'')
        raise KeyError(path)
    def json(self,path):
        if path.startswith('rules/branches/'):
            branch=path[len('rules/branches/'):]
            rules=[{'type':'deletion'},{'type':'non_fast_forward'}]
            if branch in ('main',EXEC):
                return rules+[{'type':'pull_request'},{'type':'required_status_checks','parameters':{'required_status_checks':[{'context':'shared-catalogue-regression'}]}}]
            return rules+[{'type':'update','ruleset_id':1 if branch==CODE else 2}]
        if path in ('rulesets/1','rulesets/2'):
            return {'enforcement':'active','bypass_actors':[] if path=='rulesets/1' else [{'actor_id':5343530,'actor_type':'Integration','bypass_mode':'always'}]}
        if path=='git/commits/'+'7'*40:
            return {'sha':'7'*40,'parents':[{'sha':'6'*40}]}
        if path.startswith('contents/') and '?ref=' in path:
            import base64
            file_path,ref=path[len('contents/'):].split('?ref=',1)
            value=self.storage[(file_path,ref)]
            return {'encoding':'base64','size':len(value),
                    'content':base64.b64encode(value).decode('ascii')}
        if path=='branches/'+CODE or path=='branches/'+BRANCH:
            return {'protected':True}
        if path=='git/ref/heads/'+BRANCH:
            return {'object':{'sha':self.current_head}}
        if path=='compare/'+HEAD+'...'+self.current_head:
            return ({'status':'diverged','ahead_by':2,'behind_by':1,
                     'base_commit':{'sha':'9'*40}} if self.divergent else
                    {'status':'ahead','ahead_by':1,'behind_by':0,
                     'base_commit':{'sha':HEAD}})
        if path=='compare/'+CHECKPOINT+'...'+'6'*40:
            return {'status':'diverged','ahead_by':1,'behind_by':1,
                    'base_commit':{'sha':'9'*40}} if self.divergent_ack else {
                    'status':'ahead','ahead_by':1,'behind_by':0,
                    'base_commit':{'sha':CHECKPOINT}}
        if path=='actions/runs/'+str(RUN):
            return {'id':RUN,'status':'completed' if self.run_ok else 'in_progress',
                    'conclusion':'success' if self.run_ok else None,
                    'path':'.github/workflows/mxm-integrated-p0.yml',
                    'head_branch':EXEC,'run_attempt':1,'head_sha':'9'*40}
        if path=='actions/runs/'+str(HISTORIC):
            return {'id':HISTORIC,'path':'.github/workflows/mxm-integrated-p0.yml',
                    'status':'completed','head_branch':EXEC,'head_sha':'8'*40,'run_attempt':1,'conclusion':'failure'}
        if path=='actions/runs/'+str(RUN)+'/attempts/1/jobs?per_page=100':
            jobs=[{'id':100+i,'run_id':RUN,'name':name,'status':'completed',
                   'conclusion':'failure' if name==self.missing_job else 'success',
                   'steps':[{'name':'Checkout sealed source','number':2,'status':'completed','conclusion':'success'}]}
                  for i,name in enumerate(JOB_NAMES)]
            return {'jobs':jobs,'total_count':len(jobs)}
        if path=='actions/runs/'+str(HISTORIC)+'/attempts/1/jobs?per_page=100':
            states=('failure','skipped','skipped')
            return {'jobs':[{'id':90,'name':'preflight','status':'completed','conclusion':'success',
                 'steps':[{'name':'Checkout sealed source','number':2,'status':'completed','conclusion':'success'}]}]+
                 [{'id':91+i,'name':name,'status':'completed','conclusion':states[i],
                   'steps':[{'name':'Checkout sealed source','number':2,'status':'completed','conclusion':'success'}]}
                            for i,name in enumerate(NEG_NAMES)]}
        raise KeyError(path)

def make_fixture():
    state={'source_sha':SOURCE,'sequence':21,'last_run_id':RUN,'last_trigger_sha':'9'*40,
           'ciphertext_sha256':'c'*64,'accounting':{
                'lanes':{'V2':{'outcome_charged':21,'reservation_holds':1,
                                'encumbered':22,'limit':84}},
                'refunds':0,'economic_observations':29},
           'orders':0,'pending':None,'safe_stop':True,
           'original_public_sha256':ORIGINAL_PUBLIC}
    cold={'schema':'mxm.integrated-cold-readback.v3',
          'source_sha':SOURCE,'run_id':RUN,'evidence_oid':CHECKPOINT,
          'sequence':21,'ciphertext_sha256':'c'*64,
          'private_sha256':'d'*64,'accounting':state['accounting'],
          'shared_catalogue_sha256':'e'*64,
          'shared_catalogue_quarantine_sha256':'f'*64,
          'programme_execution_history_sha256':'1'*64,
          'programme_checkpoints':[
             {'id':x,'checkpoint_sha256':'2'*64,
              'progress_sha256':'7'*64,'catalogue_sha256':'8'*64,
              'acquisition_budget_sha256':'9'*64,
              'native_receipts_sha256':'0'*64,
              'acquisition_remaining':0,
              'steps_used':1,'safe_stop':True} for x in ('A','B')],
          'multi_program_A_B_A_verified':True,
          'budgets_and_quarantine_verified':True,
          'all_admitted_programmes_complete':True,
          'authentic_nonoutcome_results':[{
            'programme':'B','task':'quote','result_sha256':'3'*64,
            'asset_ids':['4'*64],'preserved_corpus_sha256':'5'*64,
            'verified_quote_rows':2}],
          'original_unchanged':True,
          'economic_workflow_released':False,'orders':0,'new_outcomes':0}
    adapter=native_adapter_attestation(cold)
    neg={'schema':'mxm.e2e.native-negatives.v3',
         'run_id':RUN,'source_sha':SOURCE,'sequence':21,
         'ciphertext_sha256':'c'*64,'checkpoint_parent_oid':CHECKPOINT,
         'ack_commit_oid':'6'*40,'ack_path':'typed-successor/fault-probes/'
                    +str(RUN)+'/ack.json',
         'ack_sha256':None,
         'concurrent_writers':[{'writer':'A','accepted':True,'oid':'7'*40,'expected_oid':'6'*40},
                               {'writer':'B','accepted':False,'expected_oid':'6'*40,
                                'candidate_oid':'8'*40,'observed_oid':'7'*40,'reason':'NATIVE_GIT_STALE_INFO'}],
         'cas_base_oid':'6'*40,'cas_final_oid':'7'*40,
         'pre_fence_native_run_id':HISTORIC,
         'pre_fence_recovery_path':'typed-successor/recoveries/'
                       +str(HISTORIC)+'.json',
         'unauthorized_get_http_code':401,
         'incomplete_checkpoint_rejected':True,
         'missing_private_key_refused':True,
         'original_public_sha256':ORIGINAL_PUBLIC,
         'original_unchanged':True,'orders':0,'new_outcomes':0}
    ack={'native_run_id':RUN,'checkpoint_cipher_sha256':'c'*64,
         'orders':0,'new_outcomes':0}
    neg['ack_sha256']=digest(ack)
    receipt={'schema':'mxm.integrated-segment-receipt.v2','trigger_sha':'9'*40,
             'run_id':RUN,'source_sha':SOURCE,'sequence':21,
             'ciphertext_sha256':'c'*64,'accounting_after':state['accounting'],
             'pending':None,'safe_stop':True,'orders':0,'new_outcomes':0,
             'new_economic_identities_opened':0,'new_identity_reservations':0,
             'broker_requests':0,'native_wire_counts':{},
             'economic_release':False}
    route=ArtificialRoute();paths=proof_paths(RUN)
    route.storage[('.github/workflows/mxm-integrated-p0.yml','9'*40)]=encoded({
        'env':{'LAB_SOURCE_SHA':SOURCE,'LAB_INTEGRATED_PROTOCOL':'v2'},'jobs':{
            name:{'steps':[{'name':'Checkout sealed source',
                'uses':'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',
                'with':{'ref':SOURCE,'persist-credentials':False}}]} for name in JOB_NAMES}})
    route.storage[('.github/workflows/mxm-integrated-p0.yml','8'*40)]=route.storage[('.github/workflows/mxm-integrated-p0.yml','9'*40)]
    route.cas_writers=deepcopy(neg['concurrent_writers'])
    for oid in ('6'*40,'7'*40):
        route.storage[('typed-successor/program-state.json',oid)]=encoded(state)
    route.storage[('typed-successor/fault-probes/'+str(RUN)+'/A.json','7'*40)]=encoded({'probe':'A','not_economic':True})
    route.storage[('typed-successor/program-state.json',HEAD)]=encoded(state)
    route.storage[('typed-successor/program-state.json',CHECKPOINT)]=encoded(state)
    route.storage[(neg['ack_path'],neg['ack_commit_oid'])]=encoded(ack)
    route.storage[(neg['pre_fence_recovery_path'],CHECKPOINT)]=encoded({
         'run_id':HISTORIC,'no_economic_exposure':True,'refunds':0})
    issuer=build_issuer(route,RUN,SOURCE,CHECKPOINT,cold,adapter,neg,state)
    for path,obj in [(paths['cold'],cold),(paths['adapter'],adapter),
                     (paths['negative'],neg),(paths['issuer'],issuer),
                     ('typed-successor/segments/21/receipt.json',receipt)]:
        route.storage[(path,HEAD)]=encoded(obj)
    gate={'schema':'mxm.e2e.native-acceptance.v3',
          'status':'END_TO_END_OPERATIONAL_ACCEPTED',
          'source_sha':SOURCE,'evidence_branch':BRANCH,'evidence_oid':HEAD,
          'sequence':21,'run_id':RUN,'checkpoint_cipher_sha256':'c'*64,
          'native_receipt_path':'typed-successor/segments/21/receipt.json',
          'issuer_path':paths['issuer'],'cold_proof_path':paths['cold'],
          'negative_proof_path':paths['negative'],
          'authentic_adapter_path':paths['adapter']}
    return route,gate,paths

class IndependentNativeV3ContractTests(unittest.TestCase):
    def verify(self,route,gate):
        def file_at(_route,path,oid):
            return route.storage[(path,oid)]
        with patch('research_core_v4.laboratory.runtime.file_at',new=file_at):
            return verify_operational_acceptance(
                route,gate,SOURCE,{'main':route.main_protected,EXEC:True})
    def test_fully_linked_artificial_protocol_fixture(self):
        route,gate,_=make_fixture()
        self.assertEqual(self.verify(route,gate)['run_id'],RUN)
    def test_bare_favorable_json_is_rejected(self):
        route,gate,_=make_fixture()
        with self.assertRaises(Exception):
            self.verify(route,{'status':'END_TO_END_OPERATIONAL_ACCEPTED',
                               'source_sha':SOURCE})
    def test_unprotected_control_plane_and_incomplete_native_run_rejected(self):
        for change in ('main_protected','run_ok'):
            route,gate,_=make_fixture()
            setattr(route,change,False)
            with self.subTest(change=change),self.assertRaises(Exception):
                self.verify(route,gate)
    def test_skipped_or_failed_native_job_is_not_acceptance(self):
        for name in JOB_NAMES:
            route,gate,_=make_fixture()
            route.missing_job=name
            with self.subTest(name=name),self.assertRaises(Exception):
                self.verify(route,gate)
    def test_tampered_or_missing_v3_proof_rejected(self):
        for part in ('cold','negative','adapter','issuer'):
            route,gate,paths=make_fixture()
            key=(paths[part],HEAD)
            route.storage.pop(key)
            with self.subTest(part=part),self.assertRaises(Exception):
                self.verify(route,gate)
    def test_fake_boolean_positive_cannot_replace_native_history(self):
        route,gate,paths=make_fixture()
        proof=deepcopy(__import__('json').loads(
            route.storage[(paths['negative'],HEAD)]))
        proof['pre_fence_native_run_id']=10
        route.storage[(paths['negative'],HEAD)]=encoded(proof)
        with self.assertRaises(Exception):self.verify(route,gate)
    def test_ack_native_proof_from_divergent_git_history_rejected(self):
        route,gate,_=make_fixture()
        route.divergent_ack=True
        with self.assertRaises(Exception):self.verify(route,gate)
    def test_missing_programme_budget_or_receipt_hash_rejected(self):
        for key in ('acquisition_budget_sha256','native_receipts_sha256'):
            route,gate,paths=make_fixture()
            proof=__import__('json').loads(route.storage[(paths['cold'],HEAD)])
            proof['programme_checkpoints'][0].pop(key)
            route.storage[(paths['cold'],HEAD)]=encoded(proof)
            with self.subTest(key=key),self.assertRaises(Exception):
                self.verify(route,gate)
    def test_cold_schema_v2_rejected_even_with_native_jobs(self):
        route,gate,paths=make_fixture()
        proof=__import__('json').loads(route.storage[(paths['cold'],HEAD)])
        proof['schema']='mxm.integrated-cold-readback.v2'
        route.storage[(paths['cold'],HEAD)]=encoded(proof)
        with self.assertRaises(Exception):self.verify(route,gate)
    def test_missing_aba_or_authentic_proof_must_hold(self):
        for part,value in (('multi_program_A_B_A_verified',False),
                            ('authentic_nonoutcome_results',[])):
            route,gate,paths=make_fixture()
            proof=__import__('json').loads(route.storage[(paths['cold'],HEAD)])
            proof[part]=value
            route.storage[(paths['cold'],HEAD)]=encoded(proof)
            with self.subTest(part=part),self.assertRaises(Exception):
                self.verify(route,gate)
    def test_exact_cipher_or_accounting_change_rejected(self):
        for part,value in (('ciphertext_sha256','0'*64),
                           ('sequence',22),('orders',1)):
            route,gate,_=make_fixture();gate[part]=value
            with self.subTest(part=part),self.assertRaises(Exception):
                self.verify(route,gate)
    def test_certificate_proof_ancestor_survives_native_append_only(self):
        route,gate,_=make_fixture()
        route.current_head='c'*40
        self.assertEqual(self.verify(route,gate)['run_id'],RUN)
        route.divergent=True
        with self.assertRaises(Exception):self.verify(route,gate)
    def test_certifier_denies_missing_protected_main_or_failed_run(self):
        from .certify_v3 import eligible_certificate
        route,gate,_=make_fixture()
        # The mock branch has valid proof but no operator authority if either
        # official control-plane protection is missing.
        with patch('research_core_v4.laboratory.runtime.file_at',
                   side_effect=lambda _,path,oid:route.storage[(path,oid)]):
            with patch('research_core_v4.laboratory.certify_v3.verify_operational_acceptance',
                       side_effect=RuntimeError('CONTROL_PLANE_NOT_PROTECTED')):
                with self.assertRaises(Exception):
                    eligible_certificate(route,RUN,SOURCE)
        route.run_ok=False
        with self.assertRaises(Exception):eligible_certificate(route,RUN,SOURCE)
    def test_cross_run_job_or_seal_binding_rejected(self):
        route,gate,paths=make_fixture()
        issuer=__import__('json').loads(route.storage[(paths['issuer'],HEAD)])
        issuer['job_ids']['cold-readback']=999
        route.storage[(paths['issuer'],HEAD)]=encoded(issuer)
        with self.assertRaises(Exception):self.verify(route,gate)

if __name__=='__main__':unittest.main()
