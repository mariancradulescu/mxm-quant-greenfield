"""Shared verifier and selector, usable only in an explicit synthetic harness.

No GitHub transport, private key loader, issuer, broker, legacy import or callback.
Production entry is unconditionally closed; returned inputs grant no execution.
"""
import base64
import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

ACTIVE_REF = 'refs/heads/mxm-o04-active-v1'
OWNER_ROOT = ('refs/heads/mxm-o04-accepted-owner-1807-v1',
              'a830c132521bd4348454653f713e04f6107484fe', 1807,
              'ea93f6c38768824521d4ad3e316c0cd507c837e5c089c5e3b6f63d20d79e7470')
ROLES = ('OWNER_SYNTHETIC', 'AUDITOR_SYNTHETIC')
CONSUMERS = ('restore', 'worker', 'handoff', 'economic')
FLAGS = {'execution': False, 'research': False, 'restart': False, 'broker_io': False}
MAX_BYTES = 1024 * 1024


class Denied(RuntimeError):
    pass


def need(condition, code):
    if not condition:
        raise Denied(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                          allow_nan=False).encode('ascii')
    except (ValueError, TypeError, UnicodeError):
        raise Denied('CANONICAL_ENCODING') from None


def strict_json(raw):
    need(type(raw) is bytes and len(raw) <= MAX_BYTES, 'PAYLOAD_BYTES')
    def pairs(items):
        obj = {}
        for key, value in items:
            need(key not in obj, 'DUPLICATE_JSON_KEY')
            obj[key] = value
        return obj
    try:
        obj = json.loads(raw, object_pairs_hook=pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(Denied('NONFINITE_JSON')))
        need(canonical(obj) == raw, 'NONCANONICAL_JSON')
        return obj
    except (ValueError, UnicodeError, RecursionError):
        raise Denied('JSON_PARSE') from None


def exact_fields(value, fields, code):
    need(type(value) is dict and set(value) == set(fields), code)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def oid(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{40}', value) is not None


def sha256(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def closed_flags(value):
    return type(value) is dict and set(value) == set(FLAGS) and all(v is False for v in value.values())


@dataclass(frozen=True)
class Policy:
    candidate_oid: str
    generation: int
    payload_sha256: str
    predecessor_oid: str
    issuer_principal: str
    source_sha: str
    policy_sha256: str
    epoch: int = 1
    repository_id: int = 1374181010
    repository: str = 'mariancradulescu/mxm-quant-greenfield'
    authority_ref: str = ACTIVE_REF
    owner_root: tuple = OWNER_ROOT
    issuer_revoked: bool = False
    authority_revoked: bool = False
    valid_from: int = 1000
    valid_until: int = 1300

    def validate(self):
        need(self.authority_ref == ACTIVE_REF and self.owner_root == OWNER_ROOT, 'FIXED_ROOT_OR_REF')
        need(self.repository_id == 1374181010 and type(self.repository_id) is int and
             self.repository == 'mariancradulescu/mxm-quant-greenfield', 'REPOSITORY')
        need(oid(self.candidate_oid) and oid(self.predecessor_oid) and oid(self.source_sha), 'POLICY_OID')
        need(integer(self.generation, 1808) and integer(self.epoch, 1), 'POLICY_GENERATION_EPOCH')
        need(sha256(self.payload_sha256) and sha256(self.policy_sha256), 'POLICY_DIGEST')
        need(type(self.issuer_principal) is str and self.issuer_principal.startswith('SYNTHETIC_'), 'SYNTHETIC_ISSUER_ONLY')
        need(self.issuer_revoked is False and self.authority_revoked is False, 'ISSUER_OR_AUTHORITY_REVOKED')
        need(integer(self.valid_from) and integer(self.valid_until) and
             0 < self.valid_until-self.valid_from <= 300, 'POLICY_VALIDITY_WINDOW')


@dataclass(frozen=True)
class TrustRoot:
    role: str
    principal: str
    key_id: str
    public_pem: bytes
    valid_from: int
    valid_until: int
    revoked: bool = False


class ReceiptVerifier:
    """Public keys supplied out-of-band by the SYNTHETIC test harness only."""
    def __init__(self, roots):
        self.roots = tuple(roots)
        need(len(self.roots) == 2 and {r.role for r in self.roots} == set(ROLES), 'TRUST_ROLES')
        need(len({r.principal for r in self.roots}) == 2 and
             len({r.key_id for r in self.roots}) == 2, 'SEPARATE_TRUST_ROOTS')
        for root in self.roots:
            need(root.principal.startswith('SYNTHETIC_') and root.key_id.startswith('SYNTHETIC_') and
                 type(root.public_pem) is bytes and len(root.public_pem) <= 2048 and
                 integer(root.valid_from) and integer(root.valid_until) and
                 root.valid_from < root.valid_until and type(root.revoked) is bool, 'TRUST_ROOT_FORMAT')
        fingerprints = []
        for root in self.roots:
            try:
                with tempfile.TemporaryDirectory(prefix='mxm-public-type-') as folder:
                    path = Path(folder)/'public.pem'; path.write_bytes(root.public_pem)
                    result = subprocess.run(['openssl','pkey','-pubin','-in',str(path),'-outform','DER'],
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        timeout=10, check=False)
                need(result.returncode == 0 and len(result.stdout) == 44 and
                     result.stdout.startswith(bytes.fromhex('302a300506032b6570032100')), 'ED25519_PUBLIC_KEY_REQUIRED')
                fingerprints.append(digest(result.stdout))
            except (OSError, subprocess.SubprocessError):
                raise Denied('TRUST_KEY_PARSE') from None
        need(len(set(fingerprints)) == 2, 'SEPARATE_PUBLIC_KEYS')

    def verify(self, receipts, statement, now):
        need(type(receipts) is tuple and len(receipts) == 2, 'TWO_RECEIPTS_REQUIRED')
        seen = set(); nonces = []
        for receipt in receipts:
            exact_fields(receipt, ('schema','role','principal','key_id','algorithm','nonce',
                                  'not_before','expires_at','statement','signature_b64'), 'RECEIPT_FIELDS')
            role = receipt['role']
            need(type(role) is str and role in ROLES and role not in seen, 'RECEIPT_ROLE')
            seen.add(role)
            root = next(r for r in self.roots if r.role == role)
            need(not root.revoked and root.valid_from <= now < root.valid_until, 'TRUST_REVOKED_OR_EXPIRED')
            need(receipt['schema'] == 'mxm.synthetic.consumer-receipt.v1' and
                 receipt['principal'] == root.principal and receipt['key_id'] == root.key_id and
                 receipt['algorithm'] == 'Ed25519', 'RECEIPT_IDENTITY_OR_ALGORITHM')
            need(integer(receipt['not_before']) and integer(receipt['expires_at']) and
                 receipt['not_before'] <= now < receipt['expires_at'] and
                 receipt['expires_at'] - receipt['not_before'] <= 300 and
                 root.valid_from <= receipt['not_before'] < receipt['expires_at'] <= root.valid_until,
                 'RECEIPT_TIME')
            need(type(receipt['nonce']) is str and re.fullmatch('[a-z0-9-]{8,80}', receipt['nonce']), 'RECEIPT_NONCE')
            need(canonical(receipt['statement']) == canonical(statement), 'RECEIPT_BINDING')
            body = {k:v for k,v in receipt.items() if k != 'signature_b64'}
            try:
                signature = base64.b64decode(receipt['signature_b64'], validate=True)
                need(len(signature) == 64, 'SIGNATURE_LENGTH')
                with tempfile.TemporaryDirectory(prefix='mxm-public-verify-') as folder:
                    path = Path(folder)
                    (path/'public.pem').write_bytes(root.public_pem)
                    (path/'message').write_bytes(canonical(body))
                    (path/'signature').write_bytes(signature)
                    result = subprocess.run(['openssl','pkeyutl','-verify','-pubin','-inkey',str(path/'public.pem'),
                        '-rawin','-in',str(path/'message'),'-sigfile',str(path/'signature')],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=10, check=False)
                need(result.returncode == 0, 'SIGNATURE_INVALID')
            except (ValueError, TypeError, OSError, subprocess.SubprocessError):
                raise Denied('SIGNATURE_VERIFICATION_FAILED') from None
            nonces.append((role, receipt['nonce']))
        return tuple(nonces)


class SyntheticLedger:
    """Local durable at-most-once selection journal. Never a real authority store.

    All instances on the SAME SQLite file serialize through BEGIN IMMEDIATE.
    Missing/deleted/rollbacked storage is not a certified production trust root.
    The marker must exist before opening; a live database is never auto-created.
    """
    @staticmethod
    def initialize(path):
        path = Path(path)
        need(not path.exists(), 'LEDGER_ALREADY_EXISTS')
        connection = sqlite3.connect(path)
        try:
            connection.executescript('''
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=FULL;
                CREATE TABLE marker(value TEXT NOT NULL);
                INSERT INTO marker VALUES('SYNTHETIC_ONLY_NO_GO_V1');
                CREATE TABLE head(slot INTEGER PRIMARY KEY CHECK(slot=1), generation INTEGER NOT NULL,
                                  oid TEXT NOT NULL, digest TEXT NOT NULL, epoch INTEGER NOT NULL);
                CREATE TABLE intents(intent TEXT PRIMARY KEY, binding TEXT NOT NULL);
                CREATE TABLE nonces(role TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(role,nonce));
            ''')
            connection.execute('INSERT INTO head VALUES(1,?,?,?,?)', (OWNER_ROOT[2], OWNER_ROOT[1], OWNER_ROOT[3], 0))
            connection.commit()
        finally:
            connection.close()

    def __init__(self, path, *, fault_after_commit=False):
        self.path = Path(path)
        self.fault_after_commit = fault_after_commit
        need(self.path.is_file(), 'LEDGER_MISSING_STOP')
        with self.connect() as con:
            need(con.execute('SELECT value FROM marker').fetchall() == [('SYNTHETIC_ONLY_NO_GO_V1',)], 'LEDGER_MARKER')

    def connect(self):
        # mode=rw avoids recreating a deleted ledger. Timeout is finite.
        con = sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw', uri=True, timeout=5)
        con.execute('PRAGMA synchronous=FULL')
        return con

    def consume(self, statement, nonces, binding):
        con = self.connect()
        try:
            con.execute('BEGIN IMMEDIATE')
            need(con.execute('SELECT value FROM marker').fetchall() == [('SYNTHETIC_ONLY_NO_GO_V1',)], 'LEDGER_MARKER')
            rows = con.execute('SELECT generation,oid,digest,epoch FROM head WHERE slot=1').fetchall()
            need(len(rows) == 1, 'LEDGER_HEAD_MISSING')
            generation, old_oid, old_digest, epoch = rows[0]
            new_generation = statement['generation']
            need(new_generation >= generation and statement['epoch'] >= epoch, 'ROLLBACK')
            if new_generation == generation:
                need((statement['oid'], statement['payload_sha256'], statement['epoch']) ==
                     (old_oid, old_digest, epoch), 'CONFLICTING_SAME_GENERATION')
            else:
                need(new_generation == generation+1 and statement['predecessor_oid'] == old_oid,
                     'GENERATION_GAP_OR_PARENT')
            need(con.execute('SELECT 1 FROM intents WHERE intent=?', (statement['intent'],)).fetchone() is None,
                 'INTENT_REPLAY')
            for role, nonce in nonces:
                need(con.execute('SELECT 1 FROM nonces WHERE role=? AND nonce=?', (role,nonce)).fetchone() is None,
                     'RECEIPT_REUSE')
                con.execute('INSERT INTO nonces VALUES(?,?)', (role,nonce))
            con.execute('INSERT INTO intents VALUES(?,?)', (statement['intent'],binding))
            con.execute('UPDATE head SET generation=?,oid=?,digest=?,epoch=? WHERE slot=1',
                        (new_generation,statement['oid'],statement['payload_sha256'],statement['epoch']))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        if self.fault_after_commit:
            raise Denied('ACK_UNKNOWN_STOP_NO_RETRY')

    def reconcile(self, intent, binding):
        # Read-only connection: this returns no payload or execution permission.
        con = sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro', uri=True, timeout=5)
        try:
            row = con.execute('SELECT binding FROM intents WHERE intent=?', (intent,)).fetchone()
            need(row is not None and row[0] == binding, 'ACK_UNKNOWN_OR_CONFLICT_STOP')
            return {'state':'ALREADY_RECORDED_NO_REEXECUTION','execution_allowed':False,'retry_allowed':False}
        finally:
            con.close()


@dataclass(frozen=True)
class Evidence:
    source_kind: str
    ref: str
    oid: str
    generation: int
    payload: bytes
    issuer_principal: str
    predecessor_oid: str
    epoch: int
    transport: str
    # Complete set of asserted *authority* claims; archive locators are not claims.
    authority_claims: tuple
    receipts: tuple


@dataclass(frozen=True)
class PreparedInput:
    consumer: str
    oid: str
    generation: int
    payload: bytes
    intent: str
    execution_allowed: bool = False
    external_calls_allowed: bool = False
    scope: str = 'SYNTHETIC_INPUT_ONLY_NO_GO'


@dataclass(frozen=True)
class ArchivePin:
    archive_id: str
    payload_sha256: str


@dataclass(frozen=True)
class ArchiveRead:
    archive_id: str
    payload: bytes
    read_only: bool = True
    execution_allowed: bool = False


def read_archive(raw, pin):
    """Integrity-pinned bytes only; a Release URL/manifest never grants execution.

    Pin provenance must be supplied by the trusted caller. Synthetic test pins
    are not proof of reading/decrypting the real OWNER1807 journal.
    """
    need(type(pin) is ArchivePin and type(pin.archive_id) is str and
         sha256(pin.payload_sha256), 'ARCHIVE_PIN_REQUIRED')
    need(type(raw) is bytes and len(raw) <= MAX_BYTES and digest(raw) == pin.payload_sha256,
         'ARCHIVE_INTEGRITY')
    return ArchiveRead(pin.archive_id, raw)


def read_owner_archive(raw):
    # Exact real root digest; no locator or caller-provided digest may replace it.
    return read_archive(raw, ArchivePin('OWNER_1807_IMMUTABLE_ROOT', OWNER_ROOT[3]))


class AuthoritySelector:
    def __init__(self, policy, verifier, ledger, clock, *, mode='REAL_DISABLED'):
        need(mode == 'SYNTHETIC_ONLY', 'REAL_AUTHORITY_BACKEND_DISABLED')
        need(type(policy) is Policy and type(verifier) is ReceiptVerifier and
             type(ledger) is SyntheticLedger, 'TRUSTED_COMPONENT_TYPES')
        policy.validate()
        self.policy = policy; self.verifier = verifier; self.ledger = ledger; self.clock = clock

    def statement(self, consumer, intent):
        p = self.policy
        need(consumer in CONSUMERS and type(intent) is str and
             re.fullmatch('[a-z0-9-]{8,80}', intent) is not None, 'CONSUMER_OR_INTENT')
        return {'schema':'mxm.synthetic.consumer-selection.v1','marker':'SYNTHETIC_ONLY',
                'repository_id':p.repository_id,'repository':p.repository,'ref':p.authority_ref,
                'oid':p.candidate_oid,'generation':p.generation,'payload_sha256':p.payload_sha256,
                'owner_root':list(OWNER_ROOT),'predecessor_oid':p.predecessor_oid,
                'issuer_principal':p.issuer_principal,'source_sha':p.source_sha,
                'policy_sha256':p.policy_sha256,'epoch':p.epoch,'consumer':consumer,
                'policy_valid_from':p.valid_from,'policy_valid_until':p.valid_until,
                'intent':intent,'permissions':FLAGS.copy()}

    def select(self, evidence, consumer, intent):
        need(type(evidence) is Evidence, 'ACTIVE_EVIDENCE_REQUIRED_NO_ARCHIVE_PROMOTION')
        # Copy mutable nested receipts before verifying or consuming them.
        receipts = copy.deepcopy(evidence.receipts)
        p = self.policy
        need(evidence.source_kind == 'EXACT_ACTIVE_REF', 'HISTORICAL_SOURCE_CANNOT_AUTHORIZE')
        need(evidence.ref == ACTIVE_REF, 'EXACT_REF_REQUIRED')
        need(evidence.transport == 'CONFIRMED_READ', 'TRANSPORT_UNKNOWN_STOP')
        need(evidence.oid == p.candidate_oid and oid(evidence.oid), 'OID_MISMATCH')
        need(type(evidence.generation) is int and evidence.generation == p.generation, 'GENERATION_MISMATCH')
        need(type(evidence.epoch) is int and evidence.epoch == p.epoch, 'EPOCH_MISMATCH')
        need(evidence.predecessor_oid == p.predecessor_oid, 'PREDECESSOR_MISMATCH')
        need(evidence.issuer_principal == p.issuer_principal, 'ISSUER_MISMATCH')
        need(type(evidence.authority_claims) is tuple and len(evidence.authority_claims) == 1 and
             evidence.authority_claims == ((ACTIVE_REF,p.candidate_oid,p.generation,p.payload_sha256),),
             'CONFLICTING_OR_MISSING_AUTHORITY_CLAIMS')
        need(type(evidence.payload) is bytes and digest(evidence.payload) == p.payload_sha256, 'PAYLOAD_DIGEST')
        payload = strict_json(evidence.payload)
        exact_fields(payload, ('schema','marker','generation','checkpoint','permissions'), 'PAYLOAD_FIELDS')
        need(payload['schema'] == 'mxm.synthetic.checkpoint-input.v1' and payload['marker'] == 'SYNTHETIC_ONLY'
             and type(payload['generation']) is int and payload['generation'] == p.generation and
             closed_flags(payload['permissions']) and type(payload['checkpoint']) is dict,
             'PAYLOAD_SCOPE_OR_GENERATION')
        statement = self.statement(consumer,intent)
        now = self.clock(); need(integer(now), 'TRUSTED_CLOCK')
        p.validate()
        need(p.valid_from <= now < p.valid_until, 'POLICY_EXPIRED_OR_NOT_YET_VALID')
        nonces = self.verifier.verify(receipts, statement, now)
        binding = digest(canonical(statement))
        try:
            self.ledger.consume(statement, nonces, binding)
        except sqlite3.Error:
            raise Denied('LEDGER_UNCERTAIN_STOP') from None
        return PreparedInput(consumer, p.candidate_oid, p.generation, evidence.payload, intent)


def real_consumer_input(*args, **kwargs):
    raise Denied('REAL_CONSUMERS_NOT_AUTHORIZED_OR_CONNECTED')
