"""One authenticated new numeric experiment; saved crypto/readers, no prior exact replay."""
import os,json,pathlib,tempfile,subprocess,hashlib,base64,csv,io,math,time
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from collections import Counter,defaultdict
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
from research_core_v4.native_executable_qualification_v1.runner_v1 import schedule_state,rowcheck
from research_core_v4.native_body_persistence_v1 import kernel_v1 as k
e=rt.e;P='research_core_v4/native_body_persistence_v1/';PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
def sha(x):return hashlib.sha256(x).hexdigest()
def inv(ref):return dict(x.split('\t',1)[::-1] for x in subprocess.check_output(['git','ls-tree','-r',ref],cwd=e.a.ROOT,text=True).splitlines())
def session(t,f,row):
    if any(schedule_state(t+i*300,f,row)!='OPEN_CURRENT_SCHEDULE_PROXY' for i in range(13)):return False
    a=datetime.fromtimestamp(t,timezone.utc).astimezone(ZoneInfo('America/New_York'));b=datetime.fromtimestamp(t+3600,timezone.utc).astimezone(ZoneInfo('America/New_York'))
    if a.hour<17<=b.hour:return False
    if 'swapPeriod' in f and 'swapTime' in f:
        period=int(f['swapPeriod'])*3600;offset=int(f['swapTime'])*60
        if period>0 and (t-offset)//period!=(t+3600-offset)//period:return False
    return True
def corpus(key,fp,tmp,source):
    master,entries,digits,manifest=source;rel=e.w.old.api('releases/tags/'+manifest['DURABLE_RELEASE_IDENTITY']);assets={a['name']:a for a in e.w.old.api('releases/'+str(rel['id'])+'/assets?per_page=100')}
    results=[];provenance=[];rowcount=0;clock=defaultdict(lambda:[0,0.,0.])
    for group in range(25):
        buffers={o:{} for o in range(group*64+1,min(1576,group*64+64)+1)}
        for segment in range(1,5):
            entry=entries[(segment-1)*25+group];a=assets[entry['ENCRYPTED_ASSET_NAME']];need(a['digest']=='sha256:'+entry['ENCRYPTED_ASSET_SHA256'],'SHARD_DIGEST')
            blob=e.w.old.download(a['browser_download_url'],a['size']);need(sha(blob)==entry['ENCRYPTED_ASSET_SHA256'],'SHARD_CIPHER_BYTES');raw=e.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp);need(sha(raw)==entry['PLAINTEXT_CANONICAL_SHA256'],'SHARD_CANON_SHA')
            obj=e.w.n.canonical.strict_json(raw);need(e.w.n.canonical.canonical(obj)==raw and set(obj)==e.w.n.canonical.PACKAGE_KEYS and obj['segment_index']==segment and obj['shard_index']==group and obj['identity_range']==entry['IDENTITY_RANGE'],'SHARD_SCHEMA')
            lo,hi=entry['IDENTITY_RANGE'];need(len(obj['items'])==hi-lo+1,'SHARD_IDENTITIES');count=0
            for o,item in zip(range(lo,hi+1),obj['items']):
                need(item['ordinal']==o and item['symbol_id']==master[o-1]['symbol_id'] and item['failure'] is None,'IDENTITY_BINDING');prev=-1
                for row in item['rows']:
                    t,b=e.w.n._bar(row,digits[item['symbol_id']]);need(t>prev and t not in buffers[o] and (t-k.START)//604800==segment-1,'SHARD_TIMESTAMPS');prev=t;buffers[o][t]=b;count+=1
            need(count==entry['ROW_COUNT'] and entry['PROTECTED_FORWARD_ROW_COUNT']==0,'SHARD_ROWCOUNT');rowcount+=count;provenance.append({'segment':segment,'group':group,'rows':count,'cipher_sha256':sha(blob),'canonical_sha256':sha(raw)})
        for o,bars in buffers.items():
            rr=k.observations(bars);m=master[o-1];results.append({'ordinal':o,'sid':m['symbol_id'],'symbol':m['symbol'],'class':m['asset_class'],'source_rows':len(bars),'result':k.report(rr)})
            for r in rr:
                if r['y'] is not None:
                    z=clock[r['t']];z[0]+=1;z[1]+=r['d']*r['y'];z[2]+=r['b']*r['y']
        del buffers,raw,obj,blob;print(json.dumps({'status':'PROGRESS','shards_verified':len(provenance),'numeric_outcomes_public':False}),flush=True);e.w.old.budget(maxwall=2400,maxcpu=1800,maxkib=2097152)
    need(len(results)==1576 and len(provenance)==100 and rowcount==3355389,'FULL_AUTHENTIC_CORPUS')
    aggregate=k.merge_reports([r['result'] for r in results]);aggregate['all_classes']={c:k.merge_reports([r['result'] for r in results if r['class']==c]) for c in sorted({r['class'] for r in results})}
    def cm(times):
        v=[clock[t] for t in times if clock[t][0]]
        return {'calendar_moments':len(times),'supported_moments':len(v),'model_equal_clock_mean_bps':sum(a/n for n,a,b in v)/len(v) if v else None,'baseline_equal_clock_mean_bps':sum(b/n for n,a,b in v)/len(v) if v else None,'independent_N':'NOT_IDENTIFIED'}
    aggregate['equal_calendar_cluster']={'global':cm(list(k.grid())),'blocks':[cm([t for t in k.grid() if (t-k.START)//604800==b]) for b in range(4)],'iso':{w:cm([t for t in k.grid() if k.iso(t)==w]) for w in k.WEEKS}}
    return aggregate,results,provenance
def native_bars(old):
    bars={int(s):{rowcheck(r):r for r in rr} for s,rr in old['private_m5_rows'].items()};provenance=[]
    for src in old['archive_recovery']['sources']:
        raw=base64.b64decode(src['member_bytes_b64'],validate=True);need(sha(raw)==src['member_sha256'] and e.w.old.filehash(src['acceptance_path'])==src['acceptance_sha256'],'NATIVE_ACCEPTED_SOURCE_BYTES');need(src['same_account_fingerprint_sha256']=='b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636','NATIVE_ACCOUNT_PROVENANCE')
        rr=list(csv.DictReader(io.StringIO(raw.decode())));sid=int(src['sid']);times=[rowcheck(r) for r in rr];need(times==sorted(set(times)),'NATIVE_CSV_ORDER')
        for t,r in zip(times,rr):
            if t in bars[sid]:need(all(float(r[n])==float(bars[sid][t][n]) for n in ('open','high','low','close','tick_volume')),'NATIVE_OVERLAP_CONFLICT')
            else:bars[sid][t]=r
        provenance.append({n:v for n,v in src.items() if n!='member_bytes_b64'}|{'rows':len(rr)})
    return bars,provenance
def acquire(required,quotes,cost,tmp):
    # Exact new entry-feature cohort, not selected by markouts; existing boundaries never requested.
    from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,RateLimiter
    from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import StdlibCTraderTransport,m,enums,decode_ctrader_tick_page
    from m6.ctrader_capture import require_read_only_request
    tr=None;count=0;raw=[]
    try:
        credentials=[os.environ.get(n) for n in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')];need(all(credentials),'EXISTING_RUNNER_CREDENTIAL_ABSENT')
        tr=StdlibCTraderTransport(response_timeout=30);tr.connect();aid=authenticate_segment(tr,*credentials);rate=RateLimiter(min_interval=.25)
        for sid,t in sorted(required-set(quotes),key=lambda x:(x[1],x[0])):
            need(k.START<=t<=k.END and count<9000,'CAPTURE_SCOPE');sides={};pages=[]
            for name,typ in (('bid',enums.BID),('ask',enums.ASK)):
                q=m.ProtoOAGetTickDataReq(ctidTraderAccountId=aid,symbolId=sid,type=typ,fromTimestamp=t*1000-70000,toTimestamp=t*1000);require_read_only_request(type(q).__name__);rate.before_send();count+=1;r=tr.request(q,timeout=25)
                if isinstance(r,m.ProtoOAErrorRes):sides[name]={'state':'PROVIDER_ERROR'};pages.append({'side':name,'error_code':r.errorCode});continue
                need(isinstance(r,m.ProtoOAGetTickDataRes) and r.ctidTraderAccountId==aid,'TICK_RESPONSE');enc=[{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in r.tickData];dec=decode_ctrader_tick_page(enc);need(all(t*1000-70000<=x.timestamp_ms<=t*1000 for x in dec),'TICK_CAUSAL_BOUNDS');pages.append({'side':name,'encoded':enc,'hasMore':bool(r.hasMore)})
                sides[name]={'state':'INCOMPLETE_PAGE' if r.hasMore else 'NO_QUOTE' if not dec else 'AUTHENTIC_CAUSAL_QUOTE','source_has_more':bool(r.hasMore)}
                if dec:sides[name].update(timestamp_ms=dec[-1].timestamp_ms,raw_tick=dec[-1].raw_tick,price=dec[-1].raw_tick/100000,age_ms=t*1000-dec[-1].timestamp_ms)
            value={'symbol_id':sid,'boundary_ms':t*1000,'sides':sides,'raw_pages':pages};quotes[sid,t]=value;raw.append(value);e.w.old.budget(maxwall=5400,maxcpu=2200,maxkib=2097152)
    finally:
        if tr:tr.close()
    return count,raw
def economics(native_rr,cost,quotes):
    native=cost['current_native_evidence']['private_native_evidence'];meta={int(r['symbol_id']):r for r in cost['metadata_rows']};out=[];contracts=[]
    for sid in k.SIDS:
        f=native['full'][str(sid)];row=meta[sid];u=int(row['min_volume_cents'])/100;rr=native_rr[sid]
        contracts.append({'sid':sid,'minimum_units':u,'worst_min_margin_eur':max(float(row['buy_margin_eur']),float(row['sell_margin_eur'])),'native_minCommissionAsset':f.get('minCommissionAsset'),'native_minCommissionType':f.get('minCommissionType'),'preciseMinCommission':f.get('preciseMinCommission'),'commissionType':f.get('commissionType'),'preciseTradingCommissionRate':f.get('preciseTradingCommissionRate'),'pnlConversionFeeRate':f.get('pnlConversionFeeRate'),'field_type_checked':'STRING_CURRENCY_NOT_ASSET_ID'})
        for r in rr:
            q0=k.point(quotes.get((sid,r['t'])));fx0=k.point(quotes.get((1,r['t'])));en=k.entry_gate(r,row,f,q0,fx0,session(r['t'],f,row));r.update(sid=sid,entry=en,scenarios=None)
            # Separate later evaluation, never passed into entry_gate or allocator.
            q1=k.point(quotes.get((sid,r['exit'])));fx1=k.point(quotes.get((1,r['exit'])))
            if r['d'] and r['b'] and q0 and fx0 and q1 and fx1:
                scenarios={}
                for key,slip,fund,absfee in (('0',0,0,False),('1',1,0,False),('2',2,0,False),('2_F010',2,.10,False),('2_F050',2,.50,False),('2_ABS',2,0,True)):
                    a=k.account(r['d'],u,q0,q1,fx0,fx1,f,slip,fund,absfee);b=k.account(r['b'],u,q0,q1,fx0,fx1,f,slip,fund,absfee)
                    if a is not None and b is not None:scenarios[key]={'model':a,'baseline':b}
                if len(scenarios)==6:r['scenarios']=scenarios
            out.append(r)
    chosen=[]
    for t in k.grid():
        candidates=[r for r in out if r['t']==t and r['entry']['eligible']]
        if candidates:chosen.append(min(candidates,key=lambda r:(r['entry']['flat_cost_eur']/r['entry']['range_eur'],r['sid'])))
    portfolio=k.economic_report(chosen);portfolio.update(max_simultaneous_positions=1,capital_eur=200,nominal_moments=672,selected_before_exit=True,replacement_on_missing_exit=False,certified_NET_trades=0,actual_orders=0,survival='UNPROVEN_RANGE_PROXY_IS_NOT_STOP_OR_GAP_BOUND')
    # Cash ledger stops on first missing selected markout, never manufactures realized equity.
    balance=200.;peak=200.;dd=0.;ledger_n=0;halt='END'
    for r in chosen:
        if not r['scenarios']:halt='MISSING_SELECTED_EXIT_OR_FX';break
        if balance-r['entry']['margin_eur']<150 or balance<r['entry']['range_cost_proxy_eur']:halt='CAPITAL_BUFFER';break
        balance+=r['scenarios']['2_F010']['model']['net_eur'];peak=max(peak,balance);dd=max(dd,peak-balance);ledger_n+=1
    portfolio['partial_cash_ledger']={'priced_trades':ledger_n,'halt':halt,'terminal_balance_eur':balance,'max_closed_cash_drawdown_eur':dd,'intratrade_margin_or_survival_certified':False}
    return {'panel':k.economic_report(out),'instruments':{str(s):k.economic_report([r for r in out if r['sid']==s]) for s in k.SIDS},'portfolio':portfolio,'contracts':contracts},out,chosen
def main():
    global PHASE
    os.umask(0o077);h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text());need(a['authority']=='EXPLICIT_OWNER_REAL_ALPHA_DISCOVERY_20261011' and not any(a[x] for x in ('orders','protected_forward','cloud_deployment','closed_exact_replay')),'AUTHORITY')
    need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-native-body-persistence-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW');need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(a['base_head'],h)
    for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'FROZEN_SOURCE')
    oldtree=inv(a['base_head']);newtree=inv(h);need(all(newtree.get(p)==v for p,v in oldtree.items()),'ALL_3900_OLD_FILES_PRESERVED');source=e.w.old.verify_science();need(not e.w.v2.existing_ref(a['one_use_ref']),'CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h})
    with tempfile.TemporaryDirectory(prefix='mxm-body-persistence-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');PHASE='EXISTING_AUTHENTIC_INPUTS';old,op=load_asset(key,fp,tmp,a['qualification_source']);cost,cp=load_asset(key,fp,tmp,a['cost_source']);need(old['summary']['decision']=='DATA_LIMITED','V1_UNCHANGED')
        native=cost['current_native_evidence']['private_native_evidence'];assets={str(x['assetId']):x['name'] for x in native['assets']}
        for s in k.SIDS:need(assets[str(next(x for x in native['light'] if int(x['symbolId'])==s)['quoteAssetId'])]=='USD','USD_QUOTE_ASSET')
        bars,np=native_bars(old);native_rr={s:k.observations(bars[s]) for s in k.SIDS};native_gross=k.merge_reports([k.report(native_rr[s]) for s in k.SIDS]);PHASE='NEW_MASTER1576_DIRECTIONAL_CALCULATION';master,identities,provenance=corpus(key,fp,tmp,source)
        quotes={(int(q['symbol_id']),int(q['boundary_ms'])//1000):q for q in old['private_quote_receipts']};need(len(quotes)==300,'SAVED300');count=0;newraw=[];gate=k.promising(native_gross)
        if gate:
            PHASE='PRESTATED_COHORT_ONLY_MISSING_BOUNDARIES';required=set()
            meta={int(r['symbol_id']):r for r in cost['metadata_rows']}
            for s in k.SIDS:
                for r in native_rr[s]:
                    if r['d'] and session(r['t'],native['full'][str(s)],meta[s]):required.update((z,t) for z in (s,1) for t in (r['t'],r['exit']) if t<=k.END)
            count,newraw=acquire(required,quotes,cost,tmp)
        PHASE='NEW_ECONOMIC_ACCOUNTING';econ,events,chosen=economics(native_rr,cost,quotes)
        out={'schema':'mxm.private.new.body.persistence.directional.v1','source_head':h,'hypothesis':'LAG1_BODY_RETURN_COVARIANCE_CONDITIONAL_DIRECTION','MASTER1576':master,'native_panel_gross':native_gross,'native_instrument_gross':{str(s):k.report(native_rr[s]) for s in k.SIDS},'native_economics':econ,'native_gross_gate':gate,'new_tick_requests':count,'saved_boundaries_reused':300,'authentic_master_rows':3355389,'master_shards':100,'native_source_rows':{str(s):len(bars[s]) for s in k.SIDS},'input_provenance':[op,cp],'native_archive_provenance':np,'source_bindings':a['bindings'],'feature_cohort_sha256':sha(e.a.enc([[s,r['t'],r['d'],r['b']] for s in k.SIDS for r in native_rr[s]])),'decision':'DEVELOPMENT_GROSS_LEAD_NOT_ALPHA' if gate else 'CLOSED_EXACT_NO_NATIVE_PANEL_GROSS_INCREMENT','alpha_validated':False,'HARD21':False,'orders':0,'protected_forward':False,'V1_V2_unchanged':True,'historical_fills_fees_swap_receipts':'UNKNOWN','pnl_fee_scope':'REALIZED_GROSS_PNL;POSITIVE_BASE_AND_ABSOLUTE_LOSS_STRESS_REPORTED;NO_CONTRACTUAL_LOSS_CLAIM','commission_floor':'NATIVE_STRING_CURRENCY;NO_ASSET_ID_LOOKUP','cost_denominators':'ALL_ENTRY_CALCULABLE_AND_ELIGIBLE_SEPARATELY;EACH_OUTCOME_MEAN_HAS_EXPLICIT_EVALUABLE_N','next':'NEW_DISTINCT_INFORMATION_DIRECTION_IF_GATE_FAIL;NO_INVERSION_OR_CLOCK_RESCUE'}
        PHASE='ENCRYPTED_DURABLE_PUBLICATION';rt.output(h,a,tmp,key,'bodypersistence',{'summary':out,'private_native_events':events,'private_selected_portfolio':chosen,'private_identity_aggregates':identities,'verified_master_sources':provenance,'new_raw_quote_receipts':newraw},out);relay(h,a,tmp,out)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
