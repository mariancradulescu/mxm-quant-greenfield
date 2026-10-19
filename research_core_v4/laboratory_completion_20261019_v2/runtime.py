"""GET-only, finite, encrypted cross-runner continuation anchored to terminal C V3."""
import base64,gzip,io,json,os,re,subprocess,tempfile,urllib.request,zipfile
from pathlib import Path
from datetime import datetime
from .analysis import need,recover_targets,pair_frontier,admission,quote_index
from research_core_v4.successor_c_20261018 import readback as old
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015.control import lookup
from research_core_v4.remediation_p0_p4_20261015.safety import sha,strict_json,unpack
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'research_core_v4/laboratory_completion_20261019_v2'
OUT=ROOT/'verification/laboratory-completion'
ACTIVE='07d1ddbe0b83753bbf189770af1911623fef8d6f'
BRANCH='mxm-o04-successor-code-lab-v5r1'


def source_admission(head,expected,branch_head,rule):
    need(re.fullmatch(r'[0-9a-f]{40}',expected) and head==expected and branch_head==expected,'IMMUTABLE_SOURCE_PIN')
    need(rule['id']==25222248 and rule['enforcement']=='active'
         and rule['conditions']['ref_name']=={'include':['refs/heads/mxm-o04-*'],'exclude':[]}
         and {r['type'] for r in rule['rules']}=={'deletion','non_fast_forward','required_linear_history'}
         and ('bypass_actors' not in rule or rule['bypass_actors']==[])
         and datetime.fromisoformat(rule['updated_at'].replace('Z','+00:00')).timestamp()==
             datetime.fromisoformat('2026-10-16T08:41:41.359+02:00').timestamp(),'EXISTING_APPEND_ONLY_FENCE')

def anchors(route):
    old.owner_unchanged(route)
    need(route.json('git/ref/heads/mxm-o04-active-v1')['object']['sha']==ACTIVE,'AUTHORITY_MOVED')
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip()
    source_admission(head,os.environ['LAB_SOURCE_SHA'],
        route.json('git/ref/heads/'+BRANCH)['object']['sha'],route.json('rulesets/25222248'))


def read_binding(route,binding,key,tmp):
    aid=binding.get('asset_id',binding.get('id'))
    asset=lookup(route.json,binding['release_id'],aid,binding['ciphertext_sha256'])
    need(asset['size']<=128*1024*1024,'SOURCE_SIZE')
    with route.open(asset['browser_download_url']) as response: blob=response.read(asset['size']+1)
    need(len(blob)==asset['size'] and sha(blob)==binding['ciphertext_sha256'],'SOURCE_DIGEST')
    packed=owner.bounded_decrypt(blob,key,tmp);raw=unpack(packed)
    if binding.get('gzip_sha256'):need(sha(packed)==binding['gzip_sha256'],'SOURCE_GZIP')
    if binding.get('canonical_sha256'):need(sha(raw)==binding['canonical_sha256'],'SOURCE_CANONICAL')
    return strict_json(raw,max_elements=8000000)


def recovery(route,key,tmp,design):
    # Reuse the saved V4 target list. Its analysis is not executed again.
    archive=base64.b64decode((ROOT/'docs/delegated-bc/20261019/SUPPORT_V4_39207305338.zip.b64').read_bytes(),validate=False)
    need(sha(archive)==design['v4_archive_sha256'],'V4_ARCHIVE')
    with zipfile.ZipFile(io.BytesIO(archive)) as z: blob=z.read('paired-support.mxmenc')
    need(sha(blob)==design['v4_ciphertext_sha256'],'V4_CIPHER')
    v4=strict_json(unpack(owner.bounded_decrypt(blob,key,tmp)),max_elements=8000000)
    need(v4['schema']=='mxm.paired-support-private-result.v1' and v4['source_sha']==design['v4_source_sha'],'V4_IDENTITY')
    targets=v4['result']['exact_unresolved_targets']
    pilot=read_binding(route,old.SOURCE,key,tmp)
    need(sha(old.original_encoding(pilot['summary']))==old.SUMMARY_SHA,'ORIGINAL_SUMMARY')
    source=design['corpus'];run=route.json('actions/runs/'+str(source['run_id']))
    need(run['conclusion']=='success' and run['head_sha']==source['head_sha'] and run['run_attempt']==1,'CORPUS_NATIVE_RUN')
    corpus=read_binding(route,source,key,tmp)
    need(corpus['summary']['source_head']==source['head_sha'] and corpus['summary']['protected_forward'] is False,'CORPUS_IDENTITY')
    quotes=list(corpus['raw_quote_receipts']);provenance=[]
    # Full authenticated original acquisition manifests, not guessed release names.
    checkpoints=[m for m in corpus['summary']['checkpoints'] if m['phase'] in ('quotes','screen')]
    need(len(checkpoints)<=256,'ARCHIVE_RESOURCE_LIMIT')
    for i,meta in enumerate(checkpoints):
        value=read_binding(route,meta,key,tmp)
        need(value['source_head']==source['head_sha'],'ARCHIVE_SOURCE')
        q=value.get('new_quotes',value.get('quotes',[]));quotes.extend(q)
        provenance.append({'asset_id':meta['id'],'release_id':meta['release_id'],
                           'ciphertext_sha256':meta['ciphertext_sha256'],'quote_rows':len(q)})
        if i%20==0:print(json.dumps({'phase':'AUTHENTIC_ORIGINAL_ARCHIVES','completed':i+1,'total':len(checkpoints)}),flush=True)
    index,conflicts=quote_index(quotes)
    from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as accounts
    result=recover_targets(pilot,targets,corpus,index,accounts)
    result.update(archive_provenance=provenance,quote_conflicts_quarantined=[list(k) for k in sorted(conflicts)],
                  recovery_scope='ALL_QUOTES_AND_SCREEN_CHECKPOINTS_IN_ORIGINAL_AUTHENTIC_CORPUS_MANIFEST',
                  global_all_archives_exhausted=False,
                  OWNER1807_interval_disjoint=True,
                  interval_basis='PILOT2025JAN_TO2026JUL;OWNER1807_2026AUG_TOSEP',
                  no_new_broker_requests=True)
    return {'recovery':result,'corpus':corpus}


def write_checkpoint(stage,values,key,tmp,design,parent):
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    checkpoint={'schema':'mxm.finite-laboratory-checkpoint.v1','stage':stage,
        'source_sha':os.environ['LAB_SOURCE_SHA'],'trigger_sha':os.environ['GITHUB_SHA'],
        'run_id':int(os.environ['GITHUB_RUN_ID']),'run_attempt':1,'design_sha256':sha((P/'DESIGN.json').read_bytes()),
        'authority':ACTIVE,'parent_ciphertext_sha256':parent,'values':values,'pending':None}
    raw=old.encoded(checkpoint);public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
    need(public_spki_sha256(public)==old.FP,'RECIPIENT')
    OUT.mkdir(parents=True,exist_ok=True);target=OUT/(stage+'.mxmenc')
    encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=target)
    need(unpack(owner.bounded_decrypt(target.read_bytes(),key,tmp))==raw,'ENCRYPTED_READBACK')
    receipt={'schema':'mxm.finite-laboratory-public-receipt.v1','stage':stage,
        'source_sha':os.environ['LAB_SOURCE_SHA'],'trigger_sha':os.environ['GITHUB_SHA'],
        'run_id':int(os.environ['GITHUB_RUN_ID']),'encrypted_sha256':sha(target.read_bytes()),
        'design_sha256':checkpoint['design_sha256'],'parent_ciphertext_sha256':parent,
        'authority_unchanged':True,'owner1807_unchanged':True,'app_key_used':False,
        'pilot_replays':0,'v4_replays':0,'completed_queue_restarted':False,
        'broker_requests':0,'orders':0,'strategy_trials':0,'cbot_qualified':False,
        'cold_checkpoint_consumed':stage!='recovery','safe_stop':stage=='admission'}
    (OUT/(stage+'-receipt.json')).write_bytes(old.encoded(receipt))
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('ciphertext_sha256='+receipt['encrypted_sha256']+'\n')
    print(json.dumps(receipt,sort_keys=True))


def read_checkpoint(stage,key,tmp):
    previous={'frontier':'recovery','admission':'frontier'}[stage]
    blob=(ROOT/'verification/laboratory-input'/(previous+'.mxmenc')).read_bytes()
    need(sha(blob)==os.environ['LAB_PARENT_SHA256'],'PARENT_CIPHER')
    cp=strict_json(unpack(owner.bounded_decrypt(blob,key,tmp)),max_elements=8000000)
    need(cp['schema']=='mxm.finite-laboratory-checkpoint.v1' and cp['stage']==previous
         and cp['source_sha']==os.environ['LAB_SOURCE_SHA'] and cp['run_id']==int(os.environ['GITHUB_RUN_ID'])
         and cp['trigger_sha']==os.environ['GITHUB_SHA'] and cp['run_attempt']==1
         and cp['design_sha256']==sha((P/'DESIGN.json').read_bytes()) and cp['authority']==ACTIVE and cp['pending'] is None,'COLD_BINDING')
    return cp['values']


def main(stage):
    need(stage in ('recovery','frontier','admission'),'STAGE')
    need(os.environ.get('GITHUB_REPOSITORY')==old.REPO and os.environ.get('GITHUB_EVENT_NAME')=='push'
         and os.environ.get('GITHUB_REF_NAME')==old.BRANCH and os.environ.get('GITHUB_RUN_ATTEMPT')=='1'
         and os.environ.get('GITHUB_JOB')==stage,'WORKLOAD')
    need(not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'NO_APP')
    need(subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip()==os.environ['LAB_SOURCE_SHA'],'CHECKOUT')
    design=json.loads((P/'DESIGN.json').read_text());need(design['predecessor']==ACTIVE,'DESIGN_ANCHOR')
    route=GetOnly();original=urllib.request.urlopen;urllib.request.urlopen=route.open
    try:
        anchors(route)
        same=route.json('actions/runs?per_page=100')['workflow_runs']
        same=[r for r in same if r['path']=='.github/workflows/mxm-laboratory-completion-v5.yml']
        need(len(same)==1 and same[0]['id']==int(os.environ['GITHUB_RUN_ID']),'DUPLICATE_RUN')
        from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
        os.umask(0o077)
        with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as directory:
            tmp=Path(directory);key,fp=_private_key_from_secret(tmp);need(fp==old.FP,'OWNER_KEY')
            parent=None
            if stage=='recovery':values=recovery(route,key,tmp,design)
            else:
                values=read_checkpoint(stage,key,tmp);parent=os.environ['LAB_PARENT_SHA256']
                if stage=='frontier':
                    values={'recovery':values['recovery'],'frontier':pair_frontier(values['corpus'])}
                else:values={**values,'admission':admission(values['recovery'],values['frontier'])}
            anchors(route)
            write_checkpoint(stage,values,key,tmp,design,parent)
    finally:urllib.request.urlopen=original

if __name__=='__main__':
    import sys
    try:main(sys.argv[1])
    except Exception as error:
        code=str(error) if re.fullmatch(r'LAB_[A-Z0-9_]+',str(error)) else type(error).__name__
        print(json.dumps({'state':'LABORATORY_SAFE_STOP','safe_code':code}));raise SystemExit(1) from None
