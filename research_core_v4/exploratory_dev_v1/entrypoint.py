"""Installed deny-by-default production gate. No ARM or key is installed here.

The independent auditor must provision the pinned Ed25519 verification key
and sign the one exact live-HEAD payload. An unsigned local JSON cannot arm.
"""
import argparse
import base64
import hashlib
import json
import os
import platform
import importlib.metadata
from pathlib import Path
import resource
import socket
import subprocess
import time
import urllib.request

os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
KEY=Path('/etc/mxm-independent-audit/primary145-ed25519.pub')
REPO='mariancradulescu/mxm-quant-greenfield'
BRANCH='performance-research-v3-20260922'
LIMITS={'accepted_corpus_passes':1,'CPU_seconds':7200,'RAM_bytes':8589934592,
        'broker_requests':0,'protected_forward_rows':0,'orders':0,'trading':0}
_FACTORY=object()

def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':')).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def require(ok,why):
    if not ok:raise ValueError(why)

def live_head():
    url='https://api.github.com/repos/'+REPO+'/branches/'+BRANCH
    with urllib.request.urlopen(urllib.request.Request(url,headers={'Accept':'application/vnd.github+json'}),timeout=30) as f:
        return json.load(f)['commit']['sha']

def validate_payload(payload, local_head, remote_head, hashes):
    require(payload.get('schema')=='mxm.primary145.single-exploratory-arm.v1','ARM_SCHEMA')
    require(payload.get('independent_preexecution_audit')=='APPROVED','INDEPENDENT_AUDIT')
    require(payload.get('execution_head')==local_head==remote_head,'LIVE_HEAD_DRIFT')
    require(payload.get('repository')==REPO and payload.get('branch')==BRANCH,'ARM_REPO')
    require(payload.get('campaign')=='PRIMARY145_EXPLORATORY_DEV_V1_SINGLE_PASS','ARM_CAMPAIGN')
    require(payload.get('inference_class')=='EXPLORATORY_ONLY_NO_FORMAL_REJECTION','ARM_CLAIM')
    require(payload.get('limits')==LIMITS,'ARM_LIMITS')
    require(payload.get('files_sha256')==hashes,'ARM_HASH_SCOPE')
    for key in ('archive_directory','checkpoint_directory','output_file'):
        p=Path(payload.get(key,''));require(p.is_absolute() and '..' not in p.parts,'ARM_PATH')
    return True

class Permit:
    def __init__(self,payload,arm_digest,_factory=None):
        require(_factory is _FACTORY,'SIGNED_GATE_CAPABILITY_REQUIRED')
        self.payload=payload;self.arm_digest=arm_digest;self.started=time.process_time()
    def check(self):
        require(time.process_time()-self.started<7200,'CPU_LIMIT')
        require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==self.payload['execution_head'],'LOCAL_HEAD_DRIFT')

def verify_signature(key_bytes,envelope):
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    key=load_pem_public_key(key_bytes);require(isinstance(key,Ed25519PublicKey),'KEY_TYPE')
    key.verify(base64.b64decode(envelope['signature_base64'],validate=True),canonical(envelope['payload']))

def reserve_invocation(payload):
    cp=Path(payload['checkpoint_directory']);cp.mkdir(parents=True,exist_ok=True)
    with (cp/'INVOCATION_CONSUMED.json').open('x') as f:
        json.dump({'arm_digest':sha(canonical(payload)),'CPU_budget_reserved_seconds':7200},f)

def authorize(envelope_path):
    require(KEY.is_file(),'INDEPENDENT_VERIFICATION_KEY_NOT_INSTALLED')
    require(KEY.stat().st_uid==0 and KEY.stat().st_mode&0o022==0,'INDEPENDENT_KEY_PERMISSIONS')
    envelope=json.loads(Path(envelope_path).read_bytes());payload=envelope['payload']
    verify_signature(KEY.read_bytes(),envelope)
    runtime=json.loads((HERE/'DESIGN_FREEZE_V1.json').read_bytes())['runtime']
    require(platform.python_version()==runtime['python'],'PYTHON_RUNTIME_DRIFT')
    for package in ('numpy','cryptography'):
        require(importlib.metadata.version(package)==runtime[package],'PACKAGE_RUNTIME_DRIFT:'+package)
    delivery=json.loads((HERE/'DELIVERY_MANIFEST_V1.json').read_bytes())
    hashes=dict(delivery['files_sha256'])
    hashes['research_core_v4/exploratory_dev_v1/DELIVERY_MANIFEST_V1.json']=sha((HERE/'DELIVERY_MANIFEST_V1.json').read_bytes())
    # Include every inherited scientific dependency, not only new code.
    hashes.update(json.loads((HERE/'RECONCILIATION_AND_CORPUS_V1.json').read_bytes())['frozen_authorities_verified_sha256'])
    for p,h in hashes.items():require(sha((ROOT/p).read_bytes())==h,'FROZEN_FILE_DRIFT:'+p)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    require(not subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT),'DIRTY_TREE')
    validate_payload(payload,head,live_head(),hashes)
    require(not Path(payload['output_file']).exists(),'OUTPUT_ALREADY_EXISTS')
    resource.setrlimit(resource.RLIMIT_CPU,(7200,7200))
    resource.setrlimit(resource.RLIMIT_AS,(8589934592,8589934592))
    # After the one live metadata check, every networking route is denied.
    def denied(*a,**k):raise RuntimeError('NETWORK_DISABLED_AFTER_GATE')
    socket.socket=denied;socket.create_connection=denied
    # One invocation per signed campaign, independent of checkpoint recovery.
    reserve_invocation(payload)
    return Permit(payload,sha(canonical(payload)),_FACTORY)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--independent-signed-arm',required=True)
    args=parser.parse_args();permit=authorize(args.independent_signed_arm)
    from .worker import read_production,evaluate,atomic_json
    p=permit.payload
    caches,ids=read_production(p['archive_directory'],p['checkpoint_directory'],permit)
    permit.check();report=evaluate(caches,ids);permit.check()
    report['authorization_payload_sha256']=permit.arm_digest
    report['execution_head']=p['execution_head'];report['CPU_seconds']=time.process_time()-permit.started
    report['max_RSS_KiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report['broker_requests']=0;report['protected_forward_rows']=0;report['orders']=0
    report['parsed_corpus_passes']=1
    atomic_json(Path(p['output_file']),report)

if __name__=='__main__':main()
