"""Missing native prefix only; unchanged credentials/accepted raw-envelope decoder."""
import os,time,json,base64
from datetime import datetime,timezone
from research_core_v4.native_executable_qualification_v1.runner_v1 import HistoryReceiptTransport
from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,send_history_page,RateLimiter,SystemicFailure
from research_core_v4 import shallow_m5_support_v2 as v2
from research_core_v4.integrated_alpha_campaign_v1 import kernel_v1 as k
from research_core_v4.native_body_persistence_v1.runner_v1 import e,need,sha

def extend(h,a,tmp,key,bars,digits):
    store=e.w.old.GitHubStore(h,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');store.release=e.w.old.api('releases',{'tag_name':'mxm-integrated-history-'+a['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':h,'name':'MXM encrypted integrated history extension','prerelease':True,'body':'Only missing native historical prefix; no orders, forward, old experiment replay or public numeric vectors.'});receipts=[];counts=0;tr=None;status={};original={s:min(bars[s]) for s in (1,2,250)}
    def checkpoint(label):return store.encrypted(e.w.old.crypto.strict_json(e.a.enc({'schema':'mxm.private.integrated.history.checkpoint.v1','source_head':h,'bars':{str(s):bars[s] for s in (1,2,250)},'receipts':receipts,'requests':counts,'status':status,'source_before':original})),'history-'+label+'.mxmenc')
    try:
        credentials=[os.environ.get(n) for n in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')];need(all(credentials),'EXISTING_RUNNER_CREDENTIAL_ABSENT');tr=HistoryReceiptTransport(response_timeout=30);tr.connect();aid=authenticate_segment(tr,*credentials);rate=RateLimiter(min_interval=.25)
        for sid in (1,2,250):
            status[str(sid)]='PREFIX_CAPTURE_IN_PROGRESS';fail=False
            for frm in range(k.PREFIX,original[sid],604800):
                upper=min(frm+604800,original[sid])*1000-1;to=upper
                for page in range(1,4):
                    need(counts<180,'HISTORY_REQUEST_CAP');ctx=v2.RequestContext(f'campaign-prefix-{sid}-{frm}-{page}',aid,sid,frm*1000,to);counts+=1;beg=time.monotonic();lower=0
                    try:rr,present,more=send_history_page(tr,ctx=ctx,digits=digits[sid],limiter=rate)
                    except SystemicFailure as ex:
                        cause=str(ex.__cause__) if ex.__cause__ is not None else None
                        if cause!='bar open timestamp outside exact frozen segment':
                            receipts.append({'sid':sid,'from_ms':ctx.from_ms,'to_ms':to,'failure_code':ex.code,'raw_envelope_b64':base64.b64encode(tr.last_history_envelope.SerializeToString()).decode() if tr.last_history_envelope else None});status[str(sid)]='PROVIDER_PREFIX_BLOCKED_'+ex.code;fail=True;break
                        res=v2.bind_response_envelope(tr.last_history_envelope,ctx);present,more=v2.response_has_more_presence(res);allrows=[v2.decode_trendbar(x,digits=digits[sid],segment_from_ms=0,segment_to_ms=to) for x in res.trendbar];tt=[int(datetime.fromisoformat(x['time_utc'].replace('Z','+00:00')).timestamp())*1000 for x in allrows];need(len(tt)==len(set(tt)) and len(tt)<=v2.PAGE_REQUESTED_COUNT and all(t<=to for t in tt),'PREFIX_RESPONSE_INTEGRITY');rr=sorted([x for x,t in zip(allrows,tt) if ctx.from_ms<=t<=to],key=lambda x:x['time_utc']);lower=sum(t<ctx.from_ms for t in tt);need(lower>0,'PREFIX_LOWER_OVERFETCH')
                    dec=v2.pagination_decision(ctx=ctx,decoded_rows=rr,has_more_present=present,has_more_value=more,page_index=page)
                    rec={'sid':sid,'from_ms':ctx.from_ms,'to_ms':to,'has_more_present':present,'has_more':more,'lower_discarded':lower,'pagination_reason':'LOWER_BOUND_REACHED' if lower else dec.reason,'raw_envelope_b64':base64.b64encode(tr.last_history_envelope.SerializeToString()).decode(),'canonical_rows_sha256':sha(e.a.enc(rr)),'rows':len(rr),'retrieved_utc':datetime.now(timezone.utc).isoformat(),'latency_ms':(time.monotonic()-beg)*1000};receipts.append(rec)
                    for r in rr:
                        t=int(datetime.fromisoformat(r['time_utc'].replace('Z','+00:00')).timestamp());need(k.PREFIX<=t<original[sid] and t not in bars[sid],'PREFIX_SCOPE_NO_REACQUISITION');bars[sid][t]=[float(r[n]) for n in ('open','high','low','close','tick_volume')]
                    if lower or dec.complete:break
                    if dec.fail_closed:status[str(sid)]='PREFIX_PAGINATION_INCOMPLETE';fail=True;break
                    to=dec.next_to_ms
                if fail:break
                e.w.old.budget(maxwall=5700,maxcpu=3000,maxkib=3145728)
            if not fail:status[str(sid)]='AUTHENTIC_PREFIX_RETRIEVED_WITH_GAPS_EXPLICIT'
            checkpoint(str(sid));print(json.dumps({'phase':'NATIVE_PREFIX','symbol_ordinal':(1,2,250).index(sid)+1,'requests':counts,'private_outcomes_public':False}),flush=True)
    except Exception as ex:
        status['capture_failure_class']=type(ex).__name__
        # Preserve authenticated partial capture and continue other frozen information mechanisms.
    finally:
        if tr:tr.close()
    primary=checkpoint('final')
    return {'requests':counts,'status':status,'checkpoint_release_id':store.release['id'],'checkpoint':primary,'raw_receipts':receipts,'source_before':original,'authenticates_existing_account':not bool(status.get('capture_failure_class')),'token_changes':0}
