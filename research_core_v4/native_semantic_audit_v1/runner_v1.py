"""Saved raw receipts only. Never call capture(), qualify(), broker or a model."""
import os,json,pathlib,tempfile,subprocess,math,hashlib,base64
from datetime import datetime,timezone
from collections import Counter
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
from research_core_v4.native_executable_qualification_v1.runner_v1 import grid,ts
from research_core_v4 import shallow_m5_support_v2 as v2
from m6.cost_evidence import decode_ctrader_tick_page
from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage
e=rt.e;P='research_core_v4/native_semantic_audit_v1/';PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
def close(x,y):return math.isclose(x,y,rel_tol=1e-11,abs_tol=1e-11)
def inventory(r):return dict(line.split('\t',1)[::-1] for line in subprocess.check_output(['git','ls-tree','-r',r],cwd=e.a.ROOT,text=True).splitlines())
def audit(old,cost,readback):
    need(old['summary']['decision']=='DATA_LIMITED' and readback['summary']['saved_decision']=='DATA_LIMITED','V1_SAVED_DECISION')
    native=cost['current_native_evidence']['private_native_evidence'];meta={int(r['symbol_id']):r for r in cost['metadata_rows']}
    digits={sid:int(native['full'][str(sid)]['digits']) for sid in (1,2,250)}
    assets={str(r['assetId']):r['name'] for r in native['assets']}
    for sid in (1,2,250):
        light=next(r for r in native['light'] if int(r['symbolId'])==sid)
        need(assets[str(light['quoteAssetId'])]=='USD','USD_QUOTE_ASSET')
    quotes={};details=[];counts=Counter();causes=Counter()
    for q in old['private_quote_receipts']:
        sid=q['symbol_id'];ms=q['boundary_ms'];need((sid,ms) not in quotes,'DUPLICATE_BOUNDARY');quotes[sid,ms]=q
        need({p['side'] for p in q['raw_pages']}=={'bid','ask'} and len(q['raw_pages'])==2,'BOTH_SIDE_RECEIPTS')
        for p in q['raw_pages']:
            side=p['side'];s=q['sides'][side];counts['pages']+=1
            if 'error_code' in p:
                need(s['state']=='PROVIDER_ERROR','ERROR_RECEIPT');counts['provider_errors']+=1;continue
            need(p['request_from_ms']==ms-60000 and p['request_to_ms']==ms,'EXACT_WINDOW')
            rows=p['encoded_tick_rows'];dec=decode_ctrader_tick_page(rows);need(len(rows)==len(dec),'DECODER_CONSERVATION')
            current_t=current_p=0;independent=[]
            for i,r in enumerate(rows):
                current_t=int(r['timestamp']) if i==0 else current_t+int(r['timestamp'])
                current_p=int(r['tick']) if i==0 else current_p+int(r['tick'])
                need(ms-60000<=current_t<=ms and current_p>0,'RAW_DECODE_DOMAIN')
                independent.append((current_t,current_p))
            need(list(reversed(independent))==[(x.timestamp_ms,x.raw_tick) for x in dec],'INDEPENDENT_DELTA_PARITY')
            counts['decoded_ticks']+=len(dec);counts['has_more']+=int(p['hasMore'])
            counts['equal_timestamp_adjacent']+=sum(x.timestamp_ms==y.timestamp_ms for x,y in zip(dec,dec[1:]))
            if not dec:need(s['state']=='NO_QUOTE_IN_FIXED_60S_WINDOW','EMPTY_WINDOW_MEANING');counts['empty_windows']+=1;continue
            last=dec[-1];need(s['timestamp_ms']==last.timestamp_ms and s['raw_tick']==last.raw_tick and s['age_ms']==ms-last.timestamp_ms and s['source_has_more']==p['hasMore'] and s['price']==round(last.raw_tick/100000,digits[sid]),'SAVED_LATEST_SIDE_PARITY')
        s=q['sides'];missing=any(s[k]['state']!='AUTHENTIC_CAUSAL_QUOTE' for k in ('bid','ask'))
        truncated=any(s[k].get('source_has_more',False) for k in ('bid','ask'))
        stale=not missing and any(s[k]['age_ms']>5000 for k in ('bid','ask'))
        skew=None if missing else abs(s['bid']['timestamp_ms']-s['ask']['timestamp_ms'])
        crossed=not missing and not 0<s['bid']['price']<=s['ask']['price']
        reason='MISSING_SIDE' if missing else 'HAS_MORE' if truncated else 'INVALID_OR_CROSSED_PRICE' if crossed else 'LAST_SIDE_TICK_AGE_GT5S' if stale else 'SIDE_TIMESTAMPS_DIFFER_GT2S' if skew>2000 else 'VALID'
        causes[reason]+=1
        details.append({'sid':sid,'boundary_ms':ms,'v1_reason_unchanged':reason,'latest_side_timestamps':{k:s[k].get('timestamp_ms') for k in ('bid','ask')},'state_at_decision':'LAST_OBSERVED_REFERENCES_ONLY;NO_CLOUD_RECEIVE_OR_VALIDITY_EVIDENCE','raw_pages_sha256':hashlib.sha256(e.a.enc(q['raw_pages'])).hexdigest()})
    expected={(sid,t*1000) for sid in (1,2,250) for entry in grid() for t in (entry,entry+3600,entry+14400)}
    need(set(quotes)==expected and len(quotes)==300 and counts['pages']==600,'FIXED_BOUNDARIES')
    need(dict(causes)==readback['summary']['saved_quote_causes'],'EXCLUSIONS_CONSERVED')
    need(causes['LAST_SIDE_TICK_AGE_GT5S']==13 and causes['SIDE_TIMESTAMPS_DIFFER_GT2S']==4,'OWNER_ACCEPTED_EXCLUSIONS')
    bars={int(s):{ts(r['time_utc']):r for r in rows} for s,rows in old['private_m5_rows'].items()};bar_receipts=[]
    for rec in old['private_m5_acquisition_receipts']:
        raw=base64.b64decode(rec['raw_response_envelope_b64'],validate=True);env=ProtoMessage();env.ParseFromString(raw)
        need(env.payloadType==v2.PROTO_OA_GET_TRENDBARS_RES_PAYLOAD_TYPE,'RAW_BAR_ENVELOPE_TYPE')
        res=v2.ProtoOAGetTrendbarsResV2();res.ParseFromString(env.payload);need(res.IsInitialized() and res.period==v2.M5_ENUM,'RAW_BAR_PERIOD')
        need(not res.HasField('symbolId') or res.symbolId==rec['sid'],'RAW_BAR_SYMBOL')
        rows=[v2.decode_trendbar(b,digits=digits[rec['sid']],segment_from_ms=0,segment_to_ms=rec['to_ms']) for b in res.trendbar]
        inside=sorted((r for r in rows if rec['from_ms']<=ts(r['time_utc'])*1000<=rec['to_ms']),key=lambda r:r['time_utc'])
        need(inside==rec['rows'] and hashlib.sha256(e.a.enc(inside)).hexdigest()==rec['canonical_rows_sha256'],'RAW_M5_CANONICAL_PARITY')
        need(sum(ts(r['time_utc'])*1000<rec['from_ms'] for r in rows)==rec['lower_boundary_overfetch_discarded'],'RAW_LOWER_OVERFETCH')
        bar_receipts.append({'sid':rec['sid'],'raw_envelope_sha256':hashlib.sha256(raw).hexdigest(),'decoded_rows_sha256':rec['canonical_rows_sha256'],'parity':'PASS'})
    fxdetails=[];temporal=[]
    for ep in old['private_qualification_episodes']:
        sid=ep['sid'];t=ep['entry'];exit_t=ep['exit'];need(t in grid() and exit_t==t+ep['horizon_seconds'],'SAVED_EPISODE_CLOCK')
        opens=sorted(t-600-i*300 for i in range(12));prior=[bars[sid].get(x) for x in opens]
        need(ep['prior12_completed_m5']==all(r is not None for r in prior),'M5_EXISTENCE_PARITY')
        temporal.append({'sid':sid,'entry':t,'exit':exit_t,'first_bar_open':opens[0],'last_bar_open':opens[-1],'last_bar_close':opens[-1]+300,'assumed_available_at':opens[-1]+305,'decision_reference':t,'qualify_reexecuted':False})
        if not ep['joint']:continue
        q=quotes[sid,t*1000]['sides'];fx0=quotes[1,t*1000]['sides'];fx1=quotes[1,exit_t*1000]['sides'];units=int(meta[sid]['min_volume_cents'])/100
        mid=(q['bid']['price']+q['ask']['price'])/2;b0=fx0['bid']['price'];a0=fx0['ask']['price'];b1=fx1['bid']['price'];a1=fx1['ask']['price']
        need(close(ep['minimum_notional_eur_reference'],units*mid/min(b0,b1)),'STORED_RETROSPECTIVE_NOTIONAL_PARITY')
        width=max(float(r['high']) for r in prior)-min(float(r['low']) for r in prior)
        need(close(ep['prior_h1_range_eur_at_minimum'],units*width/b0) and close(ep['designed_stop_price_distance_at_1eur'],b0/units),'ENTRY_FX_RISK_PARITY')
        fxdetails.append({'sid':sid,'entry':t,'exit':exit_t,'entry_fx_bid':b0,'entry_fx_ask':a0,'exit_fx_bid':b1,'exit_fx_ask':a1,'eur_per_usd_liability_at_entry':1/b0,'eur_per_usd_receipt_at_entry':1/a0,'eur_per_usd_liability_at_exit':1/b1,'eur_per_usd_receipt_at_exit':1/a1,'entry_only_minimum_notional_eur_reference':units*mid/b0,'saved_notional_eur_reference':ep['minimum_notional_eur_reference'],'saved_notional_uses_exit':True,'exit_filter_executable_at_entry':False,'conversion_fee_is_applied_in_v1_cost_cash':False})
    return {'schema':'mxm.private.native.semantic.audit.v1','decision':'DATA_LIMITED_V1_PRESERVED;SEMANTIC_MISMATCHES_DOCUMENTED;NO_PROMOTION','tick_decoder_saved_reference_parity':'PASS','m5_raw_decoder_parity':'PASS','saved_exclusions':dict(causes),'receipt_counts':dict(counts),'quote_details':details,'m5_raw_receipts':bar_receipts,'temporal_details':temporal,'fx_diagnostics':fxdetails,'bar_window':'[entry-3900,entry-300);latest open entry-600;latest close entry-300','policy_latest_close_at_entry_minus5_seconds':'NO_M5_GRID_CLOSE_AT_THAT_INSTANT;IF_MEANS_AT_OR_BEFORE_IT_THEN_IMPLEMENTED_WINDOW_IS_CONSISTENT','decision_timestamp':'QUALIFICATION_REFERENCE_ENTRY;NO_OBSERVED_LIVE_DECISION;NO_PLUS5_SHIFT_IN_CODE','equal_timestamp_cross_side_order':'NOT_OBSERVED_NO_ATOMIC_SNAPSHOT_CLAIM','actual_cloud_delivery_and_fills':'UNKNOWN','exit_quotes_and_fx':'RETROSPECTIVE_DATASET_EVALUABILITY_ONLY','new_broker_requests':0,'qualification_reexecuted':False,'new_directional_model':False,'orders':0,'protected_forward':False,'cloud_deployment':False,'v1_modified':False}
def main():
    global PHASE
    os.umask(0o077);h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
    need(a['authority']=='EXPLICIT_OWNER_SAVED_NATIVE_SEMANTIC_AUDIT_20261010' and not any(a[k] for k in ('orders','protected_forward','cloud_deployment','broker_requests','scientific_replay')),'SCOPE')
    need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-native-semantic-audit-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW')
    need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(a['base_head'],h)
    for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'SOURCE_BINDING')
    original=inventory(a['base_head']);current=inventory(h);need(all(current.get(p)==s for p,s in original.items()),'ALL_EXISTING_FILES_PRESERVED')
    e.w.old.verify_science();need(not e.w.v2.existing_ref(a['one_use_ref']),'CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h})
    with tempfile.TemporaryDirectory(prefix='mxm-native-semantic-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');PHASE='SAVED_AUTHENTIC_RECEIPTS'
        old,op=load_asset(key,fp,tmp,a['qualification_source']);cost,cp=load_asset(key,fp,tmp,a['cost_source']);readback,rp=load_asset(key,fp,tmp,a['readback_source'])
        PHASE='SEMANTIC_RECEIPT_PARITY';out=audit(old,cost,readback);out.update(input_provenance=[op,cp,rp],source_head=h,original_files_preserved=True)
        PHASE='ENCRYPTED_DELIVERY';summary={k:v for k,v in out.items() if k not in ('quote_details','m5_raw_receipts','temporal_details','fx_diagnostics')}
        rt.output(h,a,tmp,key,'nativesemantics',{'summary':summary,'private_semantic_diagnostics':out},summary);relay(h,a,tmp,summary)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
