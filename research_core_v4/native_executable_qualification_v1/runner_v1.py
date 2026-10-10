"""Frozen native data qualification. No signal, label, trade or return calculation."""
import os,json,pathlib,tempfile,subprocess,base64,gzip,hashlib,csv,io,math,time
from datetime import datetime,timezone
from collections import Counter
from zoneinfo import ZoneInfo
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay,iso,summarize
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.cloud_native_covariance_v1.runner_v1 import fee
from research_core_v4 import shallow_m5_support_v2 as v2
from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,send_history_page,RateLimiter
from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import StdlibCTraderTransport,m,enums,decode_ctrader_tick_page
from m6.ctrader_capture import require_read_only_request
e=rt.e;P='research_core_v4/native_executable_qualification_v1/';BASE='223117350f65048865815922f23d14102148aa7d';START=1787184000;END=START+28*86400;SIDS=(1,2,250);PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
def sha(b):return hashlib.sha256(b).hexdigest()
def ts(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())
def gate():
    h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
    need(a['authority']=='EXPLICIT_OWNER_NATIVE_HISTORY_RECOVERY_AND_QUALIFICATION_20261010','AUTHORITY')
    need(not any(a[k] for k in ('orders','protected_forward','cloud_deployment','scientific_replay')),'SCOPE')
    need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-native-executable-qualification-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW')
    need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(BASE,h);e.a.ancestor(a['policy_commit'],h)
    for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'FROZEN_SOURCE_DRIFT')
    inv=lambda r:dict(line.split('\t',1)[::-1] for line in subprocess.check_output(['git','ls-tree','-r',r],cwd=e.a.ROOT,text=True).splitlines())
    old=inv(BASE);new=inv(h);need(len(old)==3853 and all(new.get(p)==s for p,s in old.items()),'PRESERVED_ACCEPTED_FILES')
    need(not e.w.v2.existing_ref(a['one_use_ref']),'CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h})
    return h,a,json.loads((e.a.ROOT/(P+'POLICY_V1.json')).read_text())
def grid():
    return [START+d*86400+hour*3600+900 for d in range(28) if datetime.fromtimestamp(START+d*86400,timezone.utc).weekday()<5 for hour in (9,13)]
def rowcheck(r):
    t=ts(r['time_utc']);v=[float(r[k]) for k in ('open','high','low','close')];vol=float(r['tick_volume'])
    need(t%300==0 and t<END and all(math.isfinite(x) and x>0 for x in v),'BAR_GRID_DOMAIN_OR_PRICE')
    need(v[2]<=min(v[0],v[3])<=max(v[0],v[3])<=v[1] and math.isfinite(vol) and vol>=0 and vol.is_integer(),'BAR_OHLC_VOLUME')
    return t
def staged(key,fp,tmp):
    manifest=json.loads((e.a.ROOT/(P+'ARCHIVE_INPUT_MANIFEST_V1.json')).read_text());b=base64.b64decode(''.join((e.a.ROOT/p).read_text().strip() for p in manifest['parts']),validate=True)
    need(sha(b)==manifest['ciphertext_sha256'],'ARCHIVE_CIPHER_SHA');raw=gzip.decompress(e.w.old.crypto.decrypt_package(b,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp));need(sha(raw)==manifest['canonical_sha256'],'ARCHIVE_CANONICAL_SHA')
    value=e.w.old.crypto.strict_json(raw);need(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()==raw,'ARCHIVE_CANONICAL');bars={};provenance=[]
    for source in value['sources']:
        b=base64.b64decode(source['member_bytes_b64'],validate=True);need(sha(b)==source['member_sha256'],'CSV_BYTE_IDENTITY');need(e.w.old.filehash(source['acceptance_path'])==source['acceptance_sha256'],'ACCEPTANCE_SHA')
        rows=list(csv.DictReader(io.StringIO(b.decode())));times=[rowcheck(r) for r in rows];need(times==sorted(times) and len(set(times))==len(times),'SOURCE_MONOTONIC_DUPLICATES')
        sid=source['sid'];bars[sid]={t:r for t,r in zip(times,rows) if START<=t<END};provenance.append({k:v for k,v in source.items() if k!='member_bytes_b64'}|{'source_rows':len(rows),'reused_development_rows':len(bars[sid]),'source_first_utc':rows[0]['time_utc'],'source_last_utc':rows[-1]['time_utc']})
    need(set(bars)==set(SIDS),'SOURCE_IDENTITIES');return bars,provenance,value,manifest
def valid_quote(q,pol):
    if not q:return None
    s=q['sides']
    if any(s.get(k,{}).get('state')!='AUTHENTIC_CAUSAL_QUOTE' or s[k].get('source_has_more',True) or s[k]['age_ms']>pol['grid']['max_quote_age_ms'] for k in ('bid','ask')):return None
    if abs(s['bid']['timestamp_ms']-s['ask']['timestamp_ms'])>pol['grid']['max_bid_ask_skew_ms']:return None
    b=s['bid']['price'];a=s['ask']['price']
    if not 0<b<=a:return None
    return {'bid':b,'ask':a,'mid':(b+a)/2,'spread_bps':10000*math.log(a/b),'age_ms':max(s[k]['age_ms'] for k in s),'skew_ms':abs(s['bid']['timestamp_ms']-s['ask']['timestamp_ms'])}
def capture(h,a,pol,tmp,key,bars,digits):
    store=e.w.old.GitHubStore(h,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real')
    store.release=e.w.old.api('releases',{'tag_name':'mxm-native-history-checkpoints-'+a['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':h,'name':'MXM encrypted native history qualification checkpoints','prerelease':True,'body':'Encrypted native DEVELOPMENT data; no strategy, orders or public raw market data.'})
    receipts=[];quotes={};counts=Counter();auth='NOT_ATTEMPTED';tr=None;requests=0
    def persist(label):store.encrypted({'schema':'mxm.private.native.history.checkpoint.v1','source_head':h,'authentication':auth,'requests':dict(counts),'m5_receipts':receipts,'quotes':list(quotes.values()),'bars':{str(s):list(bars[s].values()) for s in SIDS}},'native-history-'+label+'.mxmenc')
    try:
        credentials=[os.environ.get(k) for k in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')];need(all(credentials),'EXISTING_RUNNER_CREDENTIAL_ABSENT')
        tr=StdlibCTraderTransport(response_timeout=30);tr.connect();account=authenticate_segment(tr,*credentials);auth='PASS_UNCHANGED_EXPLICIT_VIEW_SAME_LIVE_ACCOUNT_FINGERPRINT';rate=RateLimiter(min_interval=.25)
        # All three accepted CSVs exhaust through Sep13. Only the missing tail is fetched.
        for sid in SIDS:
            frm=ts('2026-09-14T00:00:00Z')*1000;to=END*1000-1
            for page in range(1,4):
                need(counts['m5']<pol['capture']['maximum_m5_requests'],'M5_REQUEST_CAP');ctx=v2.RequestContext(f'native-{sid}-{page}',account,sid,frm,to);beg=time.monotonic();counts['m5']+=1
                rows,present,more=send_history_page(tr,ctx=ctx,digits=digits[sid],limiter=rate);latency=(time.monotonic()-beg)*1000
                decision=v2.pagination_decision(ctx=ctx,decoded_rows=rows,has_more_present=present,has_more_value=more,page_index=page)
                rec={'sid':sid,'from_ms':frm,'to_ms':to,'requested_count':v2.PAGE_REQUESTED_COUNT,'rows':rows,'has_more_present':present,'has_more':more,'pagination_reason':decision.reason,'roundtrip_latency_ms':latency,'retrieved_utc':datetime.now(timezone.utc).isoformat(),'canonical_rows_sha256':sha(e.a.enc(rows)),'decoder':'UNCHANGED_ACCEPTED_V2_RAW_ENVELOPE_ACCOUNT_PERIOD_BINDING'};receipts.append(rec)
                for r in rows:
                    t=rowcheck(r);need(t not in bars[sid] or bars[sid][t]==r,'CONFLICTING_REUSED_NEW_BAR');bars[sid][t]=r
                need(not decision.fail_closed,'M5_PAGINATION_INCOMPLETE')
                if decision.complete:break
                to=decision.next_to_ms
            persist('m5-'+str(sid))
        boundaries=sorted({(s,t) for s in SIDS for entry in grid() for t in (entry,entry+3600,entry+14400)},key=lambda k:(k[1],k[0]));need(len(boundaries)==300,'FIXED_BOUNDARY_COUNT')
        for sid,t in boundaries:
            sides={};pages=[];ms=t*1000
            for name,kind in [('bid',enums.BID),('ask',enums.ASK)]:
                need(counts['ticks']<pol['capture']['maximum_tick_requests'],'TICK_REQUEST_CAP');require_read_only_request('ProtoOAGetTickDataReq');rate.before_send();beg=time.monotonic();counts['ticks']+=1
                res=tr.request(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=sid,type=kind,fromTimestamp=ms-60000,toTimestamp=ms),timeout=30);latency=(time.monotonic()-beg)*1000
                if isinstance(res,m.ProtoOAErrorRes):
                    sides[name]={'state':'PROVIDER_ERROR','code':res.errorCode};pages.append({'side':name,'error_code':res.errorCode,'roundtrip_latency_ms':latency});continue
                need(isinstance(res,m.ProtoOAGetTickDataRes) and res.ctidTraderAccountId==account,'TICK_RESPONSE_BINDING')
                encoded=[{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in res.tickData];decoded=decode_ctrader_tick_page(encoded);need(all(ms-60000<=x.timestamp_ms<=ms for x in decoded),'TICK_TIMESTAMP_DOMAIN')
                pages.append({'side':name,'request_from_ms':ms-60000,'request_to_ms':ms,'encoded_tick_rows':encoded,'hasMore':bool(res.hasMore),'roundtrip_latency_ms':latency,'retrieved_utc':datetime.now(timezone.utc).isoformat()})
                if not decoded:sides[name]={'state':'NO_QUOTE_IN_FIXED_60S_WINDOW'}
                else:
                    x=decoded[-1];sides[name]={'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':x.timestamp_ms,'raw_tick':x.raw_tick,'price':round(x.raw_tick/100000,digits[sid]),'age_ms':ms-x.timestamp_ms,'source_has_more':bool(res.hasMore)}
            quotes[sid,t]={'symbol_id':sid,'boundary_ms':ms,'sides':sides,'raw_pages':pages,'fills_observed':False}
            if counts['ticks']%100==0:persist('ticks-'+str(counts['ticks']))
            e.w.old.budget(maxwall=1800,maxcpu=1000,maxkib=2097152)
        persist('complete')
    except Exception:
        persist('interrupted');raise
    finally:
        if tr:tr.close()
    return quotes,receipts,dict(counts),auth,store.release['id']
def schedule_state(t,full,row):
    schedule=full.get('schedule');tz=full.get('scheduleTimeZone',row.get('schedule_time_zone'))
    if not isinstance(schedule,list) or not tz:return 'UNKNOWN_CURRENT_SCHEDULE'
    try:d=datetime.fromtimestamp(t,timezone.utc).astimezone(ZoneInfo(tz))
    except Exception:return 'UNKNOWN_CURRENT_SCHEDULE'
    # Open API weekly schedule has Sunday as day zero.
    sec=((d.weekday()+1)%7)*86400+d.hour*3600+d.minute*60+d.second
    return 'OPEN_CURRENT_SCHEDULE_PROXY' if any(int(v['startSecond'])<=sec<int(v['endSecond']) for v in schedule) else 'CLOSED_CURRENT_SCHEDULE_PROXY'
def qualify(pol,bars,quotes,cost):
    metadata={int(r['symbol_id']):r for r in cost['metadata_rows']};native=cost['current_native_evidence']['private_native_evidence'];episodes=[];out=[]
    for sid in SIDS:
        row=metadata[sid];full=native['full'][str(sid)];own=[];units=int(row['min_volume_cents'])/100;margin=max(float(row['buy_margin_eur']),float(row['sell_margin_eur']))
        need(row['broker_symbol']==dict(zip(SIDS,('EURUSD','GBPUSD','SpotCrude')))[sid],'NATIVE_IDENTITY')
        for t in grid():
            prior=[bars[sid].get(t-600-i*300) for i in range(12)];m5=all(r is not None for r in prior)
            for horizon in (3600,14400):
                q0=valid_quote(quotes.get((sid,t)),pol);q1=valid_quote(quotes.get((sid,t+horizon)),pol);fx0=valid_quote(quotes.get((1,t)),pol);fx1=valid_quote(quotes.get((1,t+horizon)),pol)
                ep={'sid':sid,'entry':t,'exit':t+horizon,'horizon_seconds':horizon,'block':(t-START)//604800,'iso':iso(t),'entry_clock':datetime.fromtimestamp(t,timezone.utc).strftime('%H:%M'),'prior12_completed_m5':m5,'both_quotes':bool(q0 and q1),'causal_two_sided_fx':bool(fx0 and fx1),'joint':bool(m5 and q0 and q1 and fx0 and fx1),'current_economic_pass':False,'entry_session_proxy':schedule_state(t,full,row),'exit_session_proxy':schedule_state(t+horizon,full,row)}
                if ep['joint']:
                    f=fee(row,native,q0['mid']);spread=.5*(q0['spread_bps']+q1['spread_bps']);notional=units*q0['mid']/min(fx0['bid'],fx1['bid']);width=max(float(r['high']) for r in prior)-min(float(r['low']) for r in prior);risk=units*width/fx0['bid'];current_conversion=row.get('pnl_conversion_fee_pct');conversion_known=current_conversion is not None
                    ep.update(spread_context_bps=spread,current_commission_bps=f['bps'],current_commission_state=f['state'],minimum_notional_eur_reference=notional,prior_h1_range_eur_at_minimum=risk,current_minimum_margin_eur=margin,current_free_capital_eur=200-margin,entry_quote_age_ms=q0['age_ms'],exit_quote_age_ms=q1['age_ms'],entry_side_skew_ms=q0['skew_ms'],exit_side_skew_ms=q1['skew_ms'],current_pnl_conversion_fee_pct=current_conversion,designed_stop_price_distance_at_1eur=fx0['bid']/units,range_is_not_directional_opportunity=True)
                    if f['bps'] is not None and conversion_known:
                        costcash=notional*(spread+f['bps']+2)/10000;proxy=risk+costcash
                        ep.update(spread_commission_plus2bps_eur_reference=costcash,risk_proxy_plus_cost_eur=proxy,current_economic_pass=margin<=50 and 200-margin>=150 and proxy<=2 and ep['entry_session_proxy']=='OPEN_CURRENT_SCHEDULE_PROXY' and ep['exit_session_proxy']=='OPEN_CURRENT_SCHEDULE_PROXY')
                own.append(ep);episodes.append(ep)
        horizons={}
        for horizon in (3600,14400):
            rr=[r for r in own if r['horizon_seconds']==horizon]
            def partition(z):
                n=len(z);joint=sum(r['joint'] for r in z);econ=sum(r['current_economic_pass'] for r in z)
                return {'calendar':n,'prior_m5':sum(r['prior12_completed_m5'] for r in z),'both_quotes':sum(r['both_quotes'] for r in z),'joint':joint,'economic_scenario':econ,'pass':n>0 and joint/n>=.95 and joint>=8 and econ/n>=.80}
            blocks=[partition([r for r in rr if r['block']==b]) for b in range(4)];weeks={w:partition([r for r in rr if r['iso']==w]) for w in pol['development']['complete_iso_weeks']}
            horizons[str(horizon)]={'global':partition(rr),'original_blocks':blocks,'complete_iso_weeks':weeks,'qualified':all(z['pass'] for z in blocks+list(weeks.values())),'spread_context_bps':summarize(r.get('spread_context_bps') for r in rr),'commission_scenario_bps':summarize(r.get('current_commission_bps') for r in rr),'cost_eur_plus2bps':summarize(r.get('spread_commission_plus2bps_eur_reference') for r in rr),'risk_proxy_plus_cost_eur':summarize(r.get('risk_proxy_plus_cost_eur') for r in rr),'missing_reasons':dict(Counter('M5_PRIOR_GAP' if not r['prior12_completed_m5'] else 'BID_ASK_INVALID' if not r['both_quotes'] else 'EURUSD_EXECUTABLE_FX_MISSING' if not r['causal_two_sided_fx'] else 'CURRENT_ECONOMIC_GATE' for r in rr if not r['current_economic_pass']))}
        bt=sorted(bars[sid]);gaps=Counter((b-a)//300-1 for a,b in zip(bt,bt[1:]) if b-a>300);session=Counter(schedule_state(t,full,row) for t in range(START,END,300) if t not in bars[sid]);contractkeys=('min_volume_cents','step_volume_cents','lot_size','commission_rate_normalized','commission_rate_unit','min_commission_normalized','min_commission_type','min_commission_asset','pnl_conversion_fee_pct','swap_long','swap_short','swap_calculation_type','swap_period','swap_time','swap_rollover_3_days','schedule_time_zone','buy_margin_eur','sell_margin_eur','source')
        out.append({'sid':sid,'symbol':row['broker_symbol'],'m5_development_rows':len(bt),'m5_original_blocks':[sum(START+b*604800<=t<START+(b+1)*604800 for t in bt) for b in range(4)],'m5_complete_iso_weeks':{w:sum(iso(t)==w for t in bt) for w in pol['development']['complete_iso_weeks']},'m5_missing_calendar_slots':28*288-len(bt),'missing_slots_current_schedule_proxy':dict(session),'gaps_missing_slot_histogram':dict(gaps),'quality':{'duplicate_conflicts':0,'off_grid':0,'ohlc_invalid':0,'negative_tick_volume':0,'zero_volume_rows':sum(float(r['tick_volume'])==0 for r in bars[sid].values()),'forward_filled':0,'actual_historical_bar_delivery_times':'UNAVAILABLE'},'current_contract':{k:row.get(k) for k in contractkeys},'horizons':horizons})
    return episodes,out
def main():
    global PHASE
    os.umask(0o077);h,a,pol=gate()
    with tempfile.TemporaryDirectory(prefix='mxm-native-qualification-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY')
        if a.get('failure_checkpoint_readback_only'):
            PHASE='EXISTING_INTERRUPTED_CHECKPOINT_READBACK';saved,sp=load_asset(key,fp,tmp,a['checkpoint_source'])
            out={'schema':'mxm.private.native.failure.checkpoint.readback.v1','source_head':h,'checkpoint_source_head':saved['source_head'],'checkpoint_provenance':sp,'authentication':saved['authentication'],'request_counts':saved['requests'],'saved_m5_receipts':len(saved['m5_receipts']),'saved_quotes':len(saved['quotes']),'m5_canonical_rows':{s:len(v) for s,v in saved['bars'].items()},'new_broker_requests':0,'closed_results_replayed':False,'orders':0,'protected_forward':False,'cloud_deployment':False}
            rt.output(h,a,tmp,key,'nativefailure',{'summary':out},out);relay(h,a,tmp,out);return
        PHASE='EXISTING_BYTE_IDENTICAL_ARCHIVES';bars,provenance,recovered,manifest=staged(key,fp,tmp);cost,cp=load_asset(key,fp,tmp,a['cost_source']);native=cost['current_native_evidence']['private_native_evidence'];digits={s:int(native['full'][str(s)]['digits']) for s in SIDS}
        PHASE='MISSING_NATIVE_TAIL_AND_FIXED_BID_ASK';quotes,receipts,requests,auth,checkpoint=capture(h,a,pol,tmp,key,bars,digits)
        PHASE='FROZEN_DATA_AND_CURRENT_ECONOMIC_QUALIFICATION';episodes,identities=qualify(pol,bars,quotes,cost);qualified=[{'sid':r['sid'],'horizon_seconds':int(k)} for r in identities for k,v in r['horizons'].items() if v['qualified']]
        quality=Counter('VALID_FRESH_UNPAGED_SYNCHRONIZED' if valid_quote(q,pol) else 'INVALID_UNDER_FROZEN_RULES' for q in quotes.values());latencies=[p['roundtrip_latency_ms'] for q in quotes.values() for p in q['raw_pages']]
        out={'schema':'mxm.private.native.executable.qualification.v1','source_head':h,'policy_commit':a['policy_commit'],'policy_sha256':e.w.old.filehash(P+'POLICY_V1.json'),'archive_input_cipher_sha256':manifest['ciphertext_sha256'],'archive_input_provenance':provenance,'current_cost_provenance':cp,'catalogued_archives':len(recovered['catalog']),'existing_demo_quotes_not_live_substitutes':recovered['demo_tick_archives'],'identities':identities,'new_requests':requests,'authentication':auth,'new_m5_rows':{str(s):sum(len(r['rows']) for r in receipts if r['sid']==s) for s in SIDS},'fixed_entries_per_identity':len(grid()),'quote_boundaries':len(quotes),'quote_quality':dict(quality),'historical_tick_roundtrip_latency_ms':summarize(latencies),'quote_age_ms':summarize(v.get('age_ms') for q in quotes.values() for v in q['sides'].values()),'has_more_pages':sum(bool(p.get('hasMore')) for q in quotes.values() for p in q['raw_pages']),'checkpoint_release_id':checkpoint,'qualified_cohorts':qualified,'decision':'DATA_QUALIFIED_FOR_NEW_PROSPECTIVE_RESEARCH' if qualified else 'DATA_LIMITED','fills':0,'orders':0,'protected_forward':False,'cloud_deployment':False,'closed_results_replayed':False,'new_directional_experiment':False,'robust_NET':False,'HARD21':False,'limitations':['QUOTES_ARE_CAUSAL_REFERENCES_NOT_FILLS','CURRENT_FEES_MARGIN_SWAP_AND_CONVERSION_NOT_HISTORICALLY_CERTIFIED','NO_HISTORICAL_SLIPPAGE_OR_ACTUAL_BAR_DELIVERY_LATENCY','CURRENT_SCHEDULE_PROXY_NOT_HISTORICAL_HOLIDAY_CERTIFICATE','PRE_ENTRY_RANGE_PROXY_NOT_STOP_DRAWDOWN_OR_SURVIVAL_CERTIFICATION','CROSS_INSTRUMENT_SAME_CLOCK_DEPENDENCE_AND_SHARED_FX;NOT_INDEPENDENT_OPPORTUNITIES'],'next_action':'SINGLE_DISTINCT_FULLY_FROZEN_PROSPECTIVE_RESEARCH_ONLY_ON_QUALIFIED_COHORTS' if qualified else 'DO_NOT_FORCE_ALPHA;RESOLVE_REPORTED_DATA_OR_COST_GATE_CAUSE_WITH_AUTHENTIC_BOUNDED_EVIDENCE'}
        PHASE='OWNER_ENCRYPTED_DELIVERY';rt.output(h,a,tmp,key,'nativequalification',{'summary':out,'archive_recovery':recovered,'private_m5_rows':{str(s):[bars[s][t] for t in sorted(bars[s])] for s in SIDS},'private_m5_acquisition_receipts':receipts,'private_quote_receipts':list(quotes.values()),'private_qualification_episodes':episodes},out)
        PHASE='SESSION_ENCRYPTED_RELAY';relay(h,a,tmp,out)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
