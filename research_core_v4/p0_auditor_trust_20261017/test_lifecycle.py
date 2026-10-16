"""Only new enrollment/lifecycle public-verification tests, synthetic keys only."""
import base64
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from .public_verifier import (REPO,ROOT_OID,EXCLUDED,PREFIX,Denied,EnrollmentPin,TrustedHead,
    PublicTrustVerifier,verify_real_receipt,canonical,parse,sha)


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='SYNTHETIC-auditor-keys-')
        cls.keys=[];cls.public=[];cls.events=[]
        for i in range(3):
            path=Path(cls.tmp.name)/str(i)
            subprocess.run(['openssl','genpkey','-algorithm','Ed25519','-out',str(path)],
                check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
            path.chmod(0o600);cls.keys.append(path)
            der=subprocess.run(['openssl','pkey','-in',str(path),'-pubout','-outform','DER'],
                check=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=10).stdout
            cls.public.append(der)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def setUp(self):
        guard=patch('socket.socket',side_effect=AssertionError('NO_TEST_NETWORK'))
        guard.start();self.addCleanup(guard.stop)
        self.now=1200;self.challenge='c'*64
        self.context={'source_sha':'a'*40,'evidence_sha256':'b'*64,'policy_sha256':'d'*64,
                      'owner_root_oid':ROOT_OID,'operation_id':'synthetic-preparation-0001'}

    def key(self,i):
        return {'key_id':'SYNTHETIC_AUDITOR_KEY_'+str(i),'algorithm':'Ed25519',
                'spki_der_b64':base64.b64encode(self.public[i]).decode(),'spki_sha256':sha(self.public[i]),
                'not_before':900 if i==0 else 1100,'expires_at':2000+i*1000}

    def sign(self,body,i):
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-message-') as folder:
            path=Path(folder)/'message';path.write_bytes(PREFIX+canonical(body))
            sig=subprocess.run(['openssl','pkeyutl','-sign','-rawin','-inkey',str(self.keys[i]),'-in',str(path)],
                check=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=10).stdout
        return base64.b64encode(sig).decode()

    def fixture(self):
        body={'schema':'mxm.synthetic.auditor-enrollment.v1','marker':'SYNTHETIC_ONLY','repository':REPO,
            'repository_id':1374181010,'subject_id':'SYNTHETIC_INDEPENDENT_AUDITOR',
            'custody_id':'SYNTHETIC_OFFLINE_CUSTODIAN','independent_from':EXCLUDED.copy(),
            'owner_root_oid':ROOT_OID,'scope':'PREPARATION_RECEPTION_ONLY',
            'enrollment_nonce':'synthetic-owner-challenge-0001','enrolled_at':1000,'key':self.key(0)}
        genesis={'body':body,'proof_of_possession':self.sign(body,0)}
        pin=EnrollmentPin(sha(canonical(body)),body['subject_id'],body['custody_id'],body['key']['spki_sha256'])
        verifier=PublicTrustVerifier(pin,mode='SYNTHETIC_ONLY')
        head=TrustedHead(0,pin.genesis_sha256,1190,1250)
        return verifier,genesis,head

    def event(self,head,kind='ROTATE',old=0,new=1,**changes):
        body={'schema':'mxm.synthetic.auditor-lifecycle.v1','marker':'SYNTHETIC_ONLY','repository':REPO,
            'subject_id':'SYNTHETIC_INDEPENDENT_AUDITOR','custody_id':'SYNTHETIC_OFFLINE_CUSTODIAN',
            'sequence':head.sequence+1,'previous_sha256':head.head_sha256,'kind':kind,
            'issued_at':1100,'new_key':self.key(new) if kind=='ROTATE' else None,
            'reason':'synthetic routine rotation' if kind=='ROTATE' else 'synthetic revocation'}
        body.update(changes)
        event={'body':body,'old_signature':self.sign(body,old),
               'new_signature':self.sign(body,new) if kind=='ROTATE' else None}
        return event,TrustedHead(body['sequence'],sha(canonical(body)),1190,1250)

    def receipt(self,head,i=0,**changes):
        body={'schema':'mxm.synthetic.auditor-reception.v1','marker':'SYNTHETIC_ONLY','repository':REPO,
            'subject_id':'SYNTHETIC_INDEPENDENT_AUDITOR','custody_id':'SYNTHETIC_OFFLINE_CUSTODIAN',
            'key_id':self.key(i)['key_id'],'registry_sequence':head.sequence,'registry_head_sha256':head.head_sha256,
            'challenge':self.challenge,'issued_at':1190,'expires_at':1250,'scope':'PREPARATION_RECEPTION_ONLY',
            'verdict':'ACCEPT_PREPARATION_ONLY','context':copy.deepcopy(self.context),'execution_allowed':False}
        body.update(changes)
        return {'body':body,'signature':self.sign(body,i)}

    def deny(self,code,action):
        with self.assertRaises(Denied) as caught:action()
        self.assertEqual(str(caught.exception),code)
        self.events.append({'test':self._testMethodName,'kind':'NEGATIVE','expected':code,
                            'observed':str(caught.exception),'matched':True})

    def check(self,v,g,h,r,events=None):
        return v.receipt(g,events or [],h,r,self.context,self.challenge,self.now)

    def test_01_pinned_identity_and_proof_of_possession(self):
        v,g,h=self.fixture();r=self.receipt(h)
        result=self.check(v,g,h,r)
        self.assertTrue(result['signature_valid']);self.assertFalse(result['execution_allowed'])
        self.assertFalse(result['receipt_consumed'])
        self.events.append({'test':self._testMethodName,'kind':'POSITIVE_PUBLIC_VERIFICATION',
                            'genesis':g,'receipt':r,'result':result,
                            'pin':v.pin.__dict__,'trusted_head':h.__dict__})
        bad=copy.deepcopy(g);bad['proof_of_possession']=self.sign(g['body'],2)
        self.deny('SIGNATURE_INVALID',lambda:self.check(v,bad,h,r))

    def test_02_self_asserted_key_is_not_enrollment(self):
        v,g,h=self.fixture();bad=copy.deepcopy(g)
        bad['body']['key']=self.key(2);bad['proof_of_possession']=self.sign(bad['body'],2)
        self.deny('GENESIS_PIN_MISMATCH',lambda:v.chain(bad,[],h,self.now))
        self.deny('REAL_AUDITOR_NOT_ENROLLED',lambda:PublicTrustVerifier(v.pin))

    def test_03_identity_custody_or_exclusion_tamper(self):
        v,g,h=self.fixture()
        for field,value in (('subject_id','SYNTHETIC_DIRECTOR'),('custody_id','GITHUB_ACTIONS'),('independent_from',[])):
            bad=copy.deepcopy(g);bad['body'][field]=value;bad['proof_of_possession']=self.sign(bad['body'],0)
            self.deny('GENESIS_PIN_MISMATCH',lambda:v.chain(bad,[],h,self.now))

    def test_04_cross_signed_rotation_and_new_key_receipt(self):
        v,g,h=self.fixture();event,newhead=self.event(h);r=self.receipt(newhead,1)
        result=self.check(v,g,newhead,r,[event]);self.assertTrue(result['signature_valid'])
        self.events.append({'test':self._testMethodName,'kind':'POSITIVE_ROTATION','event':event,
                            'receipt':r,'trusted_head':newhead.__dict__,'result':result})
        self.deny('RECEIPT_IDENTITY',lambda:self.check(v,g,newhead,self.receipt(newhead,0),[event]))

    def test_05_rotation_needs_old_and_new_key_signatures(self):
        v,g,h=self.fixture();event,newhead=self.event(h)
        for field in ('old_signature','new_signature'):
            bad=copy.deepcopy(event);bad[field]=self.sign(event['body'],2)
            self.deny('SIGNATURE_INVALID',lambda:v.chain(g,[bad],newhead,self.now))
        reused,newhead=self.event(h,new=0)
        self.deny('ROTATION_KEY_REUSE_OR_TIME',lambda:v.chain(g,[reused],newhead,self.now))

    def test_06_chain_replay_fork_and_identity_change(self):
        v,g,h=self.fixture();event,newhead=self.event(h)
        self.deny('EVENT_ROLLBACK_REPLAY_OR_FORK',lambda:v.chain(g,[event,event],newhead,self.now))
        fork,forkhead=self.event(h,previous_sha256='f'*64)
        self.deny('EVENT_ROLLBACK_REPLAY_OR_FORK',lambda:v.chain(g,[fork],forkhead,self.now))
        changed,ch=self.event(h,subject_id='SYNTHETIC_REPLACEMENT')
        self.deny('EVENT_IDENTITY_SCOPE',lambda:v.chain(g,[changed],ch,self.now))

    def test_07_revocation_closes_identity_and_no_fallback(self):
        v,g,h=self.fixture();event,revoked=self.event(h,kind='REVOKE')
        self.deny('AUDITOR_REVOKED',lambda:self.check(v,g,revoked,self.receipt(revoked),[event]))
        rotated,rh=self.event(revoked,issued_at=1150)
        self.deny('REVOKED_CHAIN_CLOSED',lambda:v.chain(g,[event,rotated],rh,self.now))
        self.events.append({'test':self._testMethodName,'kind':'SIGNED_REVOCATION','event':event,
                            'trusted_head':revoked.__dict__,'execution_allowed':False})

    def test_08_key_and_receipt_expiry(self):
        v,g,h=self.fixture()
        late=TrustedHead(0,h.head_sha256,1990,2050)
        self.deny('AUDITOR_KEY_EXPIRED',lambda:v.receipt(g,[],late,self.receipt(late),self.context,self.challenge,2000))
        for times in ({'expires_at':1200},{'issued_at':1201},{'expires_at':2001}):
            self.deny('RECEIPT_EXPIRY',lambda:self.check(v,g,h,self.receipt(h,**times)))

    def test_09_independent_highwater_and_freshness_required(self):
        v,g,h=self.fixture();event,newhead=self.event(h)
        self.deny('INDEPENDENT_HEAD_MISMATCH',lambda:v.chain(g,[],newhead,self.now))
        self.deny('INDEPENDENT_HEAD_MISMATCH',lambda:v.chain(g,[event],h,self.now))
        self.deny('INDEPENDENT_HEAD_STALE',lambda:v.chain(g,[],replace(h,expires_at=1200),self.now))
        self.deny('TRUSTED_HEAD_REQUIRED',lambda:v.chain(g,[],h.__dict__,self.now))

    def test_10_reception_context_challenge_scope_and_signature(self):
        v,g,h=self.fixture()
        cases=[({'challenge':'f'*64},'FRESH_CHALLENGE_REQUIRED'),
               ({'context':{**self.context,'source_sha':'f'*40}},'RECEIPT_CONTEXT'),
               ({'scope':'BOOTSTRAP'},'RECEIPT_SCOPE'),({'execution_allowed':True},'RECEIPT_SCOPE')]
        for changes,code in cases:self.deny(code,lambda:self.check(v,g,h,self.receipt(h,**changes)))
        r=self.receipt(h);r['signature']=self.sign(r['body'],2)
        self.deny('SIGNATURE_INVALID',lambda:self.check(v,g,h,r))

    def test_11_domain_and_public_wire_profile(self):
        self.deny('DUPLICATE_KEY',lambda:parse(b'{"a":1,"a":2}'))
        self.deny('JSON_PROFILE',lambda:parse(b'{"a":1.5}'))
        v,g,h=self.fixture();r=self.receipt(h);r['body']['unexpected']=True
        self.deny('FIELDS',lambda:self.check(v,g,h,r))
        self.assertEqual(parse(canonical(self.context)),self.context)

    def test_12_real_enrollment_and_backend_remain_absent(self):
        config=json.loads(Path(__file__).with_name('real.disabled.json').read_text())
        self.assertIs(config['real_backend_enabled'],False)
        self.assertIsNone(config['auditor_identity']);self.assertIsNone(config['public_spki_sha256'])
        self.assertIsNone(config['credential_binding']);self.assertIs(config['owner_decision_received'],False)
        self.deny('REAL_AUDITOR_NOT_ENROLLED_NO_OPERATIONAL_AUTHORITY',lambda:verify_real_receipt({}))


def main():
    out=Path('verification/p0-auditor-trust');out.mkdir(parents=True,exist_ok=True)
    with (out/'tests.txt').open('w') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LifecycleTests))
    events=LifecycleTests.events
    summary={'schema':'mxm.auditor-trust.synthetic-result.v1','source_sha':os.environ['GITHUB_SHA'],
        'run_id':os.environ['GITHUB_RUN_ID'],'attempt':os.environ['GITHUB_RUN_ATTEMPT'],'tests':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'successful':result.wasSuccessful(),
        'negative_observations':sum(e['kind']=='NEGATIVE' for e in events),
        'real_auditor_enrolled':False,'real_private_keys_used':0,'real_backend_enabled':False,
        'identity_or_custody_of_a_real_person_certified':False,'network_in_tests':'DENIED',
        'scope':'NEW_SYNTHETIC_TRUST_LIFECYCLE_ONLY_NOT_37_SUPERSESSION_TESTS'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (out/'cases.json').write_text(json.dumps({'schema':'mxm.auditor-trust.synthetic-cases.v1',
        'identity_scope':'ALL_KEYS_AND_IDENTITY_LABELS_ARE_SYNTHETIC_FIXTURES','events':events},indent=2)+'\n')
    print((out/'tests.txt').read_text());print(json.dumps(summary))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
