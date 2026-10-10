"""Owner-authorized recovery/new DEVELOPMENT; existing crypto and output guard."""
import json,os,pathlib,tempfile
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
e=rt.e
P='research_core_v4/owner_recovery_v1/'

def gate(kind):
    head=os.environ['GITHUB_SHA'];e.w.v2.runtime(head)
    auth=json.loads((e.a.ROOT/(P+'OWNER_RECOVERY_EXECUTION_V1.json')).read_text())
    e.w.old.need(auth['authority']=='EXPLICIT_OWNER_RECOVERY_AND_AUTONOMOUS_RESEARCH_20261010' and not auth['orders'] and not auth['protected_forward'] and not auth['independent_acceptance_claimed'],'OWNER_RECOVERY_SCOPE')
    e.w.old.need(os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-owner-recovery-research-v1.yml@refs/heads/'+e.w.old.BRANCH,'RECOVERY_WORKFLOW_SCOPE')
    from datetime import datetime,timezone
    e.w.old.need(datetime.now(timezone.utc).isoformat()<auth['expires_utc'],'RECOVERY_EXPIRED')
    e.a.ancestor(auth['base_head'],head)
    for p,h in auth['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'RECOVERY_SOURCE_DRIFT')
    original=json.loads((e.a.ROOT/(e.P+'EXACT_COVERAGE_PREARM_V1.json')).read_text())
    for p,h in original['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'ORIGINAL_SOURCE_DRIFT')
    e.w.old.verify_science()
    claim='mxm-owner-recovery-'+kind+'-'+auth['invocation_id']
    e.w.old.need(not e.w.v2.existing_ref(claim),'RECOVERY_CONSUMED')
    e.w.old.api('git/refs',{'ref':'refs/tags/'+claim,'sha':head})
    return head,auth

def load_asset(key,fp,tmp,binding):
    import gzip
    assets=e.w.old.api('releases/'+str(binding['release_id'])+'/assets?per_page=100')
    asset=next(x for x in assets if x['id']==binding['asset_id'])
    e.w.old.need(asset['digest']=='sha256:'+binding['ciphertext_sha256'],'RECOVERY_ASSET_METADATA')
    blob=e.w.old.download(asset['browser_download_url'],asset['size'])
    e.w.old.need(e.a.sha(blob)==binding['ciphertext_sha256'],'RECOVERY_CIPHER_BYTES')
    packed=e.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
    raw=gzip.decompress(packed);value=e.w.old.crypto.strict_json(raw)
    e.w.old.need(e.a.enc(value)==raw,'RECOVERY_CANONICAL_BYTES')
    if binding.get('canonical_sha256'):e.w.old.need(e.a.sha(raw)==binding['canonical_sha256'],'RECOVERY_PRIMARY_BINDING')
    return value,{'release_id':binding['release_id'],'asset_id':asset['id'],'ciphertext_sha256':e.a.sha(blob),'canonical_sha256':e.a.sha(raw),'gzip_sha256':e.a.sha(packed)}
