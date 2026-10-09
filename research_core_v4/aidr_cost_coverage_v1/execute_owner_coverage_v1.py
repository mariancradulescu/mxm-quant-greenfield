"""Owner-authorized private coverage reader. No scientific replay or broker calls.

The owner mandate is distinct from independent scientific acceptance. Original
one-use approvals remain untouched and consumed. Public output is allowlisted.
"""
import base64,gzip,hashlib,json,os,pathlib,subprocess,tempfile,urllib.request
from collections import Counter
from research_core_v4.diverse_mechanism_wave_v2 import authority_v2 as a,worker_v2 as w
from research_core_v4.aidr_locator_v1 import discover_existing_v1 as d,extract_locators_v1 as extraction
from research_core_v4.aidr_cost_coverage_v1.coverage_kernel_v1 import intersect,CATEGORIES
from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob,ROOT as PUB
P='research_core_v4/aidr_cost_coverage_v1/'
WORKFLOW='.github/workflows/mxm-owner-existing-cost-coverage-v1.yml'
STATUS=PUB+'OWNER_EXISTING_COST_COVERAGE_V1.json'

def gate():
    head=os.environ['GITHUB_SHA'];w.v2.runtime(head)
    w.old.need(os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_WORKFLOW_REF')==w.old.REPO+'/'+WORKFLOW+'@refs/heads/'+w.old.BRANCH,'OWNER_EVENT_SCOPE')
    mandate=json.loads((a.ROOT/(P+'OWNER_EXECUTION_MANDATE_V1.json')).read_text())
    w.old.need(mandate['authority']=='EXPLICIT_OWNER_MESSAGE_2026_10_09_EXECUTE_NOW' and mandate['independent_acceptance_claimed'] is False and mandate['scope']=={'read_existing_locators':True,'exact_existing_cost_availability_intersection':True,'original_scientific_replay':False,'broker_requests':0,'protected_forward':False,'orders':False},'OWNER_SCOPE')
    a.ancestor(mandate['base_head'],head)
    for p,h in mandate['bindings'].items():w.old.need(w.old.filehash(p)==h,'OWNER_SOURCE_DRIFT')
    existing=json.loads((a.ROOT/(P+'EXACT_COVERAGE_PREARM_V1.json')).read_text())
    for p,h in existing['bindings'].items():w.old.need(w.old.filehash(p)==h,'ORIGINAL_FROZEN_SOURCE_DRIFT')
    w.old.need(w.old.api('git/ref/heads/'+w.old.BRANCH)['object']['sha']==head,'LIVE_HEAD_DRIFT')
    w.old.need(not w.v2.existing_ref('mxm-owner-cost-coverage-'+mandate['invocation_id']),'OWNER_INVOCATION_CONSUMED')
    original=a.read(a.ARM)
    w.old.need(a.digest(a.ARM)==d.ARM_SHA and a.digest(a.APPROVAL)==d.APPROVAL_SHA,'ORIGINAL_AUTHORITY_DRIFT')
    refs=w.v2.existing_ref('mxm-numeric-v3-complete-real-'+original['invocation_id'])
    w.old.need(len(refs)==1 and refs[0]['object']['sha']==d.COMPLETION,'ORIGINAL_COMPLETION_REF')
    run=w.old.api('actions/runs/'+str(existing['locator']['run_id']))
    w.old.need(run['conclusion']=='success' and run['head_sha']==existing['locator']['source_head'] and run['run_attempt']==1,'LOCATOR_ORIGINAL_RUN')
    w.old.verify_science()
    return head,mandate,existing,original

def upload_extra(release,tmp,public,value,name):
    raw=a.enc(value);dest=tmp/name
    w.old.encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=dest)
    blob=dest.read_bytes()
    request=urllib.request.Request('https://uploads.github.com/repos/'+w.old.REPO+'/releases/'+str(release['id'])+'/assets?name='+name,data=blob,method='POST',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Content-Type':'application/octet-stream','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=90) as resp:asset=json.load(resp)
    w.old.need(asset['digest']=='sha256:'+a.sha(blob) and asset['size']==len(blob),'DELIVERY_METADATA')
    got=w.old.download(asset['browser_download_url'],len(blob));w.old.need(got==blob,'DELIVERY_CIPHERTEXT_READBACK')
    return {'name':name,'id':asset['id'],'ciphertext_sha256':a.sha(blob),'canonical_sha256':a.sha(raw),'size':len(blob)}

def publish(out,document):
    raw=validate_public_blob(STATUS,document)
    current=w.old.api('git/ref/heads/'+w.old.BRANCH)['object']['sha'];w.old.need(current==out.head,'PUBLICATION_HEAD_DRIFT')
    blob=w.old.api('git/blobs',{'content':base64.b64encode(raw).decode(),'encoding':'base64'})
    tree=w.old.api('git/trees',{'base_tree':w.old.api('git/commits/'+current)['tree']['sha'],'tree':[{'path':STATUS,'mode':'100644','type':'blob','sha':blob['sha']}]})
    commit=w.old.api('git/commits',{'message':'Persist authenticated owner cost coverage evidence [skip ci]','parents':[current],'tree':tree['sha']})
    w.old.need(w.old.api('git/ref/heads/'+w.old.BRANCH)['object']['sha']==current,'PUBLICATION_CAS_DRIFT')
    w.old.api('git/refs/heads/'+w.old.BRANCH,{'sha':commit['sha'],'force':False},method='PATCH')
    w.old.need(base64.b64decode(w.old.api('contents/'+STATUS+'?ref='+commit['sha'])['content'])==raw,'STATUS_READBACK')
    return commit['sha']

def main():
    os.umask(0o077);head,mandate,existing,original=gate()
    w.old.api('git/refs',{'ref':'refs/tags/mxm-owner-cost-coverage-'+mandate['invocation_id'],'sha':head})
    w.install_identity_adapter()
    with tempfile.TemporaryDirectory(prefix='mxm-owner-coverage-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=w.old._private_key_from_secret(tmp);w.old.need(fp==w.old.FP,'PRIVATE_KEY_BINDING')
        cipher=base64.b64decode((a.ROOT/(P+'cost-availability.mxmenc.b64')).read_bytes(),validate=False)
        w.old.need(a.sha(cipher)==mandate['availability_ciphertext_sha256'],'TRANSPORT_CIPHER_DRIFT')
        packed=w.old.crypto.decrypt_package(cipher,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
        raw=gzip.decompress(packed);index=w.old.crypto.strict_json(raw)
        w.old.need(a.enc(index)==raw and a.sha(raw)==existing['normalized_availability_sha256'],'TRANSPORT_CANONICAL_DRIFT')
        store=w.Store(head,key,a.ROOT/w.old.PUBLIC_KEY,tmp,original,d.APPROVAL_SHA,fp)
        store.original_run=d.RUN;store.name=w.v2.release_name(original,d.RUN);store.release=w.old.api('releases/408041914')
        w.old.need(store.release['target_commitish']==d.ORIGINAL,'ORIGINAL_RELEASE_BINDING')
        completion=w.f.verify_complete(store);w.old.need(completion is not None,'ORIGINAL_COMPLETION_BYTES')
        journal,jmeta=store.load_named(w.f.JOURNAL);w.validate_journal(store,journal)
        locstore=w.Store(head,key,a.ROOT/w.old.PUBLIC_KEY,tmp,original,d.APPROVAL_SHA,fp);locstore.release=w.old.api('releases/'+str(existing['locator']['release_id']))
        locators,lmeta=locstore.load_named(existing['locator']['asset_name'],existing['locator']['ciphertext_sha256'])
        w.old.need(locators['schema']=='mxm.aidr.private.event.locators.v1' and locators['source_head']==existing['locator']['source_head'] and locators['prearm_sha256']==existing['original_extraction_prearm_sha256'] and locators['all_original_identity_fixed_week_counts_reconciled'] is True,'LOCATOR_BINDING')
        extraction.reconcile(locators['events'],journal['report'])
        expected={}
        for identity in journal['report']['identity_results']:
            for week in range(4):
                original_counts=identity['four_weeks'][week]['0'][extraction.MECHANISM]['reasons']
                for support in ('SUPPORTED','LABEL_GAP'):
                    if original_counts[support]:expected[(identity['ordinal'],week,support)]=original_counts[support]
        result=intersect(locators['events'],index,expected)
        master=w.old.verify_science()[0];source_symbols={s['symbol_id'] for s in index['sources']}
        summary={'schema':'mxm.owner.private.coverage.summary.v1','source_head':head,'run_id':int(os.environ['GITHUB_RUN_ID']),'original_completion':completion,'locator':lmeta,'transport_plaintext_sha256':a.sha(raw),'transport_ciphertext_sha256':a.sha(cipher),'original_counts_reconciled':True,'source_sha256':index['source_sha256'],'event_counts':{'emitted':len(result['records']),'supported':sum(e['response_support_status']=='SUPPORTED' for e in locators['events']),'label_gap':sum(e['response_support_status']=='LABEL_GAP' for e in locators['events'])},'category_week_support_counts':result['category_week_support_counts'],'category_totals':{cat:sum(r['coverage']['category']==cat for r in result['records']) for cat in CATEGORIES},'all1576_identity_four_week_counts':[{'ordinal':i+1,'symbol_id':m['symbol_id'],'symbol':m['symbol'],'weeks':[{'emitted':sum(expected.get((i+1,week,s),0) for s in ('SUPPORTED','LABEL_GAP')),'supported':expected.get((i+1,week,'SUPPORTED'),0),'label_gap':expected.get((i+1,week,'LABEL_GAP'),0),'categories':{cat:sum(r['event']['ordinal']==i+1 and r['event']['fixed_week']==week and r['coverage']['category']==cat for r in result['records']) for cat in CATEGORIES}} for week in range(4)]} for i,m in enumerate(master)],'source_symbols_in_master':sorted(source_symbols&{m['symbol_id'] for m in master}),'source_symbols_outside_master':sorted(source_symbols-{m['symbol_id'] for m in master}),'unresolved_cost_semantics_overlay':len(result['records']),'cohort_net_headroom_established':False,'executed_trades':0,'protected_forward':False,'scientific_replay':False,'original_wave_full_frontier':journal['report']['full_frontier'],'original_wave_four_weeks':journal['report']['four_weeks'],'credential_presence':{name:bool(os.environ.get(name)) for name in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN','CTRADER_REFRESH_TOKEN','CTRADER_EXPECTED_ACCOUNT_ID')},'broker_requests':0}
        out=w.old.GitHubStore(head,key,a.ROOT/w.old.PUBLIC_KEY,tmp,'real')
        status={'schema':w.SCHEMA,'source_head':head,'phase':'PUBLICATION','status':'NOT_PERSISTED','failure_code':'NONE','run_id':int(os.environ['GITHUB_RUN_ID'])}
        out.release=w.old.api('releases',{'tag_name':'mxm-owner-cost-coverage-'+mandate['invocation_id'][:12]+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM authenticated encrypted existing cost coverage','prerelease':True,'body':validate_public_blob(STATUS,status).decode()})
        full=out.encrypted({'summary':summary,'private_event_coverage':result},'owner-exact-cost-coverage.mxmenc')
        summary['durable_private_coverage']=full
        delivery=upload_extra(out.release,tmp,a.ROOT/(P+'DELIVERY_PUBLIC_KEY.pem'),summary,'owner-private-delivery.mxmenc')
        attestation=out.encrypted({'schema':'mxm.owner.coverage.delivery.attestation.v1','summary':summary,'delivery':delivery,'full_private_coverage':full,'resources':w.old.usage(),'independent_acceptance_claimed':False},'owner-coverage-attestation.mxmenc')
        status.update(status='PASS',phase='FINAL',encrypted_artifact_name=attestation['name'],encrypted_artifact_sha256=attestation['ciphertext_sha256'])
        w.old.budget(maxwall=900,maxcpu=600,maxkib=2097152)
        final=publish(out,status)
        w.old.api('git/refs',{'ref':'refs/tags/mxm-owner-cost-coverage-complete-'+mandate['invocation_id'],'sha':final})
        w.old.need(w.old.api('git/ref/tags/mxm-owner-cost-coverage-complete-'+mandate['invocation_id'])['object']['sha']==final,'COMPLETION_REF_READBACK')
        print(validate_public_blob(STATUS,status).decode().strip(),flush=True)

if __name__=='__main__':
    try:
        if os.sys.argv[1:]==['--preflight']:gate();print('PASS_OWNER_SCOPED_SOURCE_GATE')
        elif not os.sys.argv[1:]:main()
        else:raise RuntimeError()
    except Exception:
        print('FAIL_CLOSED_OWNER_EXISTING_COST_COVERAGE',flush=True);raise SystemExit(2) from None
