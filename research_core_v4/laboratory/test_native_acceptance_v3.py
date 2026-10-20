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
    def json(self,path):
        if path.startswith('contents/') and '?ref=' in path:
            import base64
            file_path,ref=path[len('contents/'):].split('?ref=',1)
            value=self.storage[(file_path,ref)]
            return {'encoding':'base64','size':len(value),
                    'content':base64.b64encode(value).decode('ascii')}
        if path=='branches/'+CODE or path=='branches/'+BRANCH:
            return {'protected':True}
        if path=='git/ref/heads/'+BRANCH:
            return {'object':{'sha':HEAD}}
        if path=='actions/runs/'+str(RUN):
            return {'id':RUN,'status':'completed' if self.run_ok else 'in_progress',
                    'conclusion':'success' if self.run_ok else None,
                    'path':'.github/workflows/mxm-integrated-p0.yml',
                    'head_branch':EXEC,'run_attempt':1}
        if path=='actions/runs/'+str(HISTORIC):
            return {'id':HISTORIC,'path':'.github/workflows/mxm-integrated-p0.yml',
                    'conclusion':'failure'}
        if path=='actions/runs/'+str(RUN)+'/attempts/1/jobs?per_page=100':
            jobs=[{'id':100+i,'run_id':RUN,'name':name,'status':'completed',
                   'conclusion':'failure' if name==self.missing_job else 'success'}
                  for i,name in enumerate(JOB_NAMES)]
            return {'jobs':jobs,'total_count':len(jobs)}
        if path=='actions/runs/'+str(HISTORIC)+'/attempts/1/jobs?per_page=100':
            states=('failure','skipped','skipped')
            return {'jobs':[{'name':name,'status':'completed','conclusion':states[i]}
                            for i,name in enumerate(NEG_NAMES)]}
        raise KeyError(path)

def make_fixture():
    state={'source_sha':SOURCE,'sequence':21,'last_run_id':RUN,
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
         'concurrent_writers':[{'writer':'A','accepted':True,'oid':'7'*40},
                               {'writer':'B','accepted':False}],
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
    receipt={'schema':'mxm.integrated-segment-receipt.v2',
             'run_id':RUN,'source_sha':SOURCE,'sequence':21,
             'ciphertext_sha256':'c'*64,'accounting_after':state['accounting'],
             'pending':None,'safe_stop':True,'orders':0,'new_outcomes':0,
             'new_economic_identities_opened':0,'new_identity_reservations':0,
             'broker_requests':0,'native_wire_counts':{},
             'economic_release':False}
    route=ArtificialRoute();paths=proof_paths(RUN)
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
    def test_cross_run_job_or_seal_binding_rejected(self):
        route,gate,paths=make_fixture()
        issuer=__import__('json').loads(route.storage[(paths['issuer'],HEAD)])
        issuer['job_ids']['cold-readback']=999
        route.storage[(paths['issuer'],HEAD)]=encoded(issuer)
        with self.assertRaises(Exception):self.verify(route,gate)

if __name__=='__main__':unittest.main()
