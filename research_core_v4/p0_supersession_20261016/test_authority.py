"""New synthetic consumer tests, never historic or previously accepted tests.

Ephemeral fixture keys are generated locally in private temp dirs, never saved
to artifacts. They attest no real OWNER/auditor identity or GitHub permission.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace, asdict
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from .authority import (ACTIVE_REF, OWNER_ROOT, FLAGS, CONSUMERS, ROLES, Policy, TrustRoot,
    ReceiptVerifier, SyntheticLedger, AuthoritySelector, Evidence, ArchivePin, Denied,
    canonical, digest, read_archive, read_owner_archive, real_consumer_input)
from .adapters import ConsumerAdapters


class ConsumerAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = []
        cls.key_temp = tempfile.TemporaryDirectory(prefix='mxm-SYNTHETIC-keys-')
        cls.keys = {}; cls.public = {}
        for role in ROLES:
            key = Path(cls.key_temp.name)/role
            subprocess.run(['openssl','genpkey','-algorithm','Ed25519','-out',str(key)],
                           check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
            key.chmod(0o600);cls.keys[role] = key
            cls.public[role] = subprocess.run(['openssl','pkey','-in',str(key),'-pubout'],
                check=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=10).stdout

    @classmethod
    def tearDownClass(cls):
        cls.key_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mxm-SYNTHETIC-ledger-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'journal.sqlite'
        SyntheticLedger.initialize(self.path)
        self.ledger = SyntheticLedger(self.path)
        self.now = 1100
        self.roots = tuple(TrustRoot(role,'SYNTHETIC_'+role,'SYNTHETIC_KEY_'+role,
                                    self.public[role],1000,2000) for role in ROLES)
        # Only the source GET preparation step can access network. Test process cannot.
        self.network_guard = patch('socket.socket',side_effect=AssertionError('TEST_NETWORK_FORBIDDEN'))
        self.network_guard.start();self.addCleanup(self.network_guard.stop)

    def sign(self, body):
        with tempfile.TemporaryDirectory(prefix='mxm-SYNTHETIC-sign-') as folder:
            message = Path(folder)/'message';message.write_bytes(canonical(body))
            signature = subprocess.run(['openssl','pkeyutl','-sign','-inkey',str(self.keys[body['role']]),
                '-rawin','-in',str(message)],check=True,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,timeout=10).stdout
        return {**body,'signature_b64':base64.b64encode(signature).decode()}

    def receipt(self, role, statement, **changes):
        body = {'schema':'mxm.synthetic.consumer-receipt.v1','role':role,
                'principal':'SYNTHETIC_'+role,'key_id':'SYNTHETIC_KEY_'+role,'algorithm':'Ed25519',
                'nonce':role.lower().replace('_','-')+'-'+statement['intent'],
                'not_before':1050,'expires_at':1250,'statement':statement}
        body.update(changes)
        return self.sign(body)

    def fixture(self, consumer='restore', intent='intent-fixture-0001', *, policy_changes=None,
                payload=None, roots=None, ledger=None):
        generation = (policy_changes or {}).get('generation',1808)
        payload = payload if payload is not None else canonical({
            'schema':'mxm.synthetic.checkpoint-input.v1','marker':'SYNTHETIC_ONLY',
            'generation':generation,'checkpoint':{'current_journal':{'id':'SYNTHETIC_ASSET_ONLY'},
                                                'pending_requests':[]},'permissions':FLAGS.copy()})
        values = dict(candidate_oid='a'*40,generation=generation,payload_sha256=digest(payload),
                      predecessor_oid=OWNER_ROOT[1],issuer_principal='SYNTHETIC_ISSUER_V1',
                      source_sha='b'*40,policy_sha256='c'*64)
        values.update(policy_changes or {})
        policy = Policy(**values)
        selector = AuthoritySelector(policy,ReceiptVerifier(roots or self.roots),ledger or self.ledger,
                                     lambda:self.now,mode='SYNTHETIC_ONLY')
        statement = selector.statement(consumer,intent)
        receipts = tuple(self.receipt(role,statement) for role in ROLES)
        evidence = Evidence('EXACT_ACTIVE_REF',ACTIVE_REF,policy.candidate_oid,policy.generation,
            payload,policy.issuer_principal,policy.predecessor_oid,policy.epoch,'CONFIRMED_READ',
            ((ACTIVE_REF,policy.candidate_oid,policy.generation,policy.payload_sha256),),receipts)
        return selector,evidence

    def denied(self, code, action):
        with self.assertRaises(Denied) as found:
            action()
        self.assertEqual(str(found.exception),code)
        self.events.append({'test':self._testMethodName,'kind':'NEGATIVE_CONTROL',
                            'expected_denial':code,'observed_denial':str(found.exception),'matched':True})

    def test_four_consumers_share_selector_fresh_scoped_receipts(self):
        for consumer in CONSUMERS:
            selector,evidence = self.fixture(consumer,'fresh-'+consumer+'-0001')
            output = getattr(ConsumerAdapters(selector),consumer)(evidence,'fresh-'+consumer+'-0001')
            self.assertEqual(output.consumer,consumer)
            self.assertEqual(output.payload,evidence.payload)
            self.assertFalse(output.execution_allowed)
            self.assertFalse(output.external_calls_allowed)
            self.events.append({'test':self._testMethodName,'kind':'SYNTHETIC_POSITIVE',
                'consumer':consumer,'result':{'oid':output.oid,'generation':output.generation,
                'execution_allowed':output.execution_allowed,'external_calls_allowed':output.external_calls_allowed},
                'policy':asdict(selector.policy),'evidence':{**asdict(evidence),
                'payload':base64.b64encode(evidence.payload).decode(),'payload_encoding':'base64'},
                'public_trust_roots':[{**asdict(r),'public_pem':r.public_pem.decode('ascii')} for r in self.roots]})
        with self.ledger.connect() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM intents').fetchone()[0],4)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM nonces').fetchone()[0],8)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM head').fetchone()[0],1)

    def test_release_manifest_and_side_ref_cannot_authorize(self):
        selector,e = self.fixture()
        for kind in ('GITHUB_RELEASE','LEGACY_MANIFEST','SECONDARY_REF','OWNER_ARCHIVE'):
            with self.subTest(kind=kind):
                self.denied('HISTORICAL_SOURCE_CANNOT_AUTHORIZE',lambda:selector.select(replace(e,source_kind=kind),'restore','intent-fixture-0001'))

    def test_exact_ref_rejects_side_alias(self):
        selector,e = self.fixture()
        for ref in ('refs/heads/mxm-o04-stage-authority-v1',OWNER_ROOT[0],'refs/tags/mxm-o04-active-v1',ACTIVE_REF+'-alias'):
            with self.subTest(ref=ref):
                self.denied('EXACT_REF_REQUIRED',lambda:selector.select(replace(e,ref=ref),'restore','intent-fixture-0001'))

    def test_oid_mismatch(self):
        s,e=self.fixture();self.denied('OID_MISMATCH',lambda:s.select(replace(e,oid='d'*40),'restore','intent-fixture-0001'))

    def test_generation_mismatch_and_bool(self):
        s,e=self.fixture()
        for value in (1807,1809,True,'1808'):
            self.denied('GENERATION_MISMATCH',lambda:s.select(replace(e,generation=value),'restore','intent-fixture-0001'))

    def test_payload_tamper(self):
        s,e=self.fixture();self.denied('PAYLOAD_DIGEST',lambda:s.select(replace(e,payload=e.payload+b' '),'restore','intent-fixture-0001'))

    def test_checkpoint_internal_generation_mismatch(self):
        raw=canonical({'schema':'mxm.synthetic.checkpoint-input.v1','marker':'SYNTHETIC_ONLY',
                       'generation':1807,'checkpoint':{},'permissions':FLAGS})
        s,e=self.fixture(payload=raw)
        self.denied('PAYLOAD_SCOPE_OR_GENERATION',lambda:s.select(e,'restore','intent-fixture-0001'))

    def test_payload_extra_field_or_execution_flag(self):
        for extra in (True,False):
            obj={'schema':'mxm.synthetic.checkpoint-input.v1','marker':'SYNTHETIC_ONLY','generation':1808,
                 'checkpoint':{},'permissions':{**FLAGS,'execution':True} if not extra else FLAGS}
            if extra:obj['release_fallback']=True
            s,e=self.fixture(payload=canonical(obj))
            self.denied('PAYLOAD_FIELDS' if extra else 'PAYLOAD_SCOPE_OR_GENERATION',lambda:s.select(e,'restore','intent-fixture-0001'))

    def test_wrong_principal_parent_and_epoch(self):
        s,e=self.fixture()
        for changes,code in (({'issuer_principal':'SYNTHETIC_WRONG'},'ISSUER_MISMATCH'),
                             ({'predecessor_oid':'d'*40},'PREDECESSOR_MISMATCH'),({'epoch':2},'EPOCH_MISMATCH')):
            self.denied(code,lambda:s.select(replace(e,**changes),'restore','intent-fixture-0001'))

    def test_conflicting_and_missing_authority_claims(self):
        s,e=self.fixture()
        for claims in ((),e.authority_claims+(('release:412686323','d'*40,1808,'e'*64),)):
            self.denied('CONFLICTING_OR_MISSING_AUTHORITY_CLAIMS',lambda:s.select(replace(e,authority_claims=claims),'restore','intent-fixture-0001'))

    def test_absent_owner_or_auditor_receipt(self):
        s,e=self.fixture()
        for receipts in ((),e.receipts[:1],e.receipts[1:]):
            self.denied('TWO_RECEIPTS_REQUIRED',lambda:s.select(replace(e,receipts=receipts),'restore','intent-fixture-0001'))

    def test_invalid_owner_and_auditor_signature(self):
        s,e=self.fixture()
        for index in (0,1):
            receipts=list(e.receipts);receipts[index]={**receipts[index],'signature_b64':base64.b64encode(b'\0'*64).decode()}
            self.denied('SIGNATURE_INVALID',lambda:s.select(replace(e,receipts=tuple(receipts)),'restore','intent-fixture-0001'))

    def test_receipt_expired_or_not_yet_valid(self):
        s,e=self.fixture();statement=s.statement('restore','intent-fixture-0001')
        for index in (0,1):
            for changes in ({'expires_at':1100},{'not_before':1150,'expires_at':1250}):
                receipts=list(e.receipts);receipts[index]=self.receipt(ROLES[index],statement,**changes)
                self.denied('RECEIPT_TIME',lambda:s.select(replace(e,receipts=tuple(receipts)),'restore','intent-fixture-0001'))

    def test_receipt_ttl_and_algorithm(self):
        s,e=self.fixture();statement=s.statement('restore','intent-fixture-0001')
        for changes,code in (({'expires_at':1500},'RECEIPT_TIME'),({'algorithm':'none'},'RECEIPT_IDENTITY_OR_ALGORITHM')):
            receipts=(self.receipt(ROLES[0],statement,**changes),e.receipts[1])
            self.denied(code,lambda:s.select(replace(e,receipts=receipts),'restore','intent-fixture-0001'))

    def test_revoked_or_expired_trust_root(self):
        for index in (0,1):
            for change in ({'revoked':True},{'valid_until':1100}):
                roots=list(self.roots);roots[index]=replace(roots[index],**change)
                s,e=self.fixture(roots=tuple(roots))
                self.denied('TRUST_REVOKED_OR_EXPIRED',lambda:s.select(e,'restore','intent-fixture-0001'))

    def test_revoked_issuer_or_authority_policy(self):
        for field in ('issuer_revoked','authority_revoked'):
            self.denied('ISSUER_OR_AUTHORITY_REVOKED',lambda:self.fixture(policy_changes={field:True}))

    def test_expired_or_future_policy_snapshot(self):
        for values in ({'valid_from':800,'valid_until':1100},{'valid_from':1150,'valid_until':1400}):
            s,e=self.fixture(policy_changes=values)
            self.denied('POLICY_EXPIRED_OR_NOT_YET_VALID',lambda:s.select(e,'restore','intent-fixture-0001'))

    def test_same_key_with_different_pem_is_not_independent(self):
        roots=(self.roots[0],replace(self.roots[1],public_pem=self.roots[0].public_pem+b'\n'))
        self.denied('SEPARATE_PUBLIC_KEYS',lambda:ReceiptVerifier(roots))

    def test_cross_consumer_and_source_scope_receipt(self):
        s,e=self.fixture()
        self.denied('RECEIPT_BINDING',lambda:s.select(e,'worker','intent-fixture-0001'))
        for field,value in (('source_sha','d'*40),('policy_sha256','e'*64),('owner_root',[]),('permissions',{**FLAGS,'restart':True})):
            bad={**s.statement('restore','intent-fixture-0001'),field:value}
            receipts=tuple(self.receipt(role,bad) for role in ROLES)
            self.denied('RECEIPT_BINDING',lambda:s.select(replace(e,receipts=receipts),'restore','intent-fixture-0001'))

    def test_receipt_identity_or_duplicate_role(self):
        s,e=self.fixture();statement=s.statement('restore','intent-fixture-0001')
        wrong=self.receipt(ROLES[0],statement,principal='SYNTHETIC_IMPOSTOR')
        self.denied('RECEIPT_IDENTITY_OR_ALGORITHM',lambda:s.select(replace(e,receipts=(wrong,e.receipts[1])),'restore','intent-fixture-0001'))
        self.denied('RECEIPT_ROLE',lambda:s.select(replace(e,receipts=(e.receipts[0],e.receipts[0])),'restore','intent-fixture-0001'))

    def test_replayed_intent_denied_after_cold_reopen(self):
        s,e=self.fixture();s.select(e,'restore','intent-fixture-0001')
        s2,e2=self.fixture(ledger=SyntheticLedger(self.path))
        self.denied('INTENT_REPLAY',lambda:s2.select(e2,'restore','intent-fixture-0001'))

    def test_receipt_nonce_reused_for_new_intent(self):
        s,e=self.fixture();s.select(e,'restore','intent-fixture-0001')
        s2,e2=self.fixture(intent='intent-fixture-0002')
        receipts=tuple(self.receipt(role,s2.statement('restore','intent-fixture-0002'),nonce=e.receipts[i]['nonce']) for i,role in enumerate(ROLES))
        self.denied('RECEIPT_REUSE',lambda:s2.select(replace(e2,receipts=receipts),'restore','intent-fixture-0002'))

    def test_conflicting_same_generation(self):
        s,e=self.fixture();s.select(e,'restore','intent-fixture-0001')
        s2,e2=self.fixture(intent='intent-conflict-0002',policy_changes={'candidate_oid':'d'*40})
        self.denied('CONFLICTING_SAME_GENERATION',lambda:s2.select(e2,'restore','intent-conflict-0002'))

    def test_generation_gap_and_predecessor_denied(self):
        for changes in ({'generation':1809},{'predecessor_oid':'d'*40}):
            s,e=self.fixture(policy_changes=changes)
            self.denied('GENERATION_GAP_OR_PARENT',lambda:s.select(e,'restore','intent-fixture-0001'))

    def test_monotonic_successor_then_rollback_denied(self):
        s,e=self.fixture();s.select(e,'restore','intent-fixture-0001')
        s2,e2=self.fixture(intent='intent-successor-0002',policy_changes={'generation':1809,'candidate_oid':'d'*40,'predecessor_oid':'a'*40,'epoch':2})
        self.assertFalse(s2.select(e2,'restore','intent-successor-0002').execution_allowed)
        s3,e3=self.fixture(intent='intent-rollback-0003')
        self.denied('ROLLBACK',lambda:s3.select(e3,'restore','intent-rollback-0003'))

    def test_transport_uncertainty_has_no_fallback(self):
        s,e=self.fixture()
        for status in ('UNKNOWN_ACK','TIMEOUT','STALE_CACHE','MISSING'):
            self.denied('TRANSPORT_UNKNOWN_STOP',lambda:s.select(replace(e,transport=status),'restore','intent-fixture-0001'))
        with self.ledger.connect() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM intents').fetchone()[0],0)

    def test_ack_lost_after_commit_no_second_acceptance(self):
        s,e=self.fixture(ledger=SyntheticLedger(self.path,fault_after_commit=True))
        self.denied('ACK_UNKNOWN_STOP_NO_RETRY',lambda:s.select(e,'restore','intent-fixture-0001'))
        binding=digest(canonical(s.statement('restore','intent-fixture-0001')))
        result=self.ledger.reconcile('intent-fixture-0001',binding)
        self.assertEqual(result['state'],'ALREADY_RECORDED_NO_REEXECUTION')
        self.assertFalse(result['execution_allowed']);self.assertFalse(result['retry_allowed'])
        self.events.append({'test':self._testMethodName,'kind':'ACK_RECONCILIATION_READ_ONLY',
                            'state':result,'second_acceptance_permitted':False})
        s2,e2=self.fixture(ledger=SyntheticLedger(self.path))
        self.denied('INTENT_REPLAY',lambda:s2.select(e2,'restore','intent-fixture-0001'))

    def test_unknown_or_conflicting_ack_reconciliation_denied(self):
        self.denied('ACK_UNKNOWN_OR_CONFLICT_STOP',lambda:self.ledger.reconcile('unknown-intent-0001','f'*64))
        s,e=self.fixture();s.select(e,'restore','intent-fixture-0001')
        self.denied('ACK_UNKNOWN_OR_CONFLICT_STOP',lambda:self.ledger.reconcile('intent-fixture-0001','f'*64))

    def test_concurrent_duplicate_accepted_once(self):
        s,e=self.fixture()
        def run(_):
            local=AuthoritySelector(s.policy,ReceiptVerifier(self.roots),SyntheticLedger(self.path),lambda:self.now,mode='SYNTHETIC_ONLY')
            try:local.select(e,'restore','intent-fixture-0001');return 'ACCEPTED_SYNTHETIC'
            except Denied as error:return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
        self.assertCountEqual(results,['ACCEPTED_SYNTHETIC','INTENT_REPLAY'])
        self.events.append({'test':self._testMethodName,'kind':'CONCURRENT_DUPLICATE',
                            'observed_results':sorted(results),'synthetic_acceptances':1})

    def test_archive_read_only_cannot_be_promoted_by_any_adapter(self):
        raw=b'SYNTHETIC_ARCHIVE_BYTES_ONLY';pin=ArchivePin('SYNTHETIC_ARCHIVE_1807',digest(raw))
        result=read_archive(raw,pin)
        self.assertEqual(result.payload,raw);self.assertTrue(result.read_only);self.assertFalse(result.execution_allowed)
        s,_=self.fixture();adapters=ConsumerAdapters(s)
        for consumer in CONSUMERS:
            self.denied('ACTIVE_EVIDENCE_REQUIRED_NO_ARCHIVE_PROMOTION',lambda:getattr(adapters,consumer)(result,'intent-archive-0001'))

    def test_archive_integrity_and_real_owner_pin(self):
        self.denied('ARCHIVE_INTEGRITY',lambda:read_archive(b'altered',ArchivePin('SYNTHETIC_ARCHIVE',digest(b'original'))))
        self.denied('ARCHIVE_INTEGRITY',lambda:read_owner_archive(b'not the real journal'))
        self.assertEqual(OWNER_ROOT[1],'a830c132521bd4348454653f713e04f6107484fe')
        self.assertEqual(OWNER_ROOT[2],1807)

    def test_duplicate_and_noncanonical_json_denied(self):
        for payload,code in ((b'{"x":1,"x":2}','DUPLICATE_JSON_KEY'),(b'{ "x": 1 }','NONCANONICAL_JSON')):
            s,e=self.fixture(payload=payload)
            self.denied(code,lambda:s.select(e,'restore','intent-fixture-0001'))

    def test_real_backend_always_disabled(self):
        s,_=self.fixture()
        self.denied('REAL_AUTHORITY_BACKEND_DISABLED',lambda:AuthoritySelector(s.policy,s.verifier,self.ledger,lambda:self.now))
        self.denied('REAL_CONSUMERS_NOT_AUTHORIZED_OR_CONNECTED',lambda:real_consumer_input({'generation':1808}))

    def test_root_and_reference_policy_cannot_drift(self):
        s,_=self.fixture()
        for changes in ({'authority_ref':ACTIVE_REF+'-other'},{'owner_root':('fake','d'*40,1807,'f'*64)}):
            self.denied('FIXED_ROOT_OR_REF',lambda:replace(s.policy,**changes).validate())

    def test_deleted_ledger_is_not_recreated(self):
        s,e=self.fixture();self.path.unlink()
        self.denied('LEDGER_UNCERTAIN_STOP',lambda:s.select(e,'restore','intent-fixture-0001'))
        self.assertFalse(self.path.exists())

    def test_failed_validation_consumes_no_intent_or_receipt(self):
        s,e=self.fixture()
        self.denied('OID_MISMATCH',lambda:s.select(replace(e,oid='d'*40),'restore','intent-fixture-0001'))
        result=s.select(e,'restore','intent-fixture-0001')
        self.assertFalse(result.execution_allowed)

    def test_pinned_source_matrix_compatibility_and_archive_boundaries(self):
        path=Path('verification/p0-supersession/compatibility.json')
        matrix=json.loads(path.read_text())
        self.assertEqual(len(matrix['source_versions']),10)
        self.assertEqual(len(matrix['consumer_matrix']),29)
        self.assertEqual(matrix['historical_executions'],0)
        self.assertEqual(matrix['operational_migrations'],0)
        for source in matrix['source_versions']:
            self.assertEqual(source['sha256'],source['readback_sha256'])
            self.assertFalse(source['executed'])
        s,e=self.fixture();adapters=ConsumerAdapters(s)
        for row in matrix['consumer_matrix']:
            with self.subTest(path=row['path'],ref=row['source_ref'],function=row['function']):
                self.assertEqual(row['migration_status'],'NOT_MIGRATED_NOT_EXECUTED')
                self.assertTrue(row['positional_arguments'] or row['function'] in ('main','child','gate'))
                archive=adapters.archive(b'SYNTHETIC_LEGACY_SHAPE',ArchivePin('SYNTHETIC_COMPAT_ARCHIVE',digest(b'SYNTHETIC_LEGACY_SHAPE')))
                self.assertFalse(archive.execution_allowed)
                boundary=row['adapter_boundary']
                if boundary in CONSUMERS:
                    self.denied('HISTORICAL_SOURCE_CANNOT_AUTHORIZE',lambda:getattr(adapters,boundary)(replace(e,source_kind='LEGACY_MANIFEST'),'intent-compat-0001'))


def main():
    output=Path('verification/p0-supersession');output.mkdir(parents=True,exist_ok=True)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ConsumerAuthorityTests)
    with (output/'tests.txt').open('w') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    summary={'schema':'mxm.p0.supersession.synthetic-tests.v1','tests':result.testsRun,
             'failures':len(result.failures),'errors':len(result.errors),'successful':result.wasSuccessful(),
             'fixture_identity_scope':'EPHEMERAL_SYNTHETIC_OWNER_AND_AUDITOR_ONLY',
             'network_in_tests':'socket.socket patched to deny','historical_executions':0,
             'real_checkpoint_acceptances':0,'broker_requests':0,'source_compatibility_rows':29,
             'production_backend':'UNCONDITIONALLY_DISABLED','sqlite_scope':'SAME_LOCAL_DATABASE_ONLY_NOT_GITHUB_ATOMICITY'}
    (output/'test-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (output/'case-evidence.json').write_text(json.dumps({'schema':'mxm.p0.supersession.case-evidence.v1',
        'scope':'SYNTHETIC_ONLY_NOT_REAL_OWNER_OR_AUDITOR','events':ConsumerAuthorityTests.events},indent=2)+'\n')
    print((output/'tests.txt').read_text());print(json.dumps(summary))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':main()
