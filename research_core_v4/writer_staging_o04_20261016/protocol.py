"""Synthetic staging protocol core. No live acceptor credential or grant exists.

Git receive-pack CAS is inherited unchanged from O04 GitFenceLab. This module
cannot confer a GitHub role: public acceptance stays closed unconditionally.
The fixture protocol is deliberately separately named and SYNTHETIC_ONLY.
"""
import base64
import copy
import hashlib
import json
import pathlib
import re
import subprocess
import tempfile
from ..writer_fencing_o04_20261016 import git_fence_lab as lab

STOP='a830c132521bd4348454653f713e04f6107484fe'
SCHEMA='mxm.o04.stage.checkpoint.v1'
ROOT={
 'root_o04_stop_oid':STOP,'owner_generation':1807,'owner_release_id':412686323,
 'owner_journal_asset_id':642889915,'owner_journal_release_id':413440554,
 'owner_canonical_sha256':'ea93f6c38768824521d4ad3e316c0cd507c837e5c089c5e3b6f63d20d79e7470',
 'owner_ciphertext_sha256':'4c4380f9de060d4bd7c8b7fb9be61916285ab581be2bdd8ba72e17909a83adac',
 'owner_gzip_sha256':'a0168de6be0817b192f154f128514da32bc1f0c2b9d14db9a9f63ff055ccf628',
 'owner_release_body_sha256':'01a6d82498c033131302b272ee4ba2f83c4e445f40585f76dfee1a91466679b9'}

def digest(raw):return hashlib.sha256(raw).hexdigest()

def accept_checkpoint(*args,**kwargs):
    # Deliberately no caller-controlled boolean, environment variable or JSON
    # may override the missing exclusive server-side grant.
    raise lab.Denied('PRINCIPAL_ISOLATION_NO_GO')

class SyntheticIssuer:
    """Ephemeral test signer, NOT a GitHub identity/OWNER attestation."""
    def __init__(self,directory):
        self.directory=pathlib.Path(directory);self.directory.mkdir()
        self.key=self.directory/'synthetic-private.pem';self.public=self.directory/'synthetic-public.pem'
        subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(self.key)],check=True,capture_output=True)
        self.key.chmod(0o600)
        subprocess.run(['openssl','pkey','-in',str(self.key),'-pubout','-out',str(self.public)],check=True,capture_output=True)
        self.fingerprint=digest(self.public.read_bytes())
    def sign(self,obj):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'message';p.write_bytes(lab.canonical(obj))
            return subprocess.check_output(['openssl','pkeyutl','-sign','-rawin','-inkey',str(self.key),'-in',str(p)])
    def verify(self,obj,signature):
        try:
            with tempfile.TemporaryDirectory() as d:
                p=pathlib.Path(d)/'message';s=pathlib.Path(d)/'sig'
                p.write_bytes(lab.canonical(obj));s.write_bytes(base64.b64decode(signature,validate=True))
                return subprocess.run(['openssl','pkeyutl','-verify','-rawin','-pubin','-inkey',str(self.public),'-in',str(p),'-sigfile',str(s)],capture_output=True).returncode==0
        except (ValueError,TypeError):return False

class FixtureProtocol:
    """Runs only on synthetic transport, cannot assert principal exclusivity."""
    def __init__(self,transport,issuer,source_sha,clock):
        self.t=transport;self.issuer=issuer;self.source=source_sha;self.clock=clock
    def read(self):
        oid,s=self.t.read()
        lab.need(s['schema_version']==SCHEMA and s['marker']=='SYNTHETIC_ONLY','SCHEMA')
        lab.need(s['root']==ROOT,'ROOT_STOP')
        return oid,s
    def genesis(self):
        s={'schema':'mxm.o04.synthetic.git-fence.v1','schema_version':SCHEMA,'marker':'SYNTHETIC_ONLY',
           'root':ROOT,'status':'UNCLAIMED','epoch':0,'version':0,'generation':0,
           'owner':None,'session':None,'lease_until':0,'accepted':{},'operations':[],
           'pending':None,'source_SHA':self.source,'evidence':{},'principal_isolation':'UNVERIFIED',
           'OWNER_accepts_new_checkpoints':False,'PRODUCTION_GO':False}
        return self.t._publish(lab.ZERO,s)
    def claim(self,expected,session):
        oid,s=self.read();now=self.clock()
        lab.need(oid==expected,'STALE_VERSION')
        lab.need(isinstance(session,str) and len(session)>0,'SESSION')
        lab.need(s['owner'] is None or now>=s['lease_until'],'LEASE_HELD')
        s=copy.deepcopy(s)
        s.update(epoch=s['epoch']+1,owner='SYNTHETIC_FIXTURE_ACCEPTOR',session=session,lease_until=now+120,status='CLAIMED',pending=None)
        return self.t._publish(oid,s)
    def proposal(self,claim_oid,operation,payload=b'SYNTHETIC_ONLY ciphertext'):
        oid,s=self.read();lab.need(oid==claim_oid,'FENCED_WRITER')
        manifest=lab.canonical({'marker':'SYNTHETIC_ONLY','source_SHA':self.source,'ciphertext_sha256':digest(payload)})
        r={'schema_version':SCHEMA,'marker':'SYNTHETIC_ONLY','root_o04_stop_oid':STOP,
           'parent_oid':oid,'expected_old_oid':oid,'epoch':s['epoch'],'version':s['version']+1,
           'operation_id':operation,'writer_principal':s['owner'],'writer_session':s['session'],
           'lease_until':s['lease_until'],'server_time_observed':self.clock(),
           'generation':s['generation']+1,'source_SHA':self.source,
           'manifest_sha256':digest(manifest),'ciphertext_sha256':digest(payload),
           'issuer':{'kind':'SYNTHETIC_EPHEMERAL_ED25519_NOT_GITHUB_IDENTITY','key_sha256':self.issuer.fingerprint}}
        return {'record':r,'manifest':base64.b64encode(manifest).decode(),'ciphertext':base64.b64encode(payload).decode(),
                'signature':base64.b64encode(self.issuer.sign(r)).decode()}
    def validate(self,s,proposal,expected):
        p=proposal;r=p['record'];now=self.clock()
        lab.need(r['schema_version']==SCHEMA and r['marker']=='SYNTHETIC_ONLY','SCHEMA')
        lab.need(r['root_o04_stop_oid']==STOP,'ROOT_STOP')
        lab.need(r['expected_old_oid']==expected and r['parent_oid']==expected,'FENCED_WRITER')
        lab.need(r['epoch']==s['epoch'] and r['writer_principal']==s['owner'] and r['writer_session']==s['session'],'FENCED_WRITER')
        lab.need(now<r['lease_until']==s['lease_until'] and r['server_time_observed']<=now,'LEASE_EXPIRED')
        lab.need(type(r['version']) is int and r['version']==s['version']+1,'VERSION')
        lab.need(type(r['generation']) is int and r['generation']==s['generation']+1,'GENERATION')
        lab.need(r['source_SHA']==s['source_SHA']==self.source and re.fullmatch('[0-9a-f]{40}',self.source),'SOURCE_SHA')
        lab.need(isinstance(r['operation_id'],str) and 1<=len(r['operation_id'])<=128 and r['operation_id'] not in s['operations'],'OPERATION_REPLAY')
        manifest=base64.b64decode(p['manifest'],validate=True);payload=base64.b64decode(p['ciphertext'],validate=True)
        lab.need(digest(manifest)==r['manifest_sha256'] and digest(payload)==r['ciphertext_sha256'],'CONTENT_DIGEST')
        m=json.loads(manifest)
        lab.need(m=={'marker':'SYNTHETIC_ONLY','source_SHA':self.source,'ciphertext_sha256':digest(payload)} and payload.startswith(b'SYNTHETIC_ONLY'),'MANIFEST_BINDING')
        lab.need(r['issuer']=={'kind':'SYNTHETIC_EPHEMERAL_ED25519_NOT_GITHUB_IDENTITY','key_sha256':self.issuer.fingerprint} and self.issuer.verify(r,p['signature']),'SIGNATURE')
    def pending(self,expected,p):
        oid,s=self.read();lab.need(oid==expected and s['status']=='CLAIMED','PENDING_STATE')
        self.validate(s,p,oid);s=copy.deepcopy(s)
        # Evidence bytes are committed with their SHA256 keys BEFORE acceptance.
        for field in ('manifest','ciphertext'):
            raw=base64.b64decode(p[field]);s['evidence'][digest(raw)]=p[field]
        s.update(status='PENDING',pending=p)
        return self.t._publish(oid,s)
    def accept_fixture(self,expected,lose_ack=False):
        oid,s=self.read();lab.need(oid==expected and s['status']=='PENDING','ACCEPT_STATE')
        p=s['pending'];r=p['record'];self.validate(s,p,r['expected_old_oid'])
        for field in ('manifest','ciphertext'):
            lab.need(s['evidence'].get(r[field+'_sha256'])==p[field],'EVIDENCE_MISSING')
        lab.need(str(r['version']) not in s['accepted'],'IMMUTABLE')
        s=copy.deepcopy(s);s['accepted'][str(r['version'])]={'proposal':p,'pending_oid':oid}
        s['operations'].append(r['operation_id'])
        s.update(status='ACCEPTED',version=r['version'],generation=r['generation'],owner=None,session=None,lease_until=0,pending=None)
        return self.t._publish(oid,s,lose_ack=lose_ack)
    def resolve(self,operation,manifest_sha256):
        oid,s=self.read()
        matches=[a for a in s['accepted'].values() if a['proposal']['record']['operation_id']==operation]
        if len(matches)==1 and matches[0]['proposal']['record']['manifest_sha256']==manifest_sha256:
            return {'status':'SYNTHETIC_ACCEPTED_READBACK_NO_REPLAY','oid':oid}
        return {'status':'UNKNOWN','oid':oid}

def owner_reader(ref,state=None,**untrusted):
    # No PRODUCTION_GO input is accepted. STOP can only be observed as STOP.
    if ref=='refs/heads/mxm-o04-accepted-owner-1807-v1' and state and state.get('oid')==STOP:
        return 'STOP_ONLY_FROZEN'
    return 'NOT_AUTHORIZED'

def staging_reader(ref,oid,state,issuer,source):
    """Dry-run only. Caller cannot select a side-ref as the expected authority."""
    if not re.fullmatch(r'refs/heads/mxm-o04-stage-[0-9]+',ref):return 'NOT_AUTHORIZED'
    try:
        lab.need(state['marker']=='SYNTHETIC_ONLY' and state['root']==ROOT and state['schema_version']==SCHEMA,'ROOT_SCHEMA')
        lab.need(state['source_SHA']==source and state['status']=='ACCEPTED','SOURCE_STATE')
        a=state['accepted'][str(state['version'])];p=a['proposal'];r=p['record']
        lab.need(r['version']==state['version'] and r['generation']==state['generation'] and r['epoch']==state['epoch'],'VERSION_EPOCH')
        lab.need(r['source_SHA']==source and r['root_o04_stop_oid']==STOP and issuer.verify(r,p['signature']),'SIGNATURE_SOURCE')
        for f in ('manifest','ciphertext'):
            lab.need(digest(base64.b64decode(p[f]))==r[f+'_sha256'] and state['evidence'][r[f+'_sha256']]==p[f],'DIGEST')
        # A good fixture signature is NOT a grant of exclusive GitHub authority.
        return 'DRY_RUN_VALID_SYNTHETIC_PRINCIPAL_ISOLATION_UNVERIFIED'
    except (lab.Denied,KeyError,ValueError,TypeError):return 'QUARANTINED'
