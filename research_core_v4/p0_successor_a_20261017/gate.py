"""Native human critical gate. GET only; no approval endpoint or impersonation."""
import json, os, pathlib, time
from .publisher import *
AUDIT_SOURCE='f1bc26280fab95b8fd083b032cb272c543aaa93b'

def plan():
    need(os.environ['GITHUB_REF']=='refs/heads/'+SOURCE_BRANCH and os.environ['GITHUB_RUN_ATTEMPT']=='1','GATE_SOURCE')
    source=os.environ['GITHUB_SHA'];now=int(time.time())
    if os.environ.get('SUCCESSOR_BUNDLE'):
        bundle=json.loads(os.environ['SUCCESSOR_BUNDLE'])
        manifest=bundle['manifest'];policy=bundle['policy']
        need(manifest['source_sha']==source and policy['source_sha']==source and
             manifest['critical_operation']=='BOOTSTRAP_AND_DELEGATE' and
             digest(canonical(policy))==manifest['policy_sha256'] and
             digest(canonical(bundle['access']))==policy['access_sha256'] and
             policy['research_go'] is False and manifest['not_before']<=now<manifest['expires_at'],'EXACT_B_PACKAGE')
        return emit(manifest,policy)
    policy={'schema':'mxm.installation-a.v1','source_sha':source,'owner_root':list(OWNER_ROOT),
            'active_ref':ACTIVE_REF,'bootstrap_allowed':False,'write_credentials_bound':False,
            'research_go':False,'scope':'INSTALLATION_RECEPTION_ONLY'}
    manifest={'schema':'mxm.owner-critical-manifest.v2','critical_operation':'INSTALL_PROTECTED_INFRASTRUCTURE',
        'operation_id':'MXM-A-'+os.environ['GITHUB_RUN_ID'],'source_sha':source,
        'policy_sha256':digest(canonical(policy)),
        'audit_reception_sha256':digest(canonical({'owner_confirmed_reception_head':AUDIT_SOURCE,
                                                  'provenance':'OWNER_CONVERSATION'})),
        'owner_root_oid':OWNER_ROOT[1],'not_before':now,'expires_at':now+86400}
    return emit(manifest,policy)

def emit(manifest,policy):
    folder=pathlib.Path('verification/successor-a');folder.mkdir(parents=True,exist_ok=True)
    raw=canonical(manifest);(folder/'critical-manifest.json').write_bytes(raw)
    (folder/'installation-policy.json').write_bytes(canonical(policy))
    h=digest(raw)
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:
        f.write('manifest='+raw.decode()+'\nhash='+h+'\n')
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
        f.write('A INSTALLATION ONLY, NO BOOTSTRAP.\n\n```json\n'+raw.decode()+'\n```\n\n')
        f.write('OWNER alone may explicitly review with exact comment:\n\n`MXM_OWNER_CRITICAL_APPROVAL_V2 sha256='+h+'`\n')
    return manifest

def verify():
    manifest=json.loads(os.environ['CRITICAL_MANIFEST']);now=int(time.time())
    need(manifest['not_before']<=now<manifest['expires_at'],'MANIFEST_EXPIRED')
    binding=GateBinding(int(os.environ['GITHUB_RUN_ID']),GATE_ENV_ID,GATE_ENV,os.environ['GITHUB_SHA'],PATH,digest(canonical(manifest)))
    result=verify_owner_review(GitHubReadOnly(),binding,manifest)
    need(manifest['critical_operation'] in ('INSTALL_PROTECTED_INFRASTRUCTURE','BOOTSTRAP_AND_DELEGATE'),'CRITICAL_SCOPE')
    print(json.dumps({'native_review':result,'bootstrap':False,'token_issuance':False,'research_go':False}))

if __name__=='__main__':
    import sys
    {'plan':plan,'verify':verify}[sys.argv[1]]()
