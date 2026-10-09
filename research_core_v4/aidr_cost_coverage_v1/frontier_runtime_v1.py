"""Exact owner-authorized bounded research runtime; encrypted delivery only."""
import gzip,json,os,pathlib,tempfile,re
from research_core_v4.aidr_cost_coverage_v1 import execute_owner_coverage_v1 as e
from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob,ROOT as PUB
P='research_core_v4/owner_frontier_v1/'

def gate(kind):
    head=os.environ['GITHUB_SHA'];e.w.v2.runtime(head);auth=json.loads((e.a.ROOT/(P+'OWNER_BOUNDED_RESEARCH_V1.json')).read_text())
    e.w.old.need(auth['authority']=='EXPLICIT_OWNER_AUTONOMOUS_EMPIRICAL_RESEARCH' and auth['independent_acceptance_claimed'] is False and auth['orders'] is False and auth['protected_forward'] is False,'OWNER_FRONTIER_AUTHORITY')
    e.a.ancestor(auth['base_head'],head)
    for p,h in auth['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'FRONTIER_SOURCE_DRIFT')
    existing=json.loads((e.a.ROOT/(e.P+'EXACT_COVERAGE_PREARM_V1.json')).read_text())
    for p,h in existing['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'ORIGINAL_SOURCE_DRIFT')
    claim='mxm-owner-frontier-'+kind+'-'+auth['invocation_id']
    e.w.old.need(not e.w.v2.existing_ref(claim),'FRONTIER_INVOCATION_CONSUMED')
    e.w.old.api('git/refs',{'ref':'refs/tags/'+claim,'sha':head})
    master,entries,digits,manifest=e.w.old.verify_science()
    return head,auth,master,entries,digits,manifest

def output(head,auth,tmp,key,kind,full,summary):
    # Canonical JSON roundtrip avoids tuple/list receipt mismatch.
    full=e.w.old.crypto.strict_json(e.a.enc(full));summary=e.w.old.crypto.strict_json(e.a.enc(summary))
    out=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real')
    path=PUB+'OWNER_'+kind.upper()+'_RESEARCH_V1.json'
    status={'schema':e.w.SCHEMA,'source_head':head,'phase':'PUBLICATION','status':'NOT_PERSISTED','failure_code':'NONE','run_id':int(os.environ['GITHUB_RUN_ID'])}
    out.release=e.w.old.api('releases',{'tag_name':'mxm-owner-frontier-'+kind+'-'+auth['invocation_id'][:12]+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted bounded '+kind+' research','prerelease':True,'body':validate_public_blob(path,status).decode()})
    primary=out.encrypted(full,kind+'-private-result.mxmenc');summary.update(durable_primary=primary,source_head=head,run_id=int(os.environ['GITHUB_RUN_ID']))
    delivered=e.upload_extra(out.release,tmp,e.a.ROOT/(e.P+'DELIVERY_PUBLIC_KEY.pem'),summary,kind+'-private-delivery.mxmenc')
    attestation=out.encrypted({'schema':'mxm.owner.frontier.attestation.v1','primary':primary,'delivery':delivered,'summary':summary,'resources':e.w.old.usage(),'independent_acceptance_claimed':False},kind+'-attestation.mxmenc')
    status.update(phase='FINAL',status='PASS',encrypted_artifact_name=attestation['name'],encrypted_artifact_sha256=attestation['ciphertext_sha256'])
    body=validate_public_blob(path,status);e.w.old.api('releases/'+str(out.release['id']),{'body':body.decode()},method='PATCH')
    e.w.old.need(e.w.old.api('releases/'+str(out.release['id']))['body'].encode()==body,'FRONTIER_RELEASE_READBACK')
    e.w.old.api('git/refs',{'ref':'refs/tags/mxm-owner-frontier-complete-'+kind+'-'+auth['invocation_id'],'sha':head})
    print(body.decode().strip(),flush=True)

def fail(exc,phase):
    code=str(exc) if isinstance(exc,e.w.n.NumericalStop) and re.fullmatch('[A-Z][A-Z0-9_]{0,80}',str(exc)) else type(exc).__name__
    print('FAIL_CLOSED_FRONTIER_'+phase+'_'+code,flush=True)
