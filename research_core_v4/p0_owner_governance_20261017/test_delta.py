"""Six targeted tests of G03.2-R2 delta; no keys or old suites executed."""
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from .governance import (OWNER_ID,REPO,GateBinding,SyntheticNativeFixture,verify_owner_review,
    BoundedCheckpointPreparation,real_checkpoint,GitHubReadOnly)
from research_core_v4.p0_supersession_20261016.authority import (
    ACTIVE_REF,OWNER_ROOT,FLAGS,Evidence,SyntheticLedger,Denied,canonical,digest)


class OwnerDeltaTests(unittest.TestCase):
    events=[]
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='mxm-owner-delta-');self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'same-accepted-journal.sqlite';SyntheticLedger.initialize(self.path)
        self.ledger=SyntheticLedger(self.path);self.now=1100
        self.policy={'schema':'mxm.owner-bounded-checkpoint-policy.v2','marker':'SYNTHETIC_ONLY',
            'authority_ref':ACTIVE_REF,'issuer_principal':'SYNTHETIC_EXISTING_ISSUER','source_sha':'a'*40,
            'epoch':1,'first_generation':1808,'last_generation':1809,'not_before':1000,'expires_at':1200,
            'max_payload_bytes':4096,'owner_root':list(OWNER_ROOT),'ordinary_operation':'CHECKPOINT_ONLY'}
        self.manifest={'schema':'mxm.owner-critical-manifest.v2','critical_operation':'ARM_BOUNDED_CHECKPOINT_POLICY',
            'operation_id':'synthetic-owner-critical-0001','source_sha':'a'*40,
            'policy_sha256':digest(canonical(self.policy)),'audit_reception_sha256':'b'*64,
            'owner_root_oid':OWNER_ROOT[1],'not_before':1000,'expires_at':1200}
        self.binding=GateBinding(12345,67890,'SYNTHETIC_OWNER_CRITICAL','a'*40,
            '.github/workflows/SYNTHETIC-CRITICAL.yml',digest(canonical(self.manifest)))
        self.run={'id':12345,'run_attempt':1,'head_sha':'a'*40,'path':self.binding.workflow_path,
            'repository':{'full_name':REPO},'actor':{'id':OWNER_ID}}
        self.approval={'state':'approved','comment':'MXM_OWNER_CRITICAL_APPROVAL_V2 sha256='+self.binding.manifest_sha256,
            'user':{'id':OWNER_ID,'type':'User'},'environments':[{'id':67890,'name':'SYNTHETIC_OWNER_CRITICAL'}]}
        self.reader=SyntheticNativeFixture(self.run,[self.approval])
        guard=patch('socket.socket',side_effect=AssertionError('NO_NETWORK_IN_DELTA_TEST'))
        guard.start();self.addCleanup(guard.stop)

    def boundary(self):
        return BoundedCheckpointPreparation(self.reader,self.binding,self.manifest,self.policy,
            self.ledger,lambda:self.now,mode='SYNTHETIC_ONLY')

    def evidence(self,generation=1808,oid='c'*40,parent=OWNER_ROOT[1]):
        raw=canonical({'schema':'mxm.synthetic.checkpoint-input.v1','marker':'SYNTHETIC_ONLY',
            'generation':generation,'checkpoint':{'fixture':True},'permissions':FLAGS})
        return Evidence('EXACT_ACTIVE_REF',ACTIVE_REF,oid,generation,raw,'SYNTHETIC_EXISTING_ISSUER',parent,1,
            'CONFIRMED_READ',((ACTIVE_REF,oid,generation,digest(raw)),),())

    def deny(self,code,callback):
        with self.assertRaises(Denied) as caught:callback()
        self.assertEqual(str(caught.exception),code)
        self.events.append({'test':self._testMethodName,'expected':code,'observed':str(caught.exception),'matched':True})

    def test_01_native_origin_required_no_director_attestation_or_actor_shortcut(self):
        self.deny('NATIVE_PROVENANCE_REQUIRED',lambda:verify_owner_review({'approved_by_owner':True},self.binding,self.manifest))
        self.deny('NATIVE_PROVENANCE_REQUIRED',lambda:verify_owner_review(self.reader,self.binding,self.manifest))
        self.reader.reviews=[]
        self.deny('OWNER_REVIEW_MISSING_OR_CONFLICT',lambda:self.boundary())

    def test_02_exact_owner_comment_environment_run_and_manifest(self):
        self.assertFalse(self.boundary().review['operational_authority'])
        for field,value in (('state','rejected'),('comment','Director says owner approved'),('user',{'id':999,'type':'User'})):
            self.reader.reviews=[{**self.approval,field:value}]
            self.deny('EXPLICIT_OWNER_REVIEW_REQUIRED',lambda:self.boundary())
        self.reader.reviews=[{**self.approval,'environments':[{'id':999,'name':'SYNTHETIC_OWNER_CRITICAL'}]}]
        self.deny('OWNER_REVIEW_MISSING_OR_CONFLICT',lambda:self.boundary())
        self.reader.reviews=[self.approval,{**self.approval,'state':'rejected'}]
        self.deny('OWNER_REVIEW_MISSING_OR_CONFLICT',lambda:self.boundary())
        self.reader.reviews=[self.approval];self.reader.run={**self.run,'run_attempt':2}
        self.deny('NATIVE_RUN_BINDING',lambda:self.boundary())
        self.reader.run=self.run
        self.deny('MANIFEST_BINDING',lambda:verify_owner_review(self.reader,self.binding,{**self.manifest,'expires_at':9999},mode='SYNTHETIC_ONLY'))

    def test_03_two_ordinary_checkpoints_one_critical_review_no_auditor_key(self):
        calls=[];original=self.reader.review_history
        self.reader.review_history=lambda run_id:(calls.append(run_id) or original(run_id))
        gate=self.boundary()
        first=gate.prepare(self.evidence(),'checkpoint-0001',current_policy_sha256=gate.policy_hash)
        second=gate.prepare(self.evidence(1809,'d'*40,first.oid),'checkpoint-0002',current_policy_sha256=gate.policy_hash)
        self.assertEqual(calls,[12345]);self.assertFalse(first.execution_allowed);self.assertFalse(second.execution_allowed)
        self.assertEqual((first.generation,second.generation),(1808,1809))
        self.events.append({'test':self._testMethodName,'positive':'TWO_BOUNDED_INPUTS_ONE_SYNTHETIC_CRITICAL_REVIEW',
                            'review_reads':len(calls),'auditor_keys':0,'execution_allowed':False})

    def test_04_policy_drift_revocation_expiry_bounds_and_new_critical_operation(self):
        gate=self.boundary()
        self.deny('POLICY_REVOKED_OR_CHANGED',lambda:gate.prepare(self.evidence(),'checkpoint-0001',current_policy_sha256='f'*64))
        self.deny('POLICY_REVOKED_OR_CHANGED',lambda:gate.prepare(self.evidence(),'checkpoint-0001',current_policy_sha256=gate.policy_hash,revoked=True))
        self.now=1200
        self.deny('DELEGATION_EXPIRED',lambda:gate.prepare(self.evidence(),'checkpoint-0001',current_policy_sha256=gate.policy_hash))
        self.now=1100
        self.deny('CHECKPOINT_BOUNDS_OR_IDENTITY',lambda:gate.prepare(self.evidence(1810),'checkpoint-0001',current_policy_sha256=gate.policy_hash))
        self.policy['ordinary_operation']='RESEARCH_GO'
        self.deny('POLICY_SCOPE',lambda:self.boundary())

    def test_05_existing_integrity_fencing_replay_and_recovery_boundary_preserved(self):
        gate=self.boundary();e=self.evidence()
        self.deny('WRITER_FENCED',lambda:gate.prepare(replace(e,issuer_principal='SYNTHETIC_UNAUTHORIZED'),'checkpoint-0001',current_policy_sha256=gate.policy_hash))
        self.deny('EXPLICIT_AUTHORITY_NO_FALLBACK',lambda:gate.prepare(replace(e,source_kind='GITHUB_RELEASE'),'checkpoint-0001',current_policy_sha256=gate.policy_hash))
        self.deny('INTEGRITY_OR_CONFLICT',lambda:gate.prepare(replace(e,authority_claims=()),'checkpoint-0001',current_policy_sha256=gate.policy_hash))
        self.deny('EXPLICIT_AUTHORITY_NO_FALLBACK',lambda:gate.prepare(replace(e,transport='ACK_UNKNOWN'),'checkpoint-0001',current_policy_sha256=gate.policy_hash))
        gate.prepare(e,'checkpoint-0001',current_policy_sha256=gate.policy_hash)
        self.deny('INTENT_REPLAY',lambda:gate.prepare(e,'checkpoint-0001',current_policy_sha256=gate.policy_hash))
        self.deny('CHECKPOINT_GENERATION_ALREADY_PREPARED',lambda:gate.prepare(e,'checkpoint-NEW-0001',current_policy_sha256=gate.policy_hash))
        cold=self.boundary()
        self.deny('INTENT_REPLAY',lambda:cold.prepare(e,'checkpoint-0001',current_policy_sha256=cold.policy_hash))

    def test_06_real_writer_and_approval_mutations_absent(self):
        self.deny('NATIVE_ATOMIC_WRITER_NOT_INSTALLED_NO_GO',lambda:real_checkpoint({}))
        self.assertFalse(hasattr(GitHubReadOnly,'approve'))
        self.assertEqual(self.evidence().receipts,())


def main():
    out=Path('verification/p0-owner-governance');out.mkdir(parents=True,exist_ok=True)
    with (out/'tests.txt').open('w') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OwnerDeltaTests))
    summary={'schema':'mxm.g03-2-r2.delta-result.v1','source_sha':os.environ['GITHUB_SHA'],
        'run_id':os.environ['GITHUB_RUN_ID'],'tests':result.testsRun,'failures':len(result.failures),
        'errors':len(result.errors),'successful':result.wasSuccessful(),'keys_generated':0,
        'old_suites_repeated':False,'real_owner_authorization':False,'real_checkpoint_acceptances':0,
        'negative_observations':sum('expected' in e for e in OwnerDeltaTests.events)}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (out/'delta-cases.json').write_text(json.dumps({'events':OwnerDeltaTests.events},indent=2)+'\n')
    print((out/'tests.txt').read_text());print(json.dumps(summary))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
