"""Recover already encrypted owner result only; never rerun intersection."""
import base64,gzip,json,os,pathlib,tempfile,re
from research_core_v4.aidr_cost_coverage_v1 import execute_owner_coverage_v1 as e
from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob
P=e.P
PHASE='GATE'

def main():
    global PHASE
    os.umask(0o077);head=os.environ['GITHUB_SHA'];e.w.v2.runtime(head)
    auth=json.loads((e.a.ROOT/(P+'OWNER_DELIVERY_RECOVERY_V1.json')).read_text());mandate=json.loads((e.a.ROOT/(P+'OWNER_EXECUTION_MANDATE_V1.json')).read_text())
    e.w.old.need(auth['authority']=='EXPLICIT_OWNER_ROUTINE_ENGINEERING_AND_RECOVERY' and auth['intersection_replayed'] is False,'RECOVERY_AUTHORITY')
    for p,h in auth['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'RECOVERY_SOURCE_DRIFT')
    for p,h in json.loads((e.a.ROOT/(P+'EXACT_COVERAGE_PREARM_V1.json')).read_text())['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'ORIGINAL_SOURCE_DRIFT')
    e.w.old.need(e.w.old.api('git/ref/heads/'+e.w.old.BRANCH)['object']['sha']==head,'LIVE_HEAD_DRIFT')
    claim=e.w.v2.existing_ref('mxm-owner-cost-coverage-'+mandate['invocation_id']);e.w.old.need(len(claim)==1 and claim[0]['object']['sha']==auth['original_head'],'ORIGINAL_CLAIM')
    run=e.w.old.api('actions/runs/'+str(auth['original_run']));e.w.old.need(run['head_sha']==auth['original_head'] and run['conclusion']=='failure','ORIGINAL_RUN')
    e.w.old.need(not e.w.v2.existing_ref('mxm-owner-delivery-recovery-'+auth['invocation_id']),'RECOVERY_CONSUMED')
    e.w.old.api('git/refs',{'ref':'refs/tags/mxm-owner-delivery-recovery-'+auth['invocation_id'],'sha':head})
    with tempfile.TemporaryDirectory(prefix='mxm-owner-delivery-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);e.w.old.need(fp==e.w.old.FP,'KEY_BINDING')
        PHASE='PRIMARY_READBACK'
        release=e.w.old.api('releases/'+str(auth['release_id']));e.w.old.need(release['target_commitish']==auth['original_head'],'RELEASE_BINDING')
        assets=e.w.old.api('releases/'+str(release['id'])+'/assets?per_page=100');asset=next(x for x in assets if x['id']==auth['asset_id'])
        e.w.old.need(asset['name']=='owner-exact-cost-coverage.mxmenc' and asset['digest']=='sha256:'+auth['ciphertext_sha256'],'PRIMARY_CIPHER_BINDING')
        blob=e.w.old.download(asset['browser_download_url'],asset['size']);e.w.old.need(e.a.sha(blob)==auth['ciphertext_sha256'],'PRIMARY_CIPHER_READBACK')
        packed=e.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
        raw=gzip.decompress(packed);value=e.w.old.crypto.strict_json(raw);e.w.old.need(e.a.enc(value)==raw,'PRIMARY_CANONICAL_READBACK')
        summary=value['summary'];result=value['private_event_coverage']
        e.w.old.need(summary['source_head']==auth['original_head'] and summary['run_id']==auth['original_run'] and summary['original_counts_reconciled'] is True and len(result['records'])==4205 and summary['event_counts']=={'emitted':4205,'supported':3321,'label_gap':884},'RESULT_BINDING')
        full={'id':asset['id'],'name':asset['name'],'size':asset['size'],'ciphertext_sha256':auth['ciphertext_sha256'],'canonical_sha256':e.a.sha(raw),'gzip_sha256':e.a.sha(packed),'url':asset['browser_download_url']}
        summary['durable_private_coverage']=full;summary['recovery_head']=head;summary['recovery_run']=int(os.environ['GITHUB_RUN_ID']);summary['intersection_replayed']=False
        PHASE='PRIVATE_DELIVERY'
        delivery=e.upload_extra(release,tmp,e.a.ROOT/(P+'DELIVERY_PUBLIC_KEY.pem'),summary,'owner-private-delivery.mxmenc')
        PHASE='ATTESTATION'
        out=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');out.release=release
        meta=out.encrypted({'schema':'mxm.owner.coverage.delivery.attestation.v1','summary':summary,'delivery':delivery,'full_private_coverage':full,'resources':e.w.old.usage(),'independent_acceptance_claimed':False,'intersection_replayed':False},'owner-coverage-attestation.mxmenc')
        PHASE='PUBLICATION'
        status={'schema':e.w.SCHEMA,'source_head':head,'phase':'FINAL','status':'PASS','failure_code':'NONE','run_id':int(os.environ['GITHUB_RUN_ID']),'encrypted_artifact_name':meta['name'],'encrypted_artifact_sha256':meta['ciphertext_sha256']}
        final=e.publish(out,status)
        e.w.old.api('git/refs',{'ref':'refs/tags/mxm-owner-cost-coverage-complete-'+mandate['invocation_id'],'sha':final})
        e.w.old.need(e.w.old.api('git/ref/tags/mxm-owner-cost-coverage-complete-'+mandate['invocation_id'])['object']['sha']==final,'COMPLETION_READBACK')
        print(validate_public_blob(e.STATUS,status).decode().strip(),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        code=str(exc) if isinstance(exc,e.w.n.NumericalStop) and re.fullmatch('[A-Z][A-Z0-9_]{0,80}',str(exc)) else type(exc).__name__
        print('FAIL_CLOSED_OWNER_RECOVERY_'+PHASE+'_'+code,flush=True);raise SystemExit(2) from None
