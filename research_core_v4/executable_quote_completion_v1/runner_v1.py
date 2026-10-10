"""Bounded outcome-blind BID/ASK completion using unchanged existing transport."""
import os,json,pathlib,tempfile,math,hashlib,subprocess
from collections import Counter,defaultdict
from datetime import datetime,timezone
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay,iso,summarize,point,boundary_quality
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import authenticate_segment,RateLimiter,StdlibCTraderTransport,m,enums,decode_ctrader_tick_page
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.cloud_native_covariance_v1.runner_v1 import fee
from m6.ctrader_capture import require_read_only_request
e=rt.e;P='research_core_v4/executable_quote_completion_v1/';PHASE='GATE'
BASE='27d46b0f92391c22cc927ca36739c22ff980833a';START=1787184000;END=START+28*86400
def need(x,c):e.w.old.need(bool(x),c)
def gate():
    h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
    need(a['authority']=='EXPLICIT_OWNER_NECESSARY_BOUNDED_READ_ONLY_QUOTE_COMPLETION_20261010','AUTHORITY')
    need(not any(a[k] for k in ('orders','protected_forward','cloud_deployment','scientific_replay')) and a['max_tick_requests']==72,'SCOPE')
    need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-executable-quote-completion-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE')
    need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(BASE,h)
    for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'FROZEN_SOURCE_DRIFT')
    inventory=lambda ref:dict(line.split('\t',1)[::-1] for line in subprocess.check_output(['git','ls-tree','-r',ref],cwd=e.a.ROOT,text=True).splitlines())
    old=inventory(BASE);new=inventory(h);need(len(old)==3844 and all(new.get(p)==s for p,s in old.items()),'PRESERVED_BASE')
    need(not e.w.v2.existing_ref(a['one_use_ref']),'CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h})
    return h,a
def plan_check(diag):
    s=diag['summary'];plan=s['frozen_outcome_blind_probe_plan'];need(len(plan)==12 and s['probe_max_new_tick_requests']==72,'FROZEN_PLAN')
    wanted=sorted({(v['sid'],t) for v in plan for t in [v['entry'],v['exits']['1h'],v['exits']['4h']]},key=lambda z:(z[1],z[0]))
    need(len(wanted)==30 and all(START<=t<END and t%3600==900 for _,t in wanted),'BOUNDARY_PLAN')
    need(len({v['sid'] for v in plan})==2,'IDENTITY_COUNT')
    for v in plan:need(v['exits']['1h']-v['entry']==3600 and v['exits']['4h']-v['entry']==14400 and v['saved_causal_economics']['research_pass'],'HORIZON_PLAN')
    return s,plan,wanted
def capture(head,auth,tmp,key,fp,wanted,prior,digits):
    quotes={(q['symbol_id'],q['boundary_ms']//1000):q for q in prior['private_boundary_receipts']};reused=sum(k in quotes for k in wanted)
    need(reused==0,'CLOCK_MISMATCH_EXPECTATION');requests=0;transport=None;auth_status='NOT_ATTEMPTED';errors=Counter()
    checkpoint=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real')
    checkpoint.release=e.w.old.api('releases',{'tag_name':'mxm-executable-quote-checkpoints-'+auth['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted bounded historical quote completion checkpoints','prerelease':True,'body':'Encrypted read-only acquisition receipts; no public numeric market data.'})
    def persist(label):
        checkpoint.encrypted({'schema':'mxm.private.executable.quote.checkpoint.v1','source_head':head,'requests':requests,'wanted_count':len(wanted),'quotes':[quotes[k] for k in wanted if k in quotes],'authentication':auth_status},'capture-'+label+'.mxmenc')
    try:
        credentials=[os.environ.get(k) for k in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')]
        if not all(credentials):
            auth_status='EXISTING_RUNNER_CREDENTIAL_ABSENT';persist('blocked');return quotes,requests,reused,auth_status,dict(errors),checkpoint.release
        transport=StdlibCTraderTransport();transport.connect()
        account=authenticate_segment(transport,*credentials);auth_status='PASS_UNCHANGED_EXPLICIT_VIEW_AND_ACCOUNT_FINGERPRINT'
        rate=RateLimiter(min_interval=.25)
        for sid,t in wanted:
            if (sid,t) in quotes:continue
            sides={};rawpages=[];ms=t*1000
            for name,kind in [('bid',enums.BID),('ask',enums.ASK)]:
                need(requests<auth['max_tick_requests'],'TICK_REQUEST_BUDGET');require_read_only_request('ProtoOAGetTickDataReq');rate.before_send()
                request=m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=sid,type=kind,fromTimestamp=ms-60000,toTimestamp=ms)
                response=transport.request(request,timeout=20);requests+=1
                if isinstance(response,m.ProtoOAErrorRes):
                    sides[name]={'state':'PROVIDER_ERROR','code':response.errorCode};rawpages.append({'side':name,'error_code':response.errorCode,'request_from_ms':ms-60000,'request_to_ms':ms});errors[response.errorCode]+=1;continue
                need(isinstance(response,m.ProtoOAGetTickDataRes),'RESPONSE_TYPE')
                need(int(response.ctidTraderAccountId)==account,'RESPONSE_ACCOUNT_BINDING')
                encoded=[{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in response.tickData]
                page=decode_ctrader_tick_page(encoded);need(all(ms-60000<=x.timestamp_ms<=ms for x in page),'TICK_TIMESTAMP_DOMAIN')
                rawpages.append({'side':name,'encoded_tick_rows':encoded,'hasMore':bool(response.hasMore),'request_from_ms':ms-60000,'request_to_ms':ms})
                if not page:sides[name]={'state':'NO_QUOTE_IN_FIXED_60_SECOND_WINDOW'}
                else:
                    last=page[-1];sides[name]={'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':last.timestamp_ms,'raw_tick':last.raw_tick,'price':round(last.raw_tick/100000,digits[sid]),'age_ms':ms-last.timestamp_ms,'source_has_more':bool(response.hasMore)}
            both=all(sides[k]['state']=='AUTHENTIC_CAUSAL_QUOTE' for k in ('bid','ask')) and 0<sides['bid'].get('price',0)<=sides['ask'].get('price',0)
            quotes[sid,t]={'symbol_id':sid,'boundary_ms':ms,'sides':sides,'two_sided_quote_available':both,'freshness_threshold_applied':False,'historical_fees_verified':False,'fills_observed':False,'raw_pages':rawpages}
            if requests%16==0:persist(str(requests))
            e.w.old.budget(maxwall=1200,maxcpu=700,maxkib=2097152)
        persist('complete')
    except Exception:
        persist('interrupted');raise
    finally:
        if transport:transport.close()
    return quotes,requests,reused,auth_status,dict(errors),checkpoint.release
def cost_support(summary,plan,quotes,cost):
    metadata={int(r['symbol_id']):r for r in cost['metadata_rows']};native=cost['current_native_evidence']['private_native_evidence'];episodes=[]
    for episode in plan:
        sid=episode['sid'];r=metadata[sid];ep=dict(episode);ep['horizons']={};q0=point(quotes.get((sid,episode['entry'])))
        for horizon,t in episode['exits'].items():
            q1=point(quotes.get((sid,t)));d={'entry_quote_valid':q0 is not None,'exit_quote_valid':q1 is not None,'both':q0 is not None and q1 is not None,'fills_observed':False,'signal_or_PnL_computed':False}
            if d['both']:
                # Half-spread at each boundary: pure cost context, no directional return.
                spread=.5*(q0['spread_bps']+q1['spread_bps']);f=fee(r,native,q0['mid']);units=int(r['min_volume_cents'])/100
                qeur=episode['saved_causal_economics']['reference_quote_to_eur'];notional=units*q0['mid']*qeur
                d.update(entry_spread_bps=q0['spread_bps'],exit_spread_bps=q1['spread_bps'],symmetric_two_boundary_spread_context_bps=spread,
                  current_commission_scenario_bps=f['bps'],minimum_units=units,step_units=int(r['step_volume_cents'])/100,
                  minimum_reference_notional_eur=notional,current_captured_worst_min_margin_eur=max(float(r['buy_margin_eur']),float(r['sell_margin_eur'])),
                  reference_after_spread_commission_plus2bps_cash=notional*(spread+f['bps']+2)/10000 if f['bps'] is not None else None,
                  funding_swap_rollover_slippage_and_dated_fees='UNKNOWN_NOT_ZERO',conversion='SAVED_CAUSAL_COMPLETED_M5_FX_REFERENCE_NOT_EXECUTABLE_BID_FX',
                  gap_stop_drawdown_and_survival='NOT_CERTIFIED')
            ep['horizons'][horizon]=d
        episodes.append(ep)
    byid=[]
    for identity in summary['diagnostic_acquisition_priority']:
        sid=identity['sid'];own=[x for x in episodes if x['sid']==sid]
        byid.append({'sid':sid,'symbol':identity['symbol'],'contract':identity['contract'],'saved_cross_period_support':identity['support'],
          'horizons':{h:{'attempted':len(own),'both':sum(v['horizons'][h]['both'] for v in own),
             'complete_weeks':{w:{'attempted':sum(v['week']==w for v in own),'both':sum(v['week']==w and v['horizons'][h]['both'] for v in own)} for w in ('2026-W35','2026-W36','2026-W37')},
             'original_blocks':{str(b):{'attempted':sum((v['entry']-START)//604800==b for v in own),'both':sum((v['entry']-START)//604800==b and v['horizons'][h]['both'] for v in own)} for b in range(4)},
             'symmetric_spread_context_bps':summarize(v['horizons'][h].get('symmetric_two_boundary_spread_context_bps') for v in own),
             'current_commission_bps':summarize(v['horizons'][h].get('current_commission_scenario_bps') for v in own)} for h in ('1h','4h')}})
    return episodes,byid
def main():
    global PHASE
    os.umask(0o077);head,auth=gate()
    with tempfile.TemporaryDirectory(prefix='mxm-bounded-quote-completion-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'KEY_BINDING')
        PHASE='EXISTING_FROZEN_DIAGNOSTIC_AND_COST_INPUTS';diag,dp=load_asset(key,fp,tmp,auth['diagnostic_source']);prior,qp=load_asset(key,fp,tmp,auth['quote_source']);cost,cp=load_asset(key,fp,tmp,auth['cost_source'])
        summary,plan,wanted=plan_check(diag);digits=e.w.old.verify_science()[2]
        PHASE='UNCHANGED_VIEW_AUTH_AND_BOUNDED_HISTORICAL_TICKS';quotes,requests,reused,auth_status,errors,checkpoint=capture(head,auth,tmp,key,fp,wanted,prior,digits)
        PHASE='QUOTE_AND_COST_AVAILABILITY_ONLY';episodes,identities=cost_support(summary,plan,quotes,cost)
        out={'schema':'mxm.private.bounded.executable.quote.completion.v1','source_head':head,'input_provenance':[dp,qp,cp],
          'frozen_diag_source_head':'27d46b0f92391c22cc927ca36739c22ff980833a','plan_episodes':len(plan),'wanted_boundaries':len(wanted),'completed_boundaries':sum(k in quotes for k in wanted),'reused_boundaries':reused,
          'new_tick_requests':requests,'authentication':auth_status,'provider_errors':errors,
          'boundary_quality':dict(Counter(boundary_quality(quotes[k]) for k in wanted if k in quotes)),
          'identities':identities,'episodes':episodes,'encrypted_checkpoint_release_id':checkpoint['id'],
          'pagination':'EXISTING_DECODER_UNCHANGED;ONE_60S_PAGE_PER_SIDE;HAS_MORE_TRUE_EXCLUDED_FROM_VALID_SUPPORT;NO_CLAIM_OF_COMPLETE_WINDOW_WHEN_TRUNCATED',
          'historical_NET':'UNKNOWN_NOT_ZERO','fills':0,'orders':0,'protected_forward':False,'cloud_deployment':False,
          'closed_signal_model_or_PnL_replayed':False,'new_directional_experiment':False,'robust_NET':False,'HARD21':False,
          'economic_verdict':'INSUFFICIENT_CROSS_PERIOD_SUPPORT_FOR_NEW_DIRECTIONAL_EXPERIMENT;BOUNDED_QUOTE_AVAILABILITY_INFORMATION_ONLY',
          'native_scope':'READ_ONLY_PEPPERSTONE_CTRADER_NATIVE_DATA;NO_FINAL_CBOT_EXTERNAL_RUNTIME_DEPENDENCY'}
        PHASE='OWNER_ENCRYPTED_DELIVERY';rt.output(head,auth,tmp,key,'executablequotes',{'summary':out,'private_boundary_receipts':[quotes[k] for k in wanted if k in quotes]},out)
        PHASE='ENCRYPTED_SESSION_RELAY';relay(head,auth,tmp,out)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
