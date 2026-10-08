"""V2 operational gate. Scientific V1 code is unchanged and signed in full.
No fixture mode, key installation, signature generation or broker route.
"""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import socket
import subprocess
import time
from research_core_v4.exploratory_dev_v1 import entrypoint as v1

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
KEY=Path('/etc/mxm-independent-audit/primary145-ed25519.pub')
_FACTORY=object()
require=v1.require
sha=v1.sha
canonical=v1.canonical

def signed_scope():
    bindings=HERE/'CODE_BINDINGS_V2.json'
    scope=json.loads(bindings.read_bytes())['files_sha256']
    old=ROOT/'research_core_v4/exploratory_dev_v1'
    inherited=dict(json.loads((old/'DELIVERY_MANIFEST_V1.json').read_bytes())['files_sha256'])
    inherited.update(json.loads((old/'RECONCILIATION_AND_CORPUS_V1.json').read_bytes())['frozen_authorities_verified_sha256'])
    inherited['research_core_v4/exploratory_dev_v1/DELIVERY_MANIFEST_V1.json']=sha((old/'DELIVERY_MANIFEST_V1.json').read_bytes())
    required=set(inherited)
    required.add('research_core_v4/exploratory_dev_v1/DELIVERY_MANIFEST_V1.json')
    required.update(json.loads((old/'RECONCILIATION_AND_CORPUS_V1.json').read_bytes())['frozen_authorities_verified_sha256'])
    required.update('research_core_v4/exploratory_dev_v2/'+p for p in ('gate.py','entrypoint.py','reader.py','HOST_LAYOUT_V2.json'))
    require(set(scope)==required,'DEPENDENCY_SCOPE_INCOMPLETE')
    require(all(scope[p]==h for p,h in inherited.items()),'INHERITED_HASH_BINDING_DRIFT')
    scope=dict(scope);scope['research_core_v4/exploratory_dev_v2/CODE_BINDINGS_V2.json']=sha(bindings.read_bytes())
    for p,h in scope.items():
        require(sha((ROOT/p).read_bytes())==h,'FROZEN_DEPENDENCY_DRIFT:'+p)
    return scope

def runtime_check():
    spec=json.loads((ROOT/'research_core_v4/exploratory_dev_v1/DESIGN_FREEZE_V1.json').read_bytes())['runtime']
    require(platform.python_version()==spec['python'],'PYTHON_RUNTIME_DRIFT')
    for p in ('numpy','cryptography'):
        require(importlib.metadata.version(p)==spec[p],'PACKAGE_RUNTIME_DRIFT:'+p)

def path_check(payload):
    layout=json.loads((HERE/'HOST_LAYOUT_V2.json').read_bytes())['paths']
    for key,expected in layout.items():
        require(payload.get(key)==expected,'EXACT_PATH_SCOPE:'+key)
        p=Path(expected)
        require(p.is_absolute() and '..' not in p.parts and p.resolve()==p,'PATH_SYMLINK_OR_RELATIVE')
    archive=Path(payload['archive_directory']);cp=Path(payload['checkpoint_directory']);out=Path(payload['output_file'])
    require(archive.is_dir(),'ARCHIVE_DIRECTORY_UNAVAILABLE')
    require(cp.parent.is_dir() and out.parent.is_dir(),'PERSISTENT_OUTPUT_PARENT_UNAVAILABLE')
    require(not out.exists(),'OUTPUT_ALREADY_EXISTS')
    return layout

def observable_host(paths):
    devices={};filesystems={}
    for key,path in paths.items():
        p=Path(path);p=p if p.exists() and p.is_dir() else p.parent
        devices[key]=p.stat().st_dev
        f=json.loads(subprocess.check_output(['findmnt','-J','-T',str(p)],text=True))['filesystems'][0]
        filesystems[key]=f['fstype']
    return {'hostname':socket.gethostname(),'devices':devices,'filesystems':filesystems}

def host_check(payload,paths):
    host=payload.get('host_binding',{});observed=observable_host(paths)
    require({k:host.get(k) for k in observed}==observed,'EXECUTION_HOST_DRIFT')
    require(host.get('independent_durability_approved') is True,'DURABILITY_NOT_APPROVED')
    evidence=host.get('durability_evidence_sha256','')
    require(len(evidence)==64 and all(c in '0123456789abcdef' for c in evidence),'DURABILITY_EVIDENCE_NOT_BOUND')
    denied=json.loads((HERE/'HOST_LAYOUT_V2.json').read_bytes())['denied_filesystem_types']
    require(not any(x in denied for x in observed['filesystems'].values()),'EPHEMERAL_FILESYSTEM_DENIED')

def validate(payload,local_head,remote_head,scope):
    require(payload.get('schema')=='mxm.primary145.single-exploratory-arm.v2','ARM_SCHEMA')
    require(payload.get('campaign')=='PRIMARY145_EXPLORATORY_V1_OPERATIONAL_V2_SINGLE_PASS','ARM_CAMPAIGN')
    require(payload.get('independent_preexecution_audit')=='APPROVED','INDEPENDENT_AUDIT')
    require(payload.get('execution_head')==local_head==remote_head,'LIVE_HEAD_DRIFT')
    require(payload.get('repository')==v1.REPO and payload.get('branch')==v1.BRANCH,'ARM_REPO')
    require(payload.get('inference_class')=='EXPLORATORY_ONLY_NO_FORMAL_REJECTION','ARM_CLAIM')
    require(payload.get('limits')==v1.LIMITS,'ARM_LIMITS')
    require(payload.get('files_sha256')==scope,'ARM_HASH_SCOPE')

def durable_json(path,value,exclusive=False):
    path=Path(path)
    if exclusive:
        with path.open('x') as f:
            json.dump(value,f,sort_keys=True,allow_nan=False);f.flush();os.fsync(f.fileno())
    else:
        tmp=path.with_suffix(path.suffix+'.tmp')
        with tmp.open('w') as f:
            json.dump(value,f,sort_keys=True,allow_nan=False);f.flush();os.fsync(f.fileno())
        tmp.replace(path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

class Permit:
    def __init__(self,payload,digest,_factory=None):
        require(_factory is _FACTORY,'SIGNED_GATE_CAPABILITY_REQUIRED')
        self.payload=payload;self.arm_digest=digest;self.started=time.process_time()
    def check(self):
        require(time.process_time()-self.started<7200,'CPU_LIMIT')
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        require(head==self.payload['execution_head'],'LOCAL_HEAD_DRIFT')

def authorize(envelope_path):
    require(KEY.is_file() and not KEY.is_symlink(),'INDEPENDENT_VERIFICATION_KEY_NOT_INSTALLED')
    require(KEY.stat().st_uid==0 and KEY.stat().st_mode&0o022==0,'INDEPENDENT_KEY_PERMISSIONS')
    envelope=json.loads(Path(envelope_path).read_bytes());payload=envelope['payload']
    v1.verify_signature(KEY.read_bytes(),envelope)
    scope=signed_scope();runtime_check()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    require(not subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT),'DIRTY_TREE')
    validate(payload,head,v1.live_head(),scope)
    paths=path_check(payload);host_check(payload,paths)
    # This reserves the total budget, not a new budget for each restart.
    cp=Path(payload['checkpoint_directory']);cp.mkdir(exist_ok=True)
    digest=sha(canonical(payload))
    durable_json(cp/'INVOCATION_CONSUMED.json',{'arm_digest':digest,'CPU_seconds_reserved':7200},exclusive=True)
    resource.setrlimit(resource.RLIMIT_CPU,(7200,7200))
    resource.setrlimit(resource.RLIMIT_AS,(8589934592,8589934592))
    def denied(*args,**kwargs):raise RuntimeError('NETWORK_DISABLED_AFTER_GATE')
    socket.socket=denied;socket.create_connection=denied
    return Permit(payload,digest,_FACTORY)
