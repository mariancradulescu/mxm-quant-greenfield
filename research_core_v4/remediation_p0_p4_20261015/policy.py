"""Successor acceptance gates; no inherited historical authority."""
import hashlib
import json
import pathlib
import re
import zipfile
from .safety import require

def workflow_guard(root):
    catalog=json.loads((root/'research_core_v4/remediation_p0_p4_20261015/workflow_catalog.json').read_text())
    actual={p.relative_to(root).as_posix() for p in (root/'.github/workflows').glob('*') if p.suffix in ('.yml','.yaml')}
    expected={r['path'] for r in catalog['workflows']}
    require(actual==expected|{'.github/workflows/mxm-remediation-p0-p4-20261015-v1.yml'},'WORKFLOW_CATALOG_INCOMPLETE')
    import yaml
    class UniqueLoader(yaml.BaseLoader):pass
    def unique(loader,node):
        result={}
        for key,value in node.value:
            k=loader.construct_object(key)
            require(k not in result,'DUPLICATE_YAML_KEY')
            result[k]=loader.construct_object(value)
        return result
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,unique)
    for path in actual:
        obj=yaml.load((root/path).read_text(),Loader=UniqueLoader)
        require(isinstance(obj,dict) and 'jobs' in obj and 'on' in obj,'WORKFLOW_SCHEMA')
        for job in obj['jobs'].values():require('timeout-minutes' in job and ('runs-on' in job or 'uses' in job),'JOB_TIMEOUT_OR_RUNNER')
    for p in expected:
        text=(root/p).read_text()
        require('if: ${{ false }}' in text and 'permissions: {}' in text and 'timeout-minutes: 1' in text,'LEGACY_ACTIVATION_DENIED')
        require('secrets.' not in text and 'uses:' not in text and 'push:' not in text,'LEGACY_CAPABILITY_DENIED')
    active=(root/'.github/workflows/mxm-remediation-p0-p4-20261015-v1.yml').read_text()
    for use in re.findall(r'uses:\s*([^\s]+)',active):require(bool(re.fullmatch(r'[^@]+@[0-9a-f]{40}',use)),'MUTABLE_ACTION_DENIED')
    require('--require-hashes' in active and 'CTRADER_' not in active and 'contents: read' in active,'ACTIVE_SCOPE_DENIED')
    return {'legacy_inert':len(expected),'active_remediation_only':1,'scope':'SUCCESSOR_ONLY'}

def independent_acceptance(receipt,producer,expected_scope,now,trusted_keys=None):
    from .safety import canonical
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    require(trusted_keys is not None,'INDEPENDENT_TRUST_ROOT_REQUIRED')
    principal=receipt.get('principal')
    require(principal and principal!=producer,'SAME_PRINCIPAL_DENIED')
    require(principal in trusted_keys,'UNTRUSTED_AUDITOR_KEY')
    payload={k:receipt.get(k) for k in ('principal','scope','expires','nonce')}
    require(payload['scope']==expected_scope and payload['expires']>now and bool(payload['nonce']),'AUDIT_SCOPE_OR_EXPIRY')
    try:Ed25519PublicKey.from_public_bytes(trusted_keys[principal]).verify(base64.b64decode(receipt['signature'],validate=True),canonical(payload))
    except Exception:raise ValueError('INDEPENDENT_SIGNATURE_REQUIRED') from None
    return True

def classify_job(job):
    if not job.get('log_sha256'):return 'UNKNOWN_LOG_UNAVAILABLE'
    if job.get('exact_policy_code')=='EXPECTED_POLICY_STOP' and job.get('source_binding_valid') is True:return 'EXPECTED_POLICY_STOP'
    if job.get('build_error'):return 'DEFECT'
    return 'UNKNOWN_REQUIRES_EXACT_SOURCE_LOG'

def packaging(directory,expected):
    actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    require(actual==set(expected),'PACKAGE_EXACT_PATHS')
    for name,h in expected.items():
        p=directory/name;require(p.stat().st_size>0 and hashlib.sha256(p.read_bytes()).hexdigest()==h,'PACKAGE_DIGEST_OR_EMPTY')
    return {'state':'PACKAGE_READY_ONLY','cloud_executed':False,'NET':None}
