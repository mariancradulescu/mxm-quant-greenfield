"""Public-only synthetic lifecycle verifier. No signing/private-key API exists.

The REAL entrypoint is unconditionally disabled. Independent human identity,
custody and current-head provenance are external prerequisites, not inferred
from repository content, a self-signature, a role string or ChatGPT.
"""
import base64
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

REPO = 'mariancradulescu/mxm-quant-greenfield'
ROOT_OID = 'a830c132521bd4348454653f713e04f6107484fe'
EXCLUDED = ['DIRECTOR','ISSUER','GITHUB_ACTIONS','STAGING_APP_5343530']
PREFIX = b'MXM-AUDITOR-TRUST-SYNTHETIC-V1\x00'


class Denied(RuntimeError):
    pass


def need(ok, code):
    if not ok: raise Denied(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    # Explicit ASCII, integer-only profile; not claimed to be general RFC8785.
    def walk(v):
        need(type(v) in (dict,list,str,int,bool,type(None)), 'JSON_PROFILE')
        if type(v) is str: need(v.isascii(), 'ASCII_PROFILE')
        if type(v) is int: need(abs(v) <= 2**53-1, 'INTEGER_RANGE')
        if type(v) is list:
            for item in v: walk(item)
        if type(v) is dict:
            for key,item in v.items():
                need(type(key) is str and key.isascii(), 'JSON_KEYS');walk(item)
    walk(value)
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')


def parse(raw):
    need(type(raw) is bytes and len(raw) <= 262144, 'JSON_BUDGET')
    def pairs(rows):
        out={}
        for key,value in rows:
            need(key not in out,'DUPLICATE_KEY');out[key]=value
        return out
    try:
        value=json.loads(raw,object_pairs_hook=pairs)
        need(canonical(value)==raw,'NONCANONICAL_JSON')
        return value
    except (ValueError,UnicodeError,RecursionError):
        raise Denied('JSON_PARSE') from None


def fields(value, expected):
    need(type(value) is dict and set(value)==set(expected),'FIELDS')


def integer(value):return type(value) is int and value >= 0
def hash256(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def key_bytes(key):
    fields(key,('key_id','algorithm','spki_der_b64','spki_sha256','not_before','expires_at'))
    need(type(key['key_id']) is str and key['key_id'].startswith('SYNTHETIC_') and
         key['algorithm']=='Ed25519','KEY_ID_OR_ALGORITHM')
    try: raw=base64.b64decode(key['spki_der_b64'],validate=True)
    except (ValueError,TypeError):raise Denied('PUBLIC_KEY_ENCODING') from None
    need(len(raw)==44 and raw.startswith(bytes.fromhex('302a300506032b6570032100')) and
         sha(raw)==key['spki_sha256'],'PUBLIC_KEY_SPKI')
    need(integer(key['not_before']) and integer(key['expires_at']) and
         0 < key['expires_at']-key['not_before'] <= 366*86400,'KEY_VALIDITY')
    return raw


def verify(key, body, signature):
    der=key_bytes(key)
    try:
        sig=base64.b64decode(signature,validate=True)
        need(len(sig)==64,'SIGNATURE_LENGTH')
        with tempfile.TemporaryDirectory(prefix='mxm-public-auditor-') as folder:
            root=Path(folder)
            (root/'public.der').write_bytes(der)
            (root/'body').write_bytes(PREFIX+canonical(body))
            (root/'signature').write_bytes(sig)
            result=subprocess.run(['openssl','pkeyutl','-verify','-pubin','-keyform','DER',
                '-inkey',str(root/'public.der'),'-rawin','-in',str(root/'body'),'-sigfile',str(root/'signature')],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,check=False)
        need(result.returncode==0,'SIGNATURE_INVALID')
    except (ValueError,TypeError,OSError,subprocess.SubprocessError):
        raise Denied('SIGNATURE_VERIFY_FAILED') from None


@dataclass(frozen=True)
class EnrollmentPin:
    genesis_sha256: str
    subject_id: str
    custody_id: str
    spki_sha256: str


@dataclass(frozen=True)
class TrustedHead:
    # Must come from independent durable high-water state, NEVER the bundle itself.
    sequence: int
    head_sha256: str
    witnessed_at: int
    expires_at: int


class PublicTrustVerifier:
    def __init__(self,pin,*,mode='REAL_DISABLED'):
        need(mode=='SYNTHETIC_ONLY','REAL_AUDITOR_NOT_ENROLLED')
        need(type(pin) is EnrollmentPin and hash256(pin.genesis_sha256) and hash256(pin.spki_sha256)
             and pin.subject_id.startswith('SYNTHETIC_') and pin.custody_id.startswith('SYNTHETIC_'),
             'EXTERNAL_ENROLLMENT_PIN_REQUIRED')
        self.pin=pin

    def chain(self,genesis,events,head,now):
        need(integer(now) and type(head) is TrustedHead and integer(head.sequence) and
             hash256(head.head_sha256),'TRUSTED_HEAD_REQUIRED')
        need(integer(head.witnessed_at) and integer(head.expires_at) and
             head.witnessed_at<=now<head.expires_at and
             0<head.expires_at-head.witnessed_at<=300,'INDEPENDENT_HEAD_STALE')
        fields(genesis,('body','proof_of_possession'))
        body=genesis['body']
        fields(body,('schema','marker','repository','repository_id','subject_id','custody_id',
                     'independent_from','owner_root_oid','scope','enrollment_nonce','enrolled_at','key'))
        need(sha(canonical(body))==self.pin.genesis_sha256,'GENESIS_PIN_MISMATCH')
        need(body['schema']=='mxm.synthetic.auditor-enrollment.v1' and body['marker']=='SYNTHETIC_ONLY'
             and body['repository']==REPO and type(body['repository_id']) is int and body['repository_id']==1374181010
             and body['owner_root_oid']==ROOT_OID and body['scope']=='PREPARATION_RECEPTION_ONLY', 'GENESIS_SCOPE')
        need(body['subject_id']==self.pin.subject_id and body['custody_id']==self.pin.custody_id and
             body['independent_from']==EXCLUDED,'IDENTITY_OR_CUSTODY_BINDING')
        need(type(body['enrollment_nonce']) is str and len(body['enrollment_nonce'])>=16 and
             integer(body['enrolled_at']) and body['enrolled_at']<=now,'ENROLLMENT_CHALLENGE')
        key=body['key'];key_bytes(key)
        need(key['spki_sha256']==self.pin.spki_sha256 and key['not_before']<=body['enrolled_at']<key['expires_at'],
             'ENROLLMENT_KEY_BINDING')
        verify(key,body,genesis['proof_of_possession'])
        current=sha(canonical(body));seq=0;revoked=False;seen={key['spki_sha256']};seen_ids={key['key_id']};last_time=body['enrolled_at']
        need(type(events) is list and len(events)<=100,'EVENT_BUDGET')
        for event in events:
            fields(event,('body','old_signature','new_signature'))
            item=event['body']
            fields(item,('schema','marker','repository','subject_id','custody_id','sequence','previous_sha256',
                         'kind','issued_at','new_key','reason'))
            need(not revoked,'REVOKED_CHAIN_CLOSED')
            need(item['schema']=='mxm.synthetic.auditor-lifecycle.v1' and item['marker']=='SYNTHETIC_ONLY'
                 and item['repository']==REPO and item['subject_id']==self.pin.subject_id and
                 item['custody_id']==self.pin.custody_id,'EVENT_IDENTITY_SCOPE')
            need(type(item['sequence']) is int and item['sequence']==seq+1 and
                 item['previous_sha256']==current,'EVENT_ROLLBACK_REPLAY_OR_FORK')
            need(integer(item['issued_at']) and last_time<=item['issued_at']<=now and
                 key['not_before']<=item['issued_at']<key['expires_at'],'EVENT_TIME')
            need(type(item['reason']) is str and 1<=len(item['reason'])<=200,'EVENT_REASON')
            verify(key,item,event['old_signature'])
            if item['kind']=='ROTATE':
                new=item['new_key'];key_bytes(new)
                need(new['spki_sha256'] not in seen and new['key_id'] not in seen_ids and
                     new['not_before']<=item['issued_at']<new['expires_at'],'ROTATION_KEY_REUSE_OR_TIME')
                verify(new,item,event['new_signature'])
                seen.add(new['spki_sha256']);seen_ids.add(new['key_id']);key=new
            else:
                need(item['kind']=='REVOKE' and item['new_key'] is None and event['new_signature'] is None,
                     'EVENT_KIND')
                revoked=True
            seq+=1;current=sha(canonical(item));last_time=item['issued_at']
        need(seq==head.sequence and current==head.head_sha256,'INDEPENDENT_HEAD_MISMATCH')
        return {'key':key,'sequence':seq,'head_sha256':current,'revoked':revoked,
                'subject_id':self.pin.subject_id,'custody_id':self.pin.custody_id,'head_effective_at':last_time}

    def receipt(self,genesis,events,head,receipt,expected,challenge,now):
        # A caller-supplied dictionary claiming to be verified state is never trusted.
        state=self.chain(genesis,events,head,now)
        need(not state['revoked'],'AUDITOR_REVOKED')
        need(state['key']['not_before']<=now<state['key']['expires_at'],'AUDITOR_KEY_EXPIRED')
        fields(receipt,('body','signature'))
        body=receipt['body']
        fields(body,('schema','marker','repository','subject_id','custody_id','key_id','registry_sequence',
                     'registry_head_sha256','challenge','issued_at','expires_at','scope','verdict',
                     'context','execution_allowed'))
        need(body['schema']=='mxm.synthetic.auditor-reception.v1' and body['marker']=='SYNTHETIC_ONLY'
             and body['repository']==REPO and body['scope']=='PREPARATION_RECEPTION_ONLY' and
             body['execution_allowed'] is False and body['verdict']=='ACCEPT_PREPARATION_ONLY','RECEIPT_SCOPE')
        need(body['subject_id']==state['subject_id'] and body['custody_id']==state['custody_id'] and
             body['key_id']==state['key']['key_id'],'RECEIPT_IDENTITY')
        need(body['registry_sequence']==state['sequence'] and type(body['registry_sequence']) is int and
             body['registry_head_sha256']==state['head_sha256'],'RECEIPT_REGISTRY_HEAD')
        need(type(challenge) is str and re.fullmatch('[0-9a-f]{64}',challenge) is not None and
             body['challenge']==challenge,'FRESH_CHALLENGE_REQUIRED')
        need(integer(body['issued_at']) and integer(body['expires_at']) and
             max(state['key']['not_before'],state['head_effective_at'])<=body['issued_at']<=now<body['expires_at'] and
             0<body['expires_at']-body['issued_at']<=86400 and
             body['expires_at']<=state['key']['expires_at'],'RECEIPT_EXPIRY')
        fields(expected,('source_sha','evidence_sha256','policy_sha256','owner_root_oid','operation_id'))
        need(type(expected['source_sha']) is str and re.fullmatch('[0-9a-f]{40}',expected['source_sha'])
             and hash256(expected['evidence_sha256']) and hash256(expected['policy_sha256']) and
             expected['owner_root_oid']==ROOT_OID and type(expected['operation_id']) is str and
             len(expected['operation_id'])>=8,'EXPECTED_CONTEXT')
        need(canonical(body['context'])==canonical(expected),'RECEIPT_CONTEXT')
        verify(state['key'],body,receipt['signature'])
        return {'state':'SYNTHETIC_PUBLIC_RECEIPT_VALID','identity_basis':'EXTERNALLY_PINNED_SYNTHETIC_ENROLLMENT',
                'signature_valid':True,'execution_allowed':False,'receipt_consumed':False,
                'replay_consumption':'NOT_IMPLEMENTED_HERE_REAL_BACKEND_DISABLED'}


def verify_real_receipt(*args,**kwargs):
    raise Denied('REAL_AUDITOR_NOT_ENROLLED_NO_OPERATIONAL_AUTHORITY')
