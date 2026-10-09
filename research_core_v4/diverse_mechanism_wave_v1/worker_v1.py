"""New science, existing verified crypto/checkpoint/Git/Release transaction path.

Only two lifecycle identity hooks change: public identity fields and exact
journal completeness validation. The prior encryption, byte restore, commit
CAS, attestation, completion linearization and finish/reader code are reused.
"""
import argparse,json,math,os,pathlib,tempfile
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as old
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n
from research_core_v4.numeric_development_v1.public_output_guard_v1 import SCHEMA,ROOT as PUB,validate_public_blob
from research_core_v4.numeric_development_v2 import machine_v2 as v2
from research_core_v4.numeric_development_v3 import finalization_v3 as f
from research_core_v4.diverse_mechanism_wave_v1 import authority_v1 as a,kernel_v1 as k

REASONS=('SUPPORTED','NO_EVENT','FEATURE_GAP','FEATURE_RECEIPT','ZERO_ACTIVITY','LABEL_GAP','LABEL_RECEIPT','DOMAIN_CENSOR')

def metrics():return {'n':0,'sum':0.,'sum_square':0.,'feature_valid':0,'emitted':0,'reasons':{r:0 for r in REASONS}}
def state(ordinal,m):
    s=n.state(ordinal,m['symbol_id'],m.get('asset_class','UNKNOWN'))
    s['lag']={str(l):{x:metrics() for x in k.MECHANISMS} for l in k.LAGS}
    s['weekly']=[{str(l):{x:metrics() for x in k.MECHANISMS} for l in k.LAGS} for _ in range(4)]
    return s
def new(master):
    a.need(len(master)==1576 and [m['symbol_id'] for m in master]==sorted({m['symbol_id'] for m in master}),'WAVE_MASTER_ORDER')
    return {'schema':'mxm.diverse.wave.scientific.state.v1','design_sha256':a.DESIGN_SHA,'next_shard':0,'rows':0,'states':[state(i+1,m) for i,m in enumerate(master)]}
def tally(m,value,reason,valid,emitted):
    a.need(reason in REASONS,'WAVE_REASON');m['reasons'][reason]+=1;m['feature_valid']+=int(valid);m['emitted']+=int(emitted)
    if value is not None:
        a.need(math.isfinite(value),'NONFINITE_WAVE_RESPONSE');m['n']+=1;m['sum']+=value;m['sum_square']+=value*value
def advance(engine,s,through):
    while s['next_clock']<672:
        j=s['next_clock'];t=n.START+j*3600
        if t+3600+max(k.LAGS)>through:break
        buffer={int(ts):b for ts,b in s['buffer'].items()}
        for lag in k.LAGS:
            directions,valid=k.directions(buffer,t,lag)
            for mechanism,(d,reason) in directions.items():
                value=None;emitted=d is not None
                if emitted:
                    y,reason=n.frozen.response(buffer,t,lag,t+3600+lag,n.END)
                    if y is not None:value=d*y*10000;reason='SUPPORTED'
                tally(s['lag'][str(lag)][mechanism],value,reason,valid,emitted)
                tally(s['weekly'][j//168][str(lag)][mechanism],value,reason,valid,emitted)
        s['next_clock']+=1
        retain=n.START+s['next_clock']*3600-10800
        s['buffer']={ts:b for ts,b in s['buffer'].items() if int(ts)>=retain}
def feed(engine,s,ts,b):
    a.need(ts>s['last'],'WAVE_DUPLICATE_OR_UNORDERED_ROW');s['last']=ts;s['rows']+=1;s['buffer'][str(ts)]=b
    advance(engine,s,ts+300);a.need(len(s['buffer'])<=96,'WAVE_ROLLING_MEMORY_BOUND')
def consume(engine,raw,entry,master,digits,ciphertext):
    idx=engine['next_shard'];a.need(idx<100,'WAVE_EXTRA_SHARD');seg=idx//25+1;shard=idx%25
    a.need((entry['SEGMENT_INDEX'],entry['SHARD_INDEX'])==(seg,shard),'WAVE_SHARD_ORDER')
    a.need(a.sha(ciphertext)==entry['ENCRYPTED_ASSET_SHA256'] and a.sha(raw)==entry['PLAINTEXT_CANONICAL_SHA256'],'WAVE_SOURCE_DIGEST')
    obj=n.canonical.strict_json(raw);a.need(n.canonical.canonical(obj)==raw,'WAVE_NONCANONICAL_INPUT')
    lo=shard*64+1;hi=min(1576,lo+63)
    a.need(set(obj)==n.canonical.PACKAGE_KEYS and obj['schema']=='mxm.v4.shallow-m5-v2.raw-shard.v1' and obj['segment_index']==seg and obj['shard_index']==shard and obj['identity_range']==entry['IDENTITY_RANGE']==[lo,hi],'WAVE_PACKAGE_BINDING')
    a.need(type(obj['items']) is list and len(obj['items'])==hi-lo+1,'WAVE_ITEM_COUNT')
    count=0;requests=0;first=None;last=None
    for ordinal,item in zip(range(lo,hi+1),obj['items']):
        symbol=master[ordinal-1]['symbol_id'];s=engine['states'][ordinal-1]
        a.need(set(item)==n.canonical.ITEM_KEYS and item['ordinal']==ordinal and item['symbol_id']==symbol and item['failure'] is None and item['page_cap_hits']==0 and item['retry_count']==0 and type(item['request_count']) is int and item['request_count']>=1 and type(item['transport_geometry_pages']) is list,'WAVE_ITEM_BINDING')
        a.need(item['classification']==('SHALLOW_SUPPORT_COMPLETE' if item['rows'] else 'NO_HISTORICAL_SUPPORT'),'WAVE_ITEM_CLASS')
        a.need(symbol in digits and 0<=digits[symbol]<=15,'WAVE_DIGITS_BINDING');previous=-1
        for row in item['rows']:
            ts,b=n._bar(row,digits[symbol]);a.need((ts-n.START)//(n.SEGMENT_BARS*300)==seg-1 and ts>previous,'WAVE_SEGMENT_TIME');previous=ts
            feed(engine,s,ts,b);count+=1;first=min(first or row['time_utc'],row['time_utc']);last=max(last or row['time_utc'],row['time_utc'])
        requests+=item['request_count']
    a.need(count==entry['ROW_COUNT'] and requests==entry['REQUEST_COUNT'] and first==entry['FIRST_TIMESTAMP'] and last==entry['LAST_TIMESTAMP'] and entry['RETRY_COUNT']==0 and entry['PAGE_CAP_HITS']==0 and entry['FAILURE_LEDGER']=={} and entry['PROTECTED_FORWARD_ROW_COUNT']==0,'WAVE_SOURCE_COUNTS')
    engine['rows']+=count;engine['next_shard']+=1
    if shard==24:
        for s in engine['states']:advance(engine,s,n.START+seg*7*86400)
    return count
def combine(ms):
    out=metrics()
    for m in ms:
        for x in ('n','sum','sum_square','feature_valid','emitted'):out[x]+=m[x]
        for x in REASONS:out['reasons'][x]+=m['reasons'][x]
    return out
def summary(m,denominator):
    a.need(sum(m['reasons'].values())==denominator and m['reasons']['SUPPORTED']==m['n'] and 0<=m['n']<=m['emitted']<=m['feature_valid']<=denominator,'WAVE_SUPPORT_ACCOUNTING')
    return {'calendar':denominator,'supported':m['n'],'feature_valid':m['feature_valid'],'emitted_before_maturity':m['emitted'],'gross_calendar_bps':m['sum']/denominator,'gross_supported_bps':m['sum']/m['n'] if m['n'] else None,'flat_baseline_gross_bps':0.,'increment_calendar_bps':m['sum']/denominator,'increment_supported_bps':m['sum']/m['n'] if m['n'] else None,'gross_sum':m['sum'],'gross_sum_square':m['sum_square'],'reasons':m['reasons'],'emitted_per_identity_calendar_week':m['emitted']/(denominator/168)}
def report(engine,rows,shards,processed,arm):
    a.need(engine['rows']==rows and engine['next_shard']==shards and sum(s['rows'] for s in engine['states'])==rows,'WAVE_PROCESSED_ACCOUNTING')
    for s in engine['states']:advance(engine,s,n.END+3600+max(k.LAGS))
    a.need(all(s['next_clock']==672 for s in engine['states']),'WAVE_ALL_CLOCKS')
    result={'schema':'mxm.diverse.wave.private.report.v1','design_sha256':a.DESIGN_SHA,'identities':1576,'input_shards':shards,'rows':rows,'mechanisms':list(k.MECHANISMS),'lags_seconds':list(k.LAGS),'full_frontier':{},'four_weeks':{},'identity_results':[],'source_bindings':{'source_head':arm['source_head'],'files':arm['bindings'],'manifest_sha256':n.MANIFEST_SHA,'processed_sources':processed,'scope':arm['scope']},'costs':'COST_UNRESOLVED','receipt_provenance':'UNKNOWN_CONDITIONAL_LAGS','claim':'STANDALONE_GROSS_EXPLORATORY_DEVELOPMENT_ONLY','protected_forward':False,'net_PnL_claimed':False}
    for lag in map(str,k.LAGS):
        result['full_frontier'][lag]={m:summary(combine([s['lag'][lag][m] for s in engine['states']]),1576*672) for m in k.MECHANISMS}
        result['four_weeks'][lag]=[{m:summary(combine([s['weekly'][w][lag][m] for s in engine['states']]),1576*168) for m in k.MECHANISMS} for w in range(4)]
    for s in engine['states']:
        result['identity_results'].append({'ordinal':s['ordinal'],'symbol_id':s['symbol_id'],'rows':s['rows'],'lags':{lag:{m:summary(s['lag'][lag][m],672) for m in k.MECHANISMS} for lag in map(str,k.LAGS)}})
    return result

def safe_status(head,phase,status,**extra):
    doc={'schema':SCHEMA,'source_head':head,'phase':phase,'status':status,'worker_sha256':a.digest(a.KERNEL),'scientific_design_sha256':a.DESIGN_SHA,'input_manifest_sha256':n.MANIFEST_SHA,'identity_count':1576,**extra}
    return doc
def validate_journal(store,j):
    a.need(j['schema']=='mxm.numeric.finalization.input.v3' and j['arm_sha256']==a.sha(a.enc(store.arm)) and j['approval_sha256']==store.approval_sha and j['invocation_id']==store.arm['invocation_id'] and j['bindings']==store.arm['bindings'] and j['original_run']==store.original_run and j['source_head']==store.release['target_commitish'],'WAVE_JOURNAL_BINDING')
    e=j['engine'];r=j['report'];expected=100 if store.mode=='real' else 2
    a.need(e['schema']=='mxm.diverse.wave.scientific.state.v1' and e['design_sha256']==a.DESIGN_SHA and r['schema']=='mxm.diverse.wave.private.report.v1' and r['design_sha256']==a.DESIGN_SHA,'WAVE_JOURNAL_SCIENCE')
    a.need(e['next_shard']==r['input_shards']==expected and len(e['states'])==len(r['identity_results'])==1576 and r['identities']==1576 and e['rows']==r['rows'] and len(r['source_bindings']['processed_sources'])==expected and sum(s['rows'] for s in e['states'])==r['rows'],'WAVE_JOURNAL_COMPLETENESS')
    a.need(r['source_bindings']['files']==store.arm['bindings'] and r['source_bindings']['scope']==store.arm['scope'] and set(r['full_frontier'])==set(r['four_weeks'])=={'0','300','900'} and r['mechanisms']==list(k.MECHANISMS),'WAVE_JOURNAL_FAMILY')
    a.need(sum(x['rows'] for x in r['source_bindings']['processed_sources'])==r['rows'],'WAVE_PROCESSED_SOURCE_ROWS')
    master=old.verify_science()[0]
    for i,(s,identity,m) in enumerate(zip(e['states'],r['identity_results'],master)):
        a.need(s['ordinal']==identity['ordinal']==i+1 and s['symbol_id']==identity['symbol_id']==m['symbol_id'] and s['rows']==identity['rows'] and s['next_clock']==672,'WAVE_JOURNAL_IDENTITY')
        for lag in map(str,k.LAGS):
            a.need(identity['lags'][lag]=={mech:summary(s['lag'][lag][mech],672) for mech in k.MECHANISMS},'WAVE_JOURNAL_IDENTITY_ACCUMULATORS')
    a.need(e['states'][514]['symbol_id']==3741 and e['states'][514]['rows']==0,'WAVE_QUB_SUPPORT_LIMITED')
    if store.mode=='real':a.need(e['rows']==3355389,'WAVE_REAL_ROWS')
    for lag in map(str,k.LAGS):
        a.need(set(r['full_frontier'][lag])==set(k.MECHANISMS) and len(r['four_weeks'][lag])==4,'WAVE_SIX_CELLS_FOUR_WEEKS')
        for m in k.MECHANISMS:
            expected_summary=summary(combine([s['lag'][lag][m] for s in e['states']]),1576*672)
            a.need(expected_summary==r['full_frontier'][lag][m],'WAVE_JOURNAL_AGGREGATE')
            for w in range(4):a.need(summary(combine([s['weekly'][w][lag][m] for s in e['states']]),1576*168)==r['four_weeks'][lag][w][m],'WAVE_JOURNAL_WEEKLY')

def install_identity_adapter():
    # Versioned identity hooks in the single worker process; prior source bytes
    # are never modified. Actual Git blob creation still uses the existing guard.
    v2.safe_status=safe_status;f.validate_journal=validate_journal

class Store(f.Store):
    def paths(self):
        stem='DIVERSE_WAVE_REAL' if self.mode=='real' else 'DIVERSE_WAVE_SYNTHETIC'
        return PUB+stem+'_DELIVERY_V1.json',PUB+stem+'_COMPLETION_V1.json'

def run(mode):
    os.umask(0o077);head=os.environ['GITHUB_SHA'];v2.runtime(head);master,entries,digits,manifest=old.verify_science()
    if mode=='real':
        a.real_event_gate();arm=a.real_gate(head);approval_sha=a.digest(a.APPROVAL);assets=a.olda.preflight_inventory(manifest,entries)
        a.need(not v2.existing_ref(v2.claim_name(arm)),'CONSUMED_WAVE_ARM')
    else:
        a.unavailable_acceptance_preflight();source=a.git('log','-1','--format=%H',head,'--',a.BINDINGS).decode().strip();arm=a.candidate(source,a.read(a.BINDINGS)['bindings'],'synthetic');a.validate_candidate(head,arm,'synthetic');approval_sha=a.sha(a.enc({'mode':'fabricated-only','design':a.DESIGN_SHA,'run':os.environ['GITHUB_RUN_ID']}));assets={}
    install_identity_adapter()
    with tempfile.TemporaryDirectory(prefix='mxm-wave-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);tmp.chmod(0o700)
        if mode=='real':key,fp=old._private_key_from_secret(tmp);public=a.ROOT/old.PUBLIC_KEY;a.need(fp==old.FP,'WAVE_KEY_FINGERPRINT')
        else:key,public,fp=old.generate_key(tmp)
        store=Store(head,key,public,tmp,arm,approval_sha,fp);store.claim();engine=new(master);processed=[];rows=0;count=100 if mode=='real' else 2
        try:
            for idx in range(count):
                old.budget();meta=entries[idx]
                if mode=='real':
                    asset=assets[meta['ENCRYPTED_ASSET_NAME']];blob=old.download(asset['browser_download_url'],asset['size']);a.need(len(blob)==asset['size'] and a.sha(blob)==meta['ENCRYPTED_ASSET_SHA256'],'WAVE_INPUT_CIPHERTEXT')
                else:
                    from research_core_v4.diverse_mechanism_wave_v1.synthetic_v1 import fabricated_shard
                    raw,meta=fabricated_shard(idx,master,digits);path=tmp/'fabricated-input.mxmenc';old.encrypt_shard(raw,public_key=public,output=path);blob=path.read_bytes();path.unlink();meta['ENCRYPTED_ASSET_SHA256']=a.sha(blob)
                raw=old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
                rows+=consume(engine,raw,meta,master,digits,blob);processed.append(v2.source_record(idx,meta));del raw,blob
                if (idx+1)%25==0 or (mode=='synthetic' and idx+1==count):
                    cp=store.checkpoint(engine,rows,processed);print(json.dumps({'checkpoint_next_shard':engine['next_shard'],'encrypted_checkpoint_readback':'PASS','ciphertext_sha256':cp['ciphertext_sha256']}),flush=True)
            if mode=='real':a.need(rows==3355389,'WAVE_REAL_ROW_TOTAL')
            result=report(engine,rows,count,processed,arm)
            if mode=='synthetic':
                a.need(all(result['full_frontier'][str(l)][m]['supported']>0 for l in k.LAGS for m in k.MECHANISMS),'SYNTHETIC_ALL_SIX_COMPARISONS_EXERCISED')
            journal=store.prepare(result,engine,0);old.budget();done=f.finish(store,journal)
            print(json.dumps({**done,'mode':mode,'processed_this_process':count,'rows':rows,'identities':1576,'family_comparisons':6,'resources':old.usage(),'closed_original_direction_calls':0,'historical_input_downloads':100 if mode=='real' else 0,'live_orders':False}),flush=True)
        except Exception:
            if store.last and store.last['phase']!='FINAL':
                try:store.body({**store.last,'status':'FAIL_CLOSED','failure_code':'INTEGRITY_FAILURE'})
                except Exception:pass
            raise

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=('real','synthetic'),required=True);args=p.parse_args()
    try:run(args.mode)
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','code':str(e.args[0]) if isinstance(e,n.NumericalStop) and e.args else 'INTEGRITY_FAILURE','resources':old.usage()}),flush=True);raise SystemExit(2) from None
if __name__=='__main__':main()
