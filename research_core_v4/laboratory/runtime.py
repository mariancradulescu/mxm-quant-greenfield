"""Read-only worker for dynamic, prospectively admitted laboratory programmes."""
import base64,gzip,json,os,re,subprocess,tempfile,urllib.request
from pathlib import Path
from .common import *
from .programs import Laboratory,validate_manifest,AUTHORITY
from .budgets import historical_accounting,TrialBook
from .admission import TypedTrialBook
from .data import DataCatalogue,Acquisition,native_collector,LazyNativeCollector
from research_core_v4.autonomous_laboratory_20261019_v6.runtime import file_at,corpus,registry as preserved_registry
from research_core_v4.successor_c_20261018 import readback as old
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.laboratory_completion_20261019_v2.runtime import source_admission
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'verification/integrated-laboratory'
SOURCE_BRANCH='mxm-o04-successor-code-integrated-p0-r3'
EVIDENCE_BRANCH='mxm-o04-integrated-laboratory-evidence'
WF='.github/workflows/mxm-integrated-laboratory.yml'
ADMISSION='research_programs/admissions/FUNCTIONAL_RECEPTION.json'

def module_digest():
    return digest({p:bytes_digest((ROOT/'research_core_v4/laboratory'/p).read_bytes()) for p in ('common.py','data.py','budgets.py','admission.py','economics.py','programs.py','science.py','sizing.py','inventory.py','volume_pressure.py','runtime.py','claim.py','publish.py','handoff.py','custody.py','protocol.py','integrated.py','execution.py','operational_acceptance.py','handoff_recovery.py','evidence_v3.py','attest_v3.py')})

def anchors(route):
    old.owner_unchanged(route)
    need(route.json('git/ref/heads/mxm-o04-active-v1')['object']['sha']==AUTHORITY,'AUTHORITY_DRIFT')
    active=strict_json(file_at(route,'state.json',AUTHORITY));need(active['revoked'] is False and active['pending'] is None,'AUTHORITY_REVOKED_OR_PENDING')
    source_admission(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),os.environ['LAB_SOURCE_SHA'],
      route.json('git/ref/heads/'+SOURCE_BRANCH)['object']['sha'],route.json('rulesets/25222248'))

def read_state(route,oid):return strict_json(file_at(route,'program-state.json',oid))
def validate_state(s,claimed_run=None):
    pending_ok=s['pending'] is None if claimed_run is None else isinstance(s['pending'],dict) and s['pending']['run_id']==claimed_run
    need(s['schema']=='mxm.general-laboratory-public-state.v1' and pending_ok and s['authority']==AUTHORITY,'PUBLIC_STATE')
    need(type(s['sequence']) is int and s['sequence']>=0 and s['orders']==0,'PUBLIC_SEQUENCE')

def admission(route,ref,path):
    need(re.fullmatch(r'research_programs/admissions/[A-Z0-9_-]+\.json',path),'ADMISSION_PATH')
    a=strict_json(file_at(route,path,ref));need(a['schema']=='mxm.laboratory-admission.v1' and a['authority']==AUTHORITY,'ADMISSION')
    need(a['module_sha256']==module_digest() and 1<=a['steps_per_segment']<=16,'ADMISSION_CODE_BUDGET')
    need(a['mode'] in ('SYNTHETIC_RECEPTION','DEVELOPMENT_RESEARCH') and len(a['programmes'])>0,'ADMISSION_MODE')
    ids=[m['id'] for m in a['programmes']];need(len(ids)==len(set(ids)),'PROGRAMME_IDENTITIES')
    need(all(m['source_sha256']==module_digest() and m['mode']==a['mode'] for m in a['programmes']),'PROSPECTIVE_SOURCE_BINDING')
    return a

def select_programme(a,private):
    for m in sorted(a['programmes'],key=lambda m:(m.get('information_priority',100),m['id'])):
        saved=private['programmes'].get(m['id'])
        if saved:need(saved['programme']==m,'PROGRAMME_REDEFINED_AFTER_OPENING')
        if not saved or not saved['progress']['safe_stop']:return m
    return None

def authentic_integration(key,tmp):
    """Minimum authentic consumption of sealed cache, no strategy/outcome replay."""
    data=corpus(key,tmp,preserved_registry());cat=DataCatalogue();count=0
    for q in data['raw_quote_receipts'][:32]:
        t=q['boundary_ms'];rows=[]
        for side,s in q['sides'].items():
            if s.get('state')=='AUTHENTIC_CAUSAL_QUOTE':rows.append({'t':s['timestamp_ms'],'available_at':s['timestamp_ms'],'side':side,'price':s['price']})
        m={'instrument':str(q['symbol_id']),'resolution':'BID_ASK','partition':'DEVELOPMENT','start_ms':t-60000,'end_ms':t+1,
           'source':'PRESERVED_AUTHENTIC_PEPPERSTONE_QUOTE','source_sha256':digest(q),'available_at_ms':t,'session_semantics':'POINT_REFERENCE_NOT_CONTINUOUS','completeness':'UNRESOLVED','account_scope':'EXISTING_AUTHENTICATED_ACCOUNT_FINGERPRINT'}
        i=cat.ingest(m,rows,trust='AUTHENTICATED_NATIVE_CUSTODY');need(cat.assets[i]['invalid']==0 and cat.assets[i]['conflicts']==0,'AUTHENTIC_QUOTE_QUALITY');count+=cat.assets[i]['row_count']
    need(count>0,'AUTHENTIC_CACHE_EMPTY');DataCatalogue.restore(json.loads(encoded(cat.export())))
    # One minimum read-only request window through the generalized adapter.
    # This is acquisition integration, not an alpha study or historical outcome replacement.
    q=next(q for q in data['raw_quote_receipts'] if str(q['symbol_id']) in data['catalog']['full'])
    sid=int(q['symbol_id']);terms=data['catalog']['full'][str(sid)];end=(q['boundary_ms']//300000)*300000
    collector=native_collector({'M5':3});probe={'state':'NOT_EXECUTED','history_request_cap':3,'orders':0}
    try:
        collector.connect();a=Acquisition(cat,collector,{'M5':3})
        plan={'provider':'PEPPERSTONE_OPEN_API','partition':'DEVELOPMENT','read_only':True,'automatic_retries':0,'instrument':str(sid),'kind':'M5','symbol_id':sid,'digits':int(terms['digits']),
          'start_ms':end-3600000,'end_ms':end,'max_pages':3,'account_scope':'EXISTING_AUTHENTICATED_ACCOUNT_FINGERPRINT'}
        receipt=a.request(plan);asset=cat.assets[receipt['asset_id']]
        probe={'state':receipt['state'],'history_request_cap':3,'wire_counts':dict(collector.wire_types),'row_count':asset['row_count'],'native_receipts':a.receipts,'asset_id':receipt['asset_id'],'orders':0}
        if asset['completeness']=='CONFIRMED_COMPLETE':need(a.request(plan)['state']=='CACHE_REUSED','LIVE_CACHE_REUSE')
    except Exception as e:
        # Credentials/provider availability are not fabricated into successful data.
        probe={'state':'ACQUISITION_UNRESOLVED','failure_class':type(e).__name__,'history_request_cap':3,'orders':0}
    finally:
        if getattr(collector,'tr',None):
            try:collector.tr.close()
            except Exception:pass
    return {'catalogue':cat.export(),'authentic_quote_rows_validated':count,'source_ciphertext_sha256':preserved_registry()['cached_input']['ciphertext_sha256'],'native_probe':probe,'economic_outcomes_opened':0}

def main():
    if os.environ.get('LAB_INTEGRATED_PROTOCOL')=='v2':
        from .integrated import execute
        return execute()
    need(os.environ['GITHUB_REPOSITORY']==old.REPO and os.environ['GITHUB_REF_NAME']==old.BRANCH and os.environ['GITHUB_RUN_ATTEMPT']=='1'
      and os.environ['GITHUB_JOB']=='investigation' and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'WORKLOAD')
    route=GetOnly();anchors(route);parent=route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha'];s=read_state(route,parent);validate_state(s,int(os.environ['GITHUB_RUN_ID']))
    expected=os.environ.get('LAB_PARENT_OID');need(not expected or parent==expected,'STALE_SEGMENT')
    admission_ref=os.environ.get('LAB_ADMISSION_REF');path=os.environ.get('LAB_ADMISSION_PATH')
    if not admission_ref:
        trigger=strict_json(file_at(route,'research_programs/admissions/EXECUTE_LABORATORY.json',os.environ['GITHUB_SHA']))
        need(trigger['authority']==AUTHORITY and re.fullmatch(r'[a-f0-9]{40}',trigger['admission_ref']),'EXECUTION_REQUEST')
        admission_ref=trigger['admission_ref'];path=trigger['admission_path']
    a=admission(route,admission_ref,path);history=historical_accounting(ROOT)
    # Native invocation before any external request is the one-shot segment receipt.
    title='MXM LAB '+(os.environ.get('LAB_DISPATCH_PARENT') or os.environ['GITHUB_SHA'])
    runs=route.json('actions/runs?per_page=100')['workflow_runs'];matches=[r for r in runs if r['path']==WF and r['display_title']==title]
    need(len(matches)==1 and matches[0]['id']==int(os.environ['GITHUB_RUN_ID']),'DUPLICATE_EXECUTION')
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    os.umask(0o077);OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as td:
        tmp=Path(td);key,fp=_private_key_from_secret(tmp);need(fp==old.FP,'OWNER_KEY')
        if s['sequence']:
            if s.get('ciphertext_format')=='CHUNKED_ENCRYPTED_ENVELOPE_V1':
                from .custody import restore_ciphertext
                manifest=strict_json(file_at(route,s['ciphertext_path'],parent));blob=restore_ciphertext(manifest,lambda p:file_at(route,p,parent))
            else:blob=base64.b64decode(file_at(route,s['ciphertext_path'],parent))
            need(bytes_digest(blob)==s['ciphertext_sha256'],'CHECKPOINT_CIPHER_CHANGED')
            private=strict_json(unpack(owner.bounded_decrypt(blob,key,tmp)),max_elements=8000000)
            need(private['sequence']==s['sequence'] and private['pending'] is None and private['source_sha']==s.get('source_sha'),'COLD_SOURCE_BINDING')
            jobs=route.json('actions/runs/'+str(s['last_run_id'])+'/jobs?per_page=100')['jobs']
            need(all(any(j['name']==n and j['conclusion']=='success' for j in jobs) for n in ('investigation','durable-archive')),'COLD_NATIVE_COMPLETION')
        else:
            from .inventory import inventory
            book=TrialBook({'RECEPTION':0,'V2':history['V2']['limit']},{'RECEPTION':0,'V2':history['V2']['used']})
            private={'schema':'mxm.general-laboratory-private-state.v1','source_sha':os.environ['LAB_SOURCE_SHA'],'sequence':0,'pending':None,'programmes':{},'trial_book':book.export(),
              'history':history,'data_inventory':inventory(ROOT),'authentic_integration':authentic_integration(key,tmp)}
        if private['source_sha']!=os.environ['LAB_SOURCE_SHA']:
            need(private['source_sha']!='b430a303dc76bd1ea07fbd7dd9e91dcc7c7e9ee5','EXACT_TYPED_TRANSITION_PROTOCOL_REQUIRED')
            need(private['source_sha'] in ('8f2197f047b12544e1736e31f4f93e642173ccd5','a54757ce89f613be91ea05bac9f46434dd9021c0','f9bfc29c2cec87a87f9bd62bd5f38f1654c5b522') and private['safe_stop'] is True and all(v['progress']['safe_stop'] for v in private['programmes'].values()),'SOURCE_MIGRATION_REQUIRES_CLOSED_PREDECESSOR')
            private.setdefault('source_migrations',[]).append({'previous':private['source_sha'],'successor':os.environ['LAB_SOURCE_SHA'],'parent_oid':parent,'closed_programmes_replayed':False})
            private['source_sha']=os.environ['LAB_SOURCE_SHA']
        private['history']=history
        if 'shared_catalogue' not in private:
            from copy import deepcopy
            private['shared_catalogue']=deepcopy(private['authentic_integration']['catalogue'])
            for saved in private['programmes'].values():
                for ident,asset in saved['catalogue']['assets'].items():
                    previous=private['shared_catalogue']['assets'].get(ident)
                    need(previous is None or previous['normalized_sha256']==asset['normalized_sha256'],'MIGRATION_CACHE_CONFLICT')
                    private['shared_catalogue']['assets'][ident]=deepcopy(asset);private['shared_catalogue']['rows'][ident]=deepcopy(saved['catalogue']['rows'][ident])
        for asset in private['shared_catalogue']['assets'].values():
            if 'trust' not in asset and asset['source'].startswith(('PEPPERSTONE_','PRESERVED_AUTHENTIC_')):asset['trust']='AUTHENTICATED_NATIVE_CUSTODY'
        authentic_proof=private['programmes'].get('FUNCTIONAL_AUTHENTIC_DATA_CONTROL')
        if authentic_proof:
            actual=authentic_proof['progress']['results'];asset=authentic_proof['catalogue']['assets'][actual['native_data']['value']['asset_id']]
            need(asset['row_count']>0 and asset['invalid']==asset['conflicts']==0,'AUTHENTIC_CONTROLLER_NONEMPTY_QUALITY')
            need(actual['native_data']['classification']=='DATA_VALID' and actual['causal_no_op']['classification']=='CAUSAL_INTENTS_DEFINED' and actual['causal_no_op']['value']['intents']==[],'AUTHENTIC_CONTROLLER_PROOF')
        book=(TypedTrialBook.restore(private['trial_book']) if private['trial_book'].get('schema')==TypedTrialBook.SCHEMA else TrialBook.restore(private['trial_book']));executed=[];cache=None
        for _ in range(a['steps_per_segment']):
            m=select_programme(a,private)
            if m is None:break
            saved=private['programmes'].get(m['id'])
            if saved:
                lab=Laboratory.restore(saved,history,shared_catalogue=private['shared_catalogue']);lab.book=book
            else:
                # Runtime preflight binds all definitions before first outcome.
                validate_manifest(m,history,book);lab=Laboratory(m,history,book,cache=DataCatalogue.restore(private['shared_catalogue']))
            if a['mode']=='DEVELOPMENT_RESEARCH':
                from copy import deepcopy
                lab.authentic_corpus=deepcopy(corpus(key,tmp,preserved_registry()))
                lab.authentic_corpus['raw_quote_receipts'].extend(r['quote_point'] for r in lab.acquisition.receipts if r.get('quote_point'))
                lazy=LazyNativeCollector({k:lab.acquisition.budget.get(k,0) for k in ('M5','H1','BID_ASK')});lab.acquisition.collector=lazy
            task=lab.next()
            if task is None:private['programmes'][m['id']]=lab.checkpoint();continue
            result=lab.execute(task);lab.next()
            if a['mode']=='DEVELOPMENT_RESEARCH':lazy.close()
            from .execution import preserve_node
            preserve_node(private,lab);book=lab.book
            executed.append({'programme':m['id'],'task':task,'classification':result['classification']})
        private['trial_book']=book.export();private['sequence']+=1;private['admission_sha256']=digest(a)
        private['admission_ref']=admission_ref;private['admission_path']=path;private['last_run_id']=int(os.environ['GITHUB_RUN_ID']);private['parent_oid']=parent
        more=select_programme(a,private) is not None;private['safe_stop']=not more
        raw=encoded(private);public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(public)==old.FP,'RECIPIENT')
        target=OUT/'result.mxmenc';encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=target)
        need(unpack(owner.bounded_decrypt(target.read_bytes(),key,tmp))==raw,'ENCRYPTED_READBACK')
        # Destructive integrity scenario is confined to an in-memory copy.
        changed=bytearray(target.read_bytes());changed[-1]^=1;rejected=False
        try:owner.bounded_decrypt(bytes(changed),key,tmp)
        except Exception:rejected=True
        need(rejected,'MODIFIED_CIPHERTEXT_ACCEPTED')
    anchors(route);need(route.json('git/ref/heads/'+EVIDENCE_BRANCH)['object']['sha']==parent,'PARENT_MOVED_DURING_EXECUTION')
    receipt={'schema':'mxm.general-laboratory-receipt.v1','authority':AUTHORITY,'source_sha':os.environ['LAB_SOURCE_SHA'],'parent_oid':parent,
      'sequence':private['sequence'],'run_id':int(os.environ['GITHUB_RUN_ID']),'trigger_sha':os.environ['GITHUB_SHA'],
      'admission_ref':admission_ref,'admission_path':path,'admission_sha256':digest(a),'ciphertext_sha256':bytes_digest(target.read_bytes()),
      'safe_stop':not more,'pending':None,'durable_intent_consumed':True,'completed_steps':len(executed),'cold_restored':s['sequence']>0,'modified_cipher_rejected':True,
      'authentic_data_controller_validated':bool(authentic_proof),'reception_assertions_checked':not more and a['mode']=='SYNTHETIC_RECEPTION' and all(m.get('acceptance') for m in a['programmes']),
      'native_acquisition_state':private['authentic_integration']['native_probe']['state'],'authentic_cache_validated':True,
      'mode':a['mode'],'orders':0,'new_economic_outcomes':0 if a['mode']=='SYNTHETIC_RECEPTION' else None,
      'app_key_used':False,'active_authority_write':False,'cbot_qualified':False}
    receipt['research_progress']=[]
    for m in a['programmes']:
        saved=private['programmes'].get(m['id'])
        if not saved:continue
        results=saved['progress']['results']
        data=[]
        for name,result in results.items():
            if result['operator']=='acquire':
                asset=saved['catalogue']['assets'][result['value']['asset_id']]
                data.append({'task':name,'instrument':asset['instrument'],'rows':asset['row_count'],'invalid':asset['invalid'],'conflicts':asset['conflicts'],'classification':result['classification']})
        receipt['research_progress'].append({'programme':m['id'],'classifications':{k:v['classification'] for k,v in results.items()},'data':data,'safe_stop':saved['progress']['safe_stop']})
    from .protocol import accounting
    v2=accounting(private['trial_book'])['lanes']['V2']
    receipt['V2_budget_used']=v2['encumbered']
    receipt['V2_budget_remaining']=v2['limit']-v2['encumbered']
    receipt['numerical_economics_encrypted']=True
    (OUT/'receipt.json').write_bytes(encoded(receipt));print(json.dumps(receipt,sort_keys=True))

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'state':'LABORATORY_SAFE_STOP_NO_RETRY','safe_code':str(e) if re.fullmatch(r'LAB_[A-Z0-9_]+',str(e)) else type(e).__name__}));raise SystemExit(1) from None
