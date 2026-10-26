"""Reuse accepted source clock; independently receive EUR typed input and identify
one ORIGINAL guard event. No strategy/account replay or economic outcome."""
import base64,hashlib,io,json,os,subprocess,sys,tempfile,zipfile
from bisect import bisect_right
from collections import defaultdict,Counter
from pathlib import Path
from .common import need,encoded
from . import source_compatibility_diagnostic as prior
from .verify_intrinsic_result import verify,FOLDER,sha
from .three_week_source_recovery import FOLDERS,RUNS,ROWS
ROOT=prior.ROOT;REPO=prior.REPO;BRANCH=prior.BRANCH
PATH='.github/workflows/mxm-eur-book-reception.yml'
PROJECT='research_core_v4/laboratory/csharp/eur_book/MxmEurBook.csproj'
def workflow():
    w=prior.workflow();w['name']='MXM typed EUR book reception and original guard-event attribution'
    w['on']['push']['paths']=[PATH];j=w['jobs'].pop('source-compatibility');w['jobs']['eur-book-reception']=j
    steps=j['steps'];steps[2]['run']='python3 -m research_core_v4.laboratory.eur_book_reception admit'
    steps[3]['run']=('dotnet build '+PROJECT+' -c Release\npython3 -m unittest research_core_v4.laboratory.test_eur_book_reception -v\n'+steps[3]['run'])
    steps[5]['name']='Read original private guard cursor only, without account replay'
    steps[5]['run']='umask 077\npython3 -m research_core_v4.laboratory.eur_book_reception context "${RUNNER_TEMP}/mxm-source-admission"'
    steps.append({'name':'Receive every typed source group and independently reconcile without keys',
      'run':'umask 077\npython3 -m research_core_v4.laboratory.eur_book_reception receive "${RUNNER_TEMP}/mxm-source-admission"'})
    return w
def admit():
    verify()
    need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF_NAME')==BRANCH and os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ.get('GITHUB_JOB')=='eur-book-reception' and os.environ.get('GITHUB_WORKFLOW_REF')==REPO+'/'+PATH+'@refs/heads/'+BRANCH,'EUR_BOOK_NATIVE_CONTEXT')
    need(not any(os.environ.get(k) for k in ('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM','R3_CUSTODY_PRIVATE_KEY_PEM','SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN','R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN')),'EUR_BOOK_ADMIT_NO_KEYS')
    code=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(code==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0 and json.loads((ROOT/PATH).read_bytes())==workflow(),'EUR_BOOK_EXACT_CODE')
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();need(route.json('git/ref/heads/'+BRANCH)['object']['sha']==code,'EUR_BOOK_OFFICIAL_HEAD')
    for ref,want in [('mxm-o04-active-v1','07d1ddbe0b83753bbf189770af1911623fef8d6f'),('mxm-o04-accepted-owner-1807-v1','a830c132521bd4348454653f713e04f6107484fe')]:need(route.json('git/ref/heads/'+ref)['object']['sha']==want,'EUR_BOOK_AUTHORITY')
    v=route.json('actions/workflows/'+PATH.split('/')[-1]+'/runs?per_page=100');need(v['total_count']==len(v['workflow_runs'])==1 and v['workflow_runs'][0]['id']==int(os.environ['GITHUB_RUN_ID']) and v['workflow_runs'][0]['run_attempt']==1,'EUR_BOOK_ONE_FINITE_RECEPTION')
    print('EUR_BOOK_NO_MODEL_NO_ACCOUNT_REPLAY_NO_BROKER_NO_WRITER')
def context(folder):
    verify();folder=Path(folder)
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    b=base64.b64decode((FOLDER/'result.zip.b64').read_bytes())
    with zipfile.ZipFile(io.BytesIO(b)) as z:cipher=z.read('full-result.mxmenc')
    receipt=json.loads((FOLDER/'receipt.json').read_bytes())
    with tempfile.TemporaryDirectory() as t:
        key,fp=_private_key_from_secret(Path(t));need(fp==FP,'EUR_BOOK_EXISTING_CUSTODY')
        raw=unpack(owner.bounded_decrypt(cipher,key,Path(t)),max_bytes=2000000);need(sha(raw)==receipt['private_sha256'],'EUR_BOOK_ORIGINAL_PRIVATE_HASH')
        p=strict_json(raw,max_elements=200000);fault=prior.original_fault(p)
        c=json.loads(base64.b64decode(p['original_csharp_json_b64'][0],validate=True));ref=p['independent_reference']['segments'][0]
        group=c['groups_processed'];source=folder/'W35.ndjson';source_hash=sha(source.read_bytes())
        need(type(group) is int and group>0 and group==ref['groups_processed'] and c['invalid_groups']==ref['invalid_groups'],'EUR_BOOK_ORIGINAL_CURSOR_AGREEMENT')
        need(c['input_sha256']==p['bridges'][0]['derived_sha256']==source_hash and p['bridges'][0]['run']==RUNS['W35'] and c['source_context']==p['context_sha256'],'EUR_BOOK_EXACT_ORIGINAL_SOURCE_AND_CONTEXT')
    (folder/'original-guard-context.json').write_bytes(encoded({'source_sha256':source_hash,'group':group,'fault':fault,'original_run':40285218660}))
    print('ORIGINAL_GUARD_CURSOR_AUTHENTICATED_PRIVATE_NO_ECONOMIC_REPLAY')
def reference(path,target=0):
    sides={s:defaultdict(set) for s in ('bid','ask')};rows=0;last=-1
    for line in Path(path).read_text().splitlines():
        e=json.loads(line);t,s,v=e['t'],e['side'],e['raw'];need(type(t) is int and t>=last and s in sides and type(v) is int and v>0,'EUR_BOOK_REFERENCE_ROW')
        sides[s][t].add(v);last=t;rows+=1
    times={s:sorted(m) for s,m in sides.items()};clocks=sorted(set(times['bid'])|set(times['ask']));digest=hashlib.sha256();counts=Counter();target_code=None
    for ordinal,t in enumerate(clocks,1):
        values={};stamps={}
        for s in sides:
            index=bisect_right(times[s],t)-1;at=times[s][index] if index>=0 else None;stamps[s]=at
            v=sides[s][at] if at is not None else set();values[s]=next(iter(v)) if len(v)==1 else None
        bid,ask=values['bid'],values['ask'];bt,at=stamps['bid'],stamps['ask']
        if bid is None or ask is None:code='SOURCE_MISSING_OR_CONFLICT'
        elif ask<bid:code='SOURCE_CROSSED'
        elif t-bt>5000 or t-at>5000:code='SOURCE_AGE_LIMIT'
        else:code='OBSERVED_LOCKED' if ask==bid else 'OBSERVED_POSITIVE_SPREAD'
        counts[code]+=1
        if ordinal==target:target_code=code
        n=lambda v:'-' if v is None else str(v)
        digest.update(f'{t}|{code}|{n(bid)}|{n(bt)}|{n(ask)}|{n(at)}\n'.encode())
    need(target<=len(clocks),'EUR_BOOK_REFERENCE_TARGET')
    return {'rows':rows,'groups':len(clocks),'codes':dict(counts),'every_group_sha256':digest.hexdigest(),'target_code':target_code,'source_sha256':sha(Path(path).read_bytes())}
def receive(folder):
    folder=Path(folder);cursor=json.loads((folder/'original-guard-context.json').read_bytes());results={}
    for week,mpath in FOLDERS.items():
        path=folder/(week+'.ndjson');r=json.loads(Path(str(path)+'.receipt.json').read_bytes());m=json.loads((ROOT/mpath/'MANIFEST.json').read_bytes())
        need(r['profile']==week and r['run']==RUNS[week] and r['rows']==ROWS[week] and r['source_code']==m['code_source'] and r['source_trigger']==m['source_head'] and r['cipher_sha256']==m['members']['capture.mxmenc']['sha256'] and r['private_sha256']==m['private_sha256'] and r['derived_sha256']==sha(path.read_bytes()),'EUR_BOOK_SOURCE')
        target=cursor['group'] if week=='W35' else 0;out=folder/(week+'-typed.json')
        subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--',str(path),str(target),str(out)],check=True,capture_output=True)
        actual=json.loads(out.read_bytes());expected=reference(path,target)
        need(all(actual[k]==v for k,v in expected.items()) and actual['market_account_replay'] is False and actual['orders']==0,'EUR_BOOK_EVERY_GROUP_INDEPENDENT_RECONCILIATION')
        results[week]={'source_run':RUNS[week],**expected};results[week].pop('target_code')
        if week=='W35':
            need(cursor['source_sha256']==expected['source_sha256'] and actual['target_code']!='OBSERVED_POSITIVE_SPREAD','EUR_BOOK_ORIGINAL_GUARD_SOURCE_EVENT')
            original_code=actual['target_code']
    public={'schema':'mxm.eur-book-reception-public.v1','run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':os.environ['GITHUB_SHA'],
      'original_economic_run':40285218660,'original_guard':cursor['fault'],'original_guard_source_class':original_code,
      'original_cursor_and_source_authenticated':True,'independent_every_group_reconciled':True,'sources':results,'closed_policy_changed':False,
      'new_models':0,'new_economic_outcomes':0,'market_account_replay':False,'historical_fills_proven':False,'native_ctrader_runtime_reception':False,
      'hard21_proven':False,'economic_edge_proven':False,'new_broker_requests':0,'orders':0,'cloud_activated':False,'protected_opened':False,
      'next_action':'KEEP_FIXED_POLICY_CLOSED;DISTINCT_PROSPECTIVE_RESEARCH_REQUIRES_SOURCE_AND_COST_ADMISSION'}
    print('MXM_EUR_BOOK_RECEPTION '+encoded(public).decode(),flush=True)
if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1:]==['admit']:admit()
    elif len(sys.argv)==3 and sys.argv[1]=='context':context(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=='receive':receive(sys.argv[2])
    else:raise ValueError('EUR_BOOK_EXACT_PHASE')
