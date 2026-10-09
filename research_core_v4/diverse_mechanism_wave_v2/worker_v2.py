"""Operational V2 adapter for unchanged frozen scientific kernel V1.

Diagnostic state validation, recovery entry and exact worker identity change. The prior encryption, byte restore, commit
CAS, attestation, completion linearization and finish/reader code are reused.
"""
import argparse,json,math,os,pathlib,tempfile,subprocess
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as old
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n
from research_core_v4.numeric_development_v1.public_output_guard_v1 import SCHEMA,ROOT as PUB,validate_public_blob
from research_core_v4.numeric_development_v2 import machine_v2 as v2
from research_core_v4.numeric_development_v3 import finalization_v3 as f
from research_core_v4.diverse_mechanism_wave_v2 import authority_v2 as a
from research_core_v4.diverse_mechanism_wave_v1 import kernel_v1 as k

REASONS=('SUPPORTED','NO_EVENT','FEATURE_GAP','FEATURE_RECEIPT','ZERO_ACTIVITY','LABEL_GAP','LABEL_RECEIPT','DOMAIN_CENSOR')

def diagnostic():return {x:0 for x in ('eligible','agreements','disagreements','undefined')}

def metrics():return {'n':0,'sum':0.,'sum_square':0.,'feature_valid':0,'emitted':0,'reasons':{r:0 for r in REASONS},'h2_diagnostic':{'emitted':diagnostic(),'supported':diagnostic()}}
def state(ordinal,m):
    s=n.state(ordinal,m['symbol_id'],m.get('asset_class','UNKNOWN'))
    s['lag']={str(l):{x:metrics() for x in k.MECHANISMS} for l in k.LAGS}
    s['weekly']=[{str(l):{x:metrics() for x in k.MECHANISMS} for l in k.LAGS} for _ in range(4)]
    return s
def new(master):
    a.need(len(master)==1576 and [m['symbol_id'] for m in master]==sorted({m['symbol_id'] for m in master}),'WAVE_MASTER_ORDER')
    return {'schema':'mxm.diverse.wave.scientific.state.v2','design_sha256':a.DESIGN_SHA,'next_shard':0,'rows':0,'states':[state(i+1,m) for i,m in enumerate(master)]}
def tally(m,value,reason,valid,emitted,agreement=None):
    a.need(reason in REASONS,'WAVE_REASON');m['reasons'][reason]+=1;m['feature_valid']+=int(valid);m['emitted']+=int(emitted)
    if emitted:
        a.need(agreement in ('agreements','disagreements'),'WAVE_UNDEFINED_EMITTED_H2')
        for subset in ('emitted','supported') if value is not None else ('emitted',):
            m['h2_diagnostic'][subset]['eligible']+=1;m['h2_diagnostic'][subset][agreement]+=1
    else:a.need(agreement is None,'WAVE_ABSTENTION_DIAGNOSTIC')
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
                value=None;emitted=d is not None;agreement=None
                if emitted:
                    hs,_=k.hours(buffer,t,lag);body=hs[1]['c']-hs[1]['o'];reference=(body>0)-(body<0)
                    a.need(d in (-1,1) and reference in (-1,1),'WAVE_H2_REFERENCE_UNDEFINED')
                    agreement='agreements' if d==reference else 'disagreements'
                    a.need(agreement==('agreements' if mechanism==k.MECHANISMS[0] else 'disagreements'),'WAVE_H2_MATHEMATICAL_INVARIANT')
                if emitted:
                    y,reason=n.frozen.response(buffer,t,lag,t+3600+lag,n.END)
                    if y is not None:value=d*y*10000;reason='SUPPORTED'
                tally(s['lag'][str(lag)][mechanism],value,reason,valid,emitted,agreement)
                tally(s['weekly'][j//168][str(lag)][mechanism],value,reason,valid,emitted,agreement)
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
        for subset in ('emitted','supported'):
            for x in diagnostic():out['h2_diagnostic'][subset][x]+=m['h2_diagnostic'][subset][x]
    return out
def summary(m,denominator):
    validate_metric(m)
    a.need(sum(m['reasons'].values())==denominator and m['reasons']['SUPPORTED']==m['n'] and 0<=m['n']<=m['emitted']<=m['feature_valid']<=denominator,'WAVE_SUPPORT_ACCOUNTING')
    return {'h2_diagnostic':m['h2_diagnostic'],'calendar':denominator,'supported':m['n'],'feature_valid':m['feature_valid'],'emitted_before_maturity':m['emitted'],'gross_calendar_bps':m['sum']/denominator,'gross_supported_bps':m['sum']/m['n'] if m['n'] else None,'flat_baseline_gross_bps':0.,'increment_calendar_bps':m['sum']/denominator,'increment_supported_bps':m['sum']/m['n'] if m['n'] else None,'gross_sum':m['sum'],'gross_sum_square':m['sum_square'],'reasons':m['reasons'],'emitted_per_identity_calendar_week':m['emitted']/(denominator/168)}
def report(engine,rows,shards,processed,arm):
    a.need(engine['rows']==rows and engine['next_shard']==shards and sum(s['rows'] for s in engine['states'])==rows,'WAVE_PROCESSED_ACCOUNTING')
    for s in engine['states']:advance(engine,s,n.END+3600+max(k.LAGS))
    a.need(all(s['next_clock']==672 for s in engine['states']),'WAVE_ALL_CLOCKS')
    result={'schema':'mxm.diverse.wave.private.report.v2','design_sha256':a.DESIGN_SHA,'identities':1576,'input_shards':shards,'rows':rows,'mechanisms':list(k.MECHANISMS),'lags_seconds':list(k.LAGS),'full_frontier':{},'four_weeks':{},'identity_results':[],'source_bindings':{'source_head':arm['source_head'],'files':arm['bindings'],'manifest_sha256':n.MANIFEST_SHA,'processed_sources':processed,'scope':arm['scope']},'costs':'COST_UNRESOLVED','receipt_provenance':'UNKNOWN_CONDITIONAL_LAGS','claim':'STANDALONE_GROSS_EXPLORATORY_DEVELOPMENT_ONLY','protected_forward':False,'net_PnL_claimed':False}
    for lag in map(str,k.LAGS):
        result['full_frontier'][lag]={m:summary(combine([s['lag'][lag][m] for s in engine['states']]),1576*672) for m in k.MECHANISMS}
        result['four_weeks'][lag]=[{m:summary(combine([s['weekly'][w][lag][m] for s in engine['states']]),1576*168) for m in k.MECHANISMS} for w in range(4)]
    for s in engine['states']:
        result['identity_results'].append({'ordinal':s['ordinal'],'symbol_id':s['symbol_id'],'rows':s['rows'],'four_weeks':[{lag:{m:summary(s['weekly'][week][lag][m],168) for m in k.MECHANISMS} for lag in map(str,k.LAGS)} for week in range(4)],'lags':{lag:{m:summary(s['lag'][lag][m],672) for m in k.MECHANISMS} for lag in map(str,k.LAGS)}})
    return result

def safe_status(head,phase,status,**extra):
    doc={'schema':SCHEMA,'source_head':head,'phase':phase,'status':status,'worker_sha256':a.digest(a.WORKER),'scientific_design_sha256':a.DESIGN_SHA,'input_manifest_sha256':n.MANIFEST_SHA,'identity_count':1576,**extra}
    return doc
def validate_journal(store,j):
    a.need(j['schema']=='mxm.numeric.finalization.input.v3' and j['arm_sha256']==a.sha(a.enc(store.arm)) and j['approval_sha256']==store.approval_sha and j['invocation_id']==store.arm['invocation_id'] and j['bindings']==store.arm['bindings'] and j['original_run']==store.original_run and j['source_head']==store.release['target_commitish'],'WAVE_JOURNAL_BINDING')
    e=j['engine'];r=j['report'];expected=100 if store.mode=='real' else 2
    master,entries,digits,_=old.verify_science()
    validate_engine(e,master)
    verify_processed({'engine':e,'processed_sources':r['source_bindings']['processed_sources'],'expected_rows':e['rows']},store.mode,master,digits,entries)
    a.need(e['schema']=='mxm.diverse.wave.scientific.state.v2' and e['design_sha256']==a.DESIGN_SHA and r['schema']=='mxm.diverse.wave.private.report.v2' and r['design_sha256']==a.DESIGN_SHA,'WAVE_JOURNAL_SCIENCE')
    a.need(e['next_shard']==r['input_shards']==expected and len(e['states'])==len(r['identity_results'])==1576 and r['identities']==1576 and e['rows']==r['rows'] and len(r['source_bindings']['processed_sources'])==expected and sum(s['rows'] for s in e['states'])==r['rows'],'WAVE_JOURNAL_COMPLETENESS')
    a.need(r['source_bindings']['files']==store.arm['bindings'] and r['source_bindings']['scope']==store.arm['scope'] and set(r['full_frontier'])==set(r['four_weeks'])=={'0','300','900'} and r['mechanisms']==list(k.MECHANISMS),'WAVE_JOURNAL_FAMILY')
    a.need(sum(x['rows'] for x in r['source_bindings']['processed_sources'])==r['rows'],'WAVE_PROCESSED_SOURCE_ROWS')
    master=old.verify_science()[0]
    for i,(s,identity,m) in enumerate(zip(e['states'],r['identity_results'],master)):
        a.need(s['ordinal']==identity['ordinal']==i+1 and s['symbol_id']==identity['symbol_id']==m['symbol_id'] and s['rows']==identity['rows'] and s['next_clock']==672,'WAVE_JOURNAL_IDENTITY')
        a.need(identity['four_weeks']==[{lag:{m:summary(s['weekly'][week][lag][m],168) for m in k.MECHANISMS} for lag in map(str,k.LAGS)} for week in range(4)],'WAVE_JOURNAL_IDENTITY_WEEKS')
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

def validate_metric(m,mechanism=None):
    a.need(type(m) is dict and set(m)==set(metrics()),'WAVE_METRIC_FIELDS')
    a.need(set(m['reasons'])==set(REASONS),'WAVE_REASON_FIELDS')
    a.need(all(type(m[x]) is int and m[x]>=0 for x in ('n','feature_valid','emitted')) and all(type(x) is int and x>=0 for x in m['reasons'].values()),'WAVE_COUNTER_TYPES')
    a.need(all(type(m[x]) in (int,float) and math.isfinite(m[x]) for x in ('sum','sum_square')) and m['sum_square']>=0,'WAVE_GROSS_FINITE')
    a.need(m['reasons']['SUPPORTED']==m['n'] and 0<=m['n']<=m['emitted']<=m['feature_valid']<=sum(m['reasons'].values()),'WAVE_METRIC_SUPPORT')
    a.need(m['emitted']==sum(m['reasons'][x] for x in ('SUPPORTED','LABEL_GAP','LABEL_RECEIPT','DOMAIN_CENSOR')),'WAVE_EMITTED_REASONS')
    a.need(m['feature_valid']==m['emitted']+m['reasons']['NO_EVENT']+m['reasons']['ZERO_ACTIVITY'],'WAVE_FEATURE_REASONS')
    a.need(type(m['h2_diagnostic']) is dict and set(m['h2_diagnostic'])=={'emitted','supported'},'WAVE_DIAGNOSTIC_REQUIRED')
    for subset,count in (('emitted',m['emitted']),('supported',m['n'])):
        d=m['h2_diagnostic'][subset]
        a.need(type(d) is dict and set(d)==set(diagnostic()) and all(type(v) is int and v>=0 for v in d.values()),'WAVE_DIAGNOSTIC_FIELDS')
        a.need(d['eligible']==count and d['eligible']==d['agreements']+d['disagreements']+d['undefined'] and d['undefined']==0,'WAVE_DIAGNOSTIC_DENOMINATOR')
        if mechanism:a.need(d['agreements' if mechanism==k.MECHANISMS[0] else 'disagreements']==count,'WAVE_DIAGNOSTIC_INVARIANT')
    a.need(all(m['h2_diagnostic']['supported'][x]<=m['h2_diagnostic']['emitted'][x] for x in diagnostic()),'WAVE_DIAGNOSTIC_SUBSET')

def validate_engine(e,master):
    a.need(set(e)=={'schema','design_sha256','next_shard','rows','states'} and e['schema']=='mxm.diverse.wave.scientific.state.v2' and e['design_sha256']==a.DESIGN_SHA,'WAVE_RECOVERY_SCIENCE')
    a.need(type(e['next_shard']) is int and 0<=e['next_shard']<=100 and type(e['rows']) is int and e['rows']>=0 and len(e['states'])==1576,'WAVE_RECOVERY_ENGINE')
    a.need(sum(s['rows'] for s in e['states'])==e['rows'],'WAVE_RECOVERY_ROWS')
    for i,(s,m) in enumerate(zip(e['states'],master)):
        a.need(set(s)==set(state(i+1,m)) and s['ordinal']==i+1 and s['symbol_id']==m['symbol_id'] and s['context']==m.get('asset_class','UNKNOWN'),'WAVE_RECOVERY_IDENTITY')
        a.need(type(s['next_clock']) is int and 0<=s['next_clock']<=672 and type(s['rows']) is int and s['rows']>=0 and type(s['last']) is int and ((s['rows']==0 and s['last']==-1) or (s['rows']>0 and n.START<=s['last']<n.END and (s['last']-n.START)%300==0)),'WAVE_RECOVERY_CURSOR')
        a.need(type(s['buffer']) is dict and len(s['buffer'])<=96 and len(s['weekly'])==4 and set(s['lag'])==set(map(str,k.LAGS)),'WAVE_RECOVERY_CAUSAL_STATE')
        retain=n.START+s['next_clock']*3600-10800
        for ts,b in s['buffer'].items():
            a.need(type(ts) is str and str(int(ts))==ts and n.START<=int(ts)<=s['last']<n.END and int(ts)>=retain and (int(ts)-n.START)%300==0,'WAVE_BUFFER_TIMESTAMP')
            a.need(set(b)=={'timestamp','available_at','open','high','low','close','tick_volume'} and type(b['timestamp']) is int and b['timestamp']==int(ts) and type(b['available_at']) is int and b['available_at']==int(ts)+300,'WAVE_BUFFER_RECEIPT')
            a.need(all(type(b[x]) in (int,float) and math.isfinite(b[x]) for x in ('open','high','low','close')) and 0<b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high'] and type(b['tick_volume']) is int and b['tick_volume']>=0,'WAVE_BUFFER_VALUES')
        if s['rows'] and s['last']>=retain:a.need(str(s['last']) in s['buffer'],'WAVE_BUFFER_LAST_REQUIRED')
        for week in s['weekly']:a.need(set(week)==set(map(str,k.LAGS)),'WAVE_RECOVERY_WEEK_LAGS')
        for lag in map(str,k.LAGS):
            a.need(set(s['lag'][lag])==set(k.MECHANISMS) and all(set(week[lag])==set(k.MECHANISMS) for week in s['weekly']),'WAVE_RECOVERY_SIX_CELLS')
            for mech in k.MECHANISMS:
                total=s['lag'][lag][mech];validate_metric(total,mech)
                a.need(sum(total['reasons'].values())==s['next_clock'],'WAVE_RECOVERY_CALENDAR')
                for w,week in enumerate(s['weekly']):
                    mm=week[lag][mech];validate_metric(mm,mech)
                    a.need(sum(mm['reasons'].values())==min(168,max(0,s['next_clock']-w*168)),'WAVE_RECOVERY_WEEK_CALENDAR')
                merged=combine([week[lag][mech] for week in s['weekly']])
                for x in total:
                    if x in ('sum','sum_square'):
                        a.need(math.isclose(total[x],merged[x],rel_tol=1e-12,abs_tol=1e-9),'WAVE_RECOVERY_WEEK_GROSS')
                    else:a.need(total[x]==merged[x],'WAVE_RECOVERY_WEEK_RECONCILIATION')

def verify_processed(prefix,mode,master,digits,entries):
    e=prefix['engine'];validate_engine(e,master)
    if prefix.get('schema')=='mxm.numeric.prefix.v2':
        a.need(prefix['operational_source_manifest_sha256']==a.digest(a.BINDINGS) and prefix['worker_sha256']==a.digest(a.WORKER) and prefix['kernel_sha256']==a.digest(a.KERNEL),'WAVE_RECOVERY_SOURCE_IDENTITIES')
        a.need(prefix['scientific_state_sha256']==a.sha(a.enc(e)) and prefix['rolling_buffer_sha256']==[a.sha(a.enc(s['buffer'])) for s in e['states']],'WAVE_RECOVERY_EXACT_ROLLING_BYTES')
    processed=prefix['processed_sources']
    a.need(len(processed)==e['next_shard'] and prefix['expected_rows']==e['rows']==sum(x['rows'] for x in processed),'WAVE_RECOVERY_SOURCE_COUNT')
    for idx,record in enumerate(processed):
        if mode=='real':expected=v2.source_record(idx,entries[idx])
        else:
            from research_core_v4.diverse_mechanism_wave_v1.synthetic_v1 import fabricated_shard
            _,meta=fabricated_shard(idx,master,digits);meta['ENCRYPTED_ASSET_SHA256']=record['ciphertext_sha256'];expected=v2.source_record(idx,meta)
        a.need(record==expected,'WAVE_RECOVERY_PROCESSED_SOURCE_IDENTITY')
        a.need(len(record['ciphertext_sha256'])==64,'WAVE_RECOVERY_CIPHER_IDENTITY')
    # Identities outside processed shard ranges cannot acquire data or clocks.
    seg=e['next_shard']//25;partial=e['next_shard']%25
    for i,s in enumerate(e['states']):
        segments=seg+int(i//64<partial)
        a.need(s['rows']<=segments*n.SEGMENT_BARS and (s['last']==-1 or s['last']<n.START+segments*7*86400),'WAVE_RECOVERY_SOURCE_DOMAIN')
        if segments==0:a.need(s['rows']==0 and (s['next_clock']==0 or e['next_shard']==2 and s['next_clock']==672),'WAVE_RECOVERY_UNPROCESSED_IDENTITY')


def install_identity_adapter():
    # Versioned identity hooks in the single worker process; prior source bytes
    # are never modified. Actual Git blob creation still uses the existing guard.
    v2.safe_status=safe_status;f.validate_journal=validate_journal
    v2.a.recovery_gate=a.recovery_gate

class Store(f.Store):
    def body(self,document):
        # Preserve the original invocation head in every recovery receipt.
        return super().body({**document,'source_head':self.release['target_commitish']})
    def prepare(self,report,engine,start):
        if self.asset(f.JOURNAL):
            journal,meta=self.load_named(f.JOURNAL);validate_journal(self,journal)
            a.need(journal['report']==report and journal['engine']==engine,'FINAL_JOURNAL_SCIENCE_CONFLICT')
        else:
            resources=old.usage()
            for x in self.prior:resources[x]+=self.prior[x]
            journal={'schema':'mxm.numeric.finalization.input.v3','arm_sha256':a.sha(a.enc(self.arm)),
                'approval_sha256':self.approval_sha,'invocation_id':self.arm['invocation_id'],
                'original_run':self.original_run,'source_head':self.release['target_commitish'],
                'bindings':self.arm['bindings'],'report':report,'engine':engine,
                'resumed_from_shard':start,'prefix_assets':list(self.uploaded),'resources':resources}
            validate_journal(self,journal);meta=self.put(journal,f.JOURNAL)
        self.body(f.status(journal,'NOT_PERSISTED',meta));return journal
    def envelope(self,engine,expected_rows,processed,resources):
        return {**super().envelope(engine,expected_rows,processed,resources),
            'operational_source_manifest_sha256':a.digest(a.BINDINGS),
            'worker_sha256':a.digest(a.WORKER),'kernel_sha256':a.digest(a.KERNEL),
            'scientific_state_sha256':a.sha(a.enc(engine)),
            'rolling_buffer_sha256':[a.sha(a.enc(s['buffer'])) for s in engine['states']]}
    def restore(self,meta):
        value=super().restore(meta)
        if isinstance(value,dict) and value.get('schema')=='mxm.numeric.prefix.v2' and hasattr(self,'prefix_validator'):
            self.prefix_validator(value)
        return value
    def recovery(self,auth,previous):
        prefix=super().recovery(auth,previous)
        receipt,meta=self.load_named(self.last['encrypted_artifact_name'],self.last['encrypted_artifact_sha256'])
        self.uploaded.extend([receipt['checkpoint'],meta])
        return prefix
    def paths(self):
        stem='DIVERSE_WAVE_V2_REAL' if self.mode=='real' else 'DIVERSE_WAVE_V2_SYNTHETIC'
        return PUB+stem+'_DELIVERY_V1.json',PUB+stem+'_COMPLETION_V1.json'

def run(args):
    mode=args.mode
    os.umask(0o077);head=os.environ['GITHUB_SHA'];v2.runtime(head);master,entries,digits,manifest=old.verify_science()
    if mode=='real':
        a.real_event_gate();arm=a.real_gate(head);approval_sha=a.digest(a.APPROVAL);assets=a.olda.preflight_inventory(manifest,entries)
        a.need(args.key_dir is None and args.stop_after is None and args.recovery_authority is None,'REAL_TEST_SWITCH_DENIED')
        if args.previous_run is not None:a.stopped_original_preflight(arm,args.previous_run)
        else:a.need(not v2.existing_ref(v2.claim_name(arm)),'CONSUMED_WAVE_ARM')
    else:
        a.unavailable_acceptance_preflight();source=a.git('log','-1','--format=%H',head,'--',a.BINDINGS).decode().strip();arm=a.candidate(source,a.read(a.BINDINGS)['bindings'],'synthetic');a.validate_candidate(head,arm,'synthetic');approval_sha=a.sha(a.enc({'mode':'fabricated-only','design':a.DESIGN_SHA,'run':os.environ['GITHUB_RUN_ID']}));assets={}
    install_identity_adapter()
    with tempfile.TemporaryDirectory(prefix='mxm-wave-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);tmp.chmod(0o700)
        if mode=='real':key,fp=old._private_key_from_secret(tmp);public=a.ROOT/old.PUBLIC_KEY;a.need(fp==old.FP,'WAVE_KEY_FINGERPRINT')
        else:
            a.need(args.key_dir is not None,'FABRICATED_KEY_REQUIRED');kd=pathlib.Path(args.key_dir)
            a.need(kd.stat().st_mode&0o077==0,'FABRICATED_KEY_MODE');key=kd/'private.pem';public=kd/'public.pem'
            a.need(key.stat().st_mode&0o077==0,'FABRICATED_PRIVATE_MODE')
            fp=a.sha(subprocess.check_output(['openssl','pkey','-pubin','-in',str(public),'-outform','DER'],stderr=subprocess.DEVNULL))
        store=Store(head,key,public,tmp,arm,approval_sha,fp);processed=[];rows=0;count=100 if mode=='real' else 2;prior={'cpu_seconds':0,'wall_seconds':0}
        if args.previous_run is None:store.claim();engine=new(master)
        else:
            if mode=='real':auth=a.recovery_document(head)
            else:
                a.need(args.recovery_authority is not None,'FABRICATED_RECOVERY_REQUIRED');auth=json.loads(pathlib.Path(args.recovery_authority).read_bytes())
            # Validate authenticated prefix before the atomic recovery claim.
            store.prefix_validator=lambda p:verify_processed(p,mode,master,digits,entries)
            if mode=='real' and auth['next_shard']==100:
                journal=store.finalization_recovery(auth,args.previous_run);f.finish(store,journal);return
            prefix=store.recovery(auth,args.previous_run);engine=prefix['engine'];rows=prefix['expected_rows'];processed=prefix['processed_sources'];prior=auth['previous_resource_ceiling'];store.prior=prior
            print(json.dumps({'cold_process_pid':os.getpid(),'resume_next_shard':engine['next_shard'],'replay_completed_shards':False}),flush=True)
        start=engine['next_shard']
        try:
            for idx in range(start,count):
                old.budget(maxwall=a.BUDGET['wall_seconds']-prior['wall_seconds'],maxcpu=a.BUDGET['cpu_seconds']-prior['cpu_seconds']);meta=entries[idx]
                if mode=='real':
                    asset=assets[meta['ENCRYPTED_ASSET_NAME']];blob=old.download(asset['browser_download_url'],asset['size']);a.need(len(blob)==asset['size'] and a.sha(blob)==meta['ENCRYPTED_ASSET_SHA256'],'WAVE_INPUT_CIPHERTEXT')
                else:
                    from research_core_v4.diverse_mechanism_wave_v1.synthetic_v1 import fabricated_shard
                    raw,meta=fabricated_shard(idx,master,digits);path=tmp/'fabricated-input.mxmenc';old.encrypt_shard(raw,public_key=public,output=path);blob=path.read_bytes();path.unlink();meta['ENCRYPTED_ASSET_SHA256']=a.sha(blob)
                raw=old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
                rows+=consume(engine,raw,meta,master,digits,blob);processed.append(v2.source_record(idx,meta));del raw,blob
                if (idx+1)%25==0 or mode=='synthetic':
                    validate_engine(engine,master)
                    cp=store.checkpoint(engine,rows,processed);print(json.dumps({'checkpoint_next_shard':engine['next_shard'],'encrypted_checkpoint_readback':'PASS','ciphertext_sha256':cp['ciphertext_sha256']}),flush=True)
                    if args.stop_after==engine['next_shard']:
                        store.body({**store.last,'status':'FAIL_CLOSED','failure_code':'UNSUPPORTED'})
                        print(json.dumps({'status':'PLANNED_FABRICATED_PROCESS_TERMINATION','pid':os.getpid(),'durable_next_shard':engine['next_shard']}),flush=True);os._exit(75)
            if mode=='real':a.need(rows==3355389,'WAVE_REAL_ROW_TOTAL')
            result=report(engine,rows,count,processed,arm)
            if mode=='synthetic':
                a.need(all(result['full_frontier'][str(l)][m]['supported']>0 for l in k.LAGS for m in k.MECHANISMS),'SYNTHETIC_ALL_SIX_COMPARISONS_EXERCISED')
            journal=store.prepare(result,engine,start);old.budget(maxwall=a.BUDGET['wall_seconds']-prior['wall_seconds'],maxcpu=a.BUDGET['cpu_seconds']-prior['cpu_seconds']);done=f.finish(store,journal)
            print(json.dumps({**done,'mode':mode,'processed_this_process':count-start,'resumed_from_shard':start,'pid':os.getpid(),'rows':rows,'identities':1576,'family_comparisons':6,'resources':old.usage(),'closed_original_direction_calls':0,'historical_input_downloads':100 if mode=='real' else 0,'live_orders':False}),flush=True)
        except Exception:
            if store.last and store.last['phase']!='FINAL':
                try:store.body({**store.last,'status':'FAIL_CLOSED','failure_code':'INTEGRITY_FAILURE'})
                except Exception:pass
            raise

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=('real','synthetic'),required=True);p.add_argument('--key-dir');p.add_argument('--stop-after',type=int,choices=(1,));p.add_argument('--previous-run',type=int);p.add_argument('--recovery-authority');args=p.parse_args()
    try:run(args)
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','code':str(e.args[0]) if isinstance(e,n.NumericalStop) and e.args else 'INTEGRITY_FAILURE','resources':old.usage()}),flush=True);raise SystemExit(2) from None
if __name__=='__main__':main()
