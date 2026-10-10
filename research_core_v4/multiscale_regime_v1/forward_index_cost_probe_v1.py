"""Post-selection DEVELOPMENT cost diagnosis, no model rerun or gate rescue."""
import json,os,tempfile,pathlib,math
from collections import Counter,defaultdict
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.owner_recovery_v1.readback_v1 import describe,iso
from research_core_v4.multiscale_regime_v1.cost_universe_v1 import eligibility
from research_core_v4.multiscale_regime_v1.kernel_v1 import n
e=rt.e;P='research_core_v4/multiscale_regime_v1/';PHASE='GATE'
def main():
    global PHASE
    os.umask(0o077);head=os.environ['GITHUB_SHA'];e.w.v2.runtime(head);a=json.loads((e.a.ROOT/(P+'FORWARD_COST_EXECUTION_V1.json')).read_text())
    e.w.old.need(a['orders'] is False and a['protected_forward'] is False and a['scientific_replay'] is False,'FORWARD_COST_SCOPE')
    e.w.old.need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-forward-index-cost-diagnostic-v1.yml@refs/heads/'+e.w.old.BRANCH,'FORWARD_COST_WORKFLOW');e.a.ancestor(a['base_head'],head)
    e.w.old.need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'FORWARD_COST_EXPIRED')
    for p,h in a['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'FORWARD_COST_SOURCE')
    original=json.loads((e.a.ROOT/(e.P+'EXACT_COVERAGE_PREARM_V1.json')).read_text())
    for p,h in original['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'ORIGINAL_SOURCE')
    claim='mxm-forward-cost-diagnostic-'+a['invocation_id'];e.w.old.need(not e.w.v2.existing_ref(claim),'FORWARD_COST_CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+claim,'sha':head})
    master,_,digits,_=e.w.old.verify_science();master={m['symbol_id']:m for m in master}
    with tempfile.TemporaryDirectory(prefix='mxm-forward-cost-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);e.w.old.need(fp==e.w.old.FP,'FORWARD_COST_KEY')
        science,sp=load_asset(key,fp,tmp,a['science_source']);cost,cp=load_asset(key,fp,tmp,a['cost_source']);att,_=load_asset(key,fp,tmp,a['science_attestation'])
        e.w.old.need(att['primary']['canonical_sha256']==sp['canonical_sha256'],'FORWARD_COST_ATTESTATION')
        metadata={int(r['symbol_id']):r for r in cost['metadata_rows']};ids={sid for sid,r in metadata.items() if sid in master and r['asset_class']=='Forwards - Indices' and r['broker_symbol']==master[sid]['symbol'] and eligibility(r)[0]};e.w.old.need(len(ids)==2,'FORWARD_COST_CLASS_COUNT')
        fields=science['trial_fields'];events=[]
        for r in science['all_identity_trials_and_denominators']['SERIAL_LOCATION_CHANGE']:
            if r['symbol_id'] in ids:
                for tr in r['trials']:events.append({'symbol_id':r['symbol_id'],**dict(zip(fields,tr))})
        e.w.old.need(len(events)==196 and sum(ev['y'] is not None for ev in events)==159,'FORWARD_COST_EVENT_COUNTS')
        old=json.loads((e.a.ROOT/'research_core_v4/synchronized_breadth_v1/EXECUTION_V1.json').read_text());prior,_=load_asset(key,fp,tmp,old['fullcost_source']);quotes={(q['symbol_id'],q['boundary_ms']):q for q in prior['private_boundary_receipts']};all_boundaries={(ev['symbol_id'],ev[k]*1000) for ev in events for k in ('action','exit')};wanted=sorted((sid,t) for sid,t in all_boundaries if n.START*1000<=t<=n.END*1000);censored=len(all_boundaries)-len(wanted);e.w.old.need(len(wanted)<=392,'FORWARD_COST_DOMAIN');e.w.old.need(all(ev['model']!=0 for ev in events),'FORWARD_COST_FLAT_MODEL')
        from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import authenticate_segment,RateLimiter,StdlibCTraderTransport,m,enums,decode_ctrader_tick_page
        from m6.ctrader_capture import require_read_only_request
        checkpoint=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');checkpoint.release=e.w.old.api('releases',{'tag_name':'mxm-forward-cost-checkpoints-'+a['invocation_id'][:12]+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'Encrypted forward-index cost diagnosis recovery','prerelease':True,'body':'Encrypted private recovery receipts only.'})
        transport=StdlibCTraderTransport();requests=0;new=[];access='COMPLETE';blocker=None;reused=sum(k in quotes for k in wanted)
        def persist(label):checkpoint.encrypted({'new_quotes':new,'requests':requests,'scientific_models_replayed':False},'forward-cost-'+label+'.mxmenc')
        try:
            PHASE='VIEW_ONLY_NEW_BOUNDARIES';transport.connect();account=authenticate_segment(transport,*[os.environ[k] for k in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')]);limiter=RateLimiter(min_interval=.25)
            for sid,t in wanted:
                if (sid,t) in quotes:continue
                sides={};pages=[]
                for name,kind in [('bid',enums.BID),('ask',enums.ASK)]:
                    e.w.old.need(requests<784,'FORWARD_COST_REQUEST_BUDGET');limiter.before_send();req=m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=sid,type=kind,fromTimestamp=t-60000,toTimestamp=t);require_read_only_request(type(req).__name__);res=transport.request(req,timeout=20);requests+=1
                    if isinstance(res,m.ProtoOAErrorRes):sides[name]={'state':'PROVIDER_ERROR','code':res.errorCode};pages.append({'side':name,'provider_error':res.errorCode});continue
                    e.w.old.need(isinstance(res,m.ProtoOAGetTickDataRes),'FORWARD_COST_RESPONSE');enc=[{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in res.tickData];page=decode_ctrader_tick_page(enc);e.w.old.need(all(t-60000<=v.timestamp_ms<=t for v in page),'FORWARD_COST_CAUSAL_TICKS');pages.append({'side':name,'encoded_ticks':enc,'hasMore':bool(res.hasMore)})
                    if not page:sides[name]={'state':'NO_QUOTE_IN60S'}
                    else:
                        v=page[-1];sides[name]={'state':'AUTHENTIC_CAUSAL_QUOTE','price':round(v.raw_tick/100000,digits[sid]),'timestamp_ms':v.timestamp_ms,'age_ms':t-v.timestamp_ms,'source_has_more':bool(res.hasMore)}
                valid=all(sides[s].get('state')=='AUTHENTIC_CAUSAL_QUOTE' for s in ('bid','ask')) and 0<sides['bid'].get('price',0)<=sides['ask'].get('price',0);q={'symbol_id':sid,'boundary_ms':t,'sides':sides,'two_sided_quote_available':valid,'raw_pages':pages};quotes[sid,t]=q;new.append(q)
                if requests%128==0:persist(str(requests));print('PRIVATE_COST_DIAGNOSTIC_CONTINUES',flush=True)
        except Exception as exc:access='ACCESS_OR_TRANSPORT_BLOCKED';blocker=type(exc).__name__
        finally:transport.close();persist('final-'+str(requests))
        PHASE='PRIVATE_ECONOMIC_INTERSECTION';counts=Counter({'DOMAIN_CENSORED_EXIT_NOT_REQUESTED':censored});blocks=defaultdict(lambda:Counter());marks=defaultdict(list);isomarks=defaultdict(list);private=[];ages=[];hasmore=0
        for ev in events:
            qs=[quotes.get((ev['symbol_id'],ev[k]*1000)) for k in ('action','exit')];matched=[q is not None and q['two_sided_quote_available'] for q in qs];cat='BOTH_BOUNDARIES' if all(matched) else 'PARTIAL_BOUNDARY' if any(matched) else 'NO_MATCHED_BOUNDARY';support='SUPPORTED' if ev['y'] is not None else 'DOMAIN_CENSOR' if ev['reason']=='DOMAIN_CENSOR' else 'LABEL_GAP';w=ev['clock']//168;counts[cat]+=1;counts[support+'_'+cat]+=1;blocks[w][support+'_'+cat]+=1;value=None
            if all(matched):
                b0=qs[0]['sides']['bid']['price'];a0=qs[0]['sides']['ask']['price'];b1=qs[1]['sides']['bid']['price'];a1=qs[1]['sides']['ask']['price'];age=max(s['age_ms'] for q in qs for s in q['sides'].values());ages.append(age);more=any(s.get('source_has_more',False) for q in qs for s in q['sides'].values());hasmore+=int(more)
                d=(ev['model']>0)-(ev['model']<0);d0=(ev['baseline']>0)-(ev['baseline']<0);mid=10000*math.log((a1+b1)/(a0+b0));value={'model_midpoint_bps':d*mid,'model_quote_side_bps':10000*math.log(b1/a0) if d>0 else 10000*math.log(b0/a1),'baseline_quote_side_bps':10000*math.log(b1/a0) if d0>0 else 10000*math.log(b0/a1),'max_quote_age_ms':age,'hasMore':more};value['spread_drag_bps']=value['model_midpoint_bps']-value['model_quote_side_bps']
                if age>60000:counts['STALE_OVER60S']+=1
                else:marks[(w,support)].append(value);isomarks[(iso(ev['action']),support)].append(value)
            private.append({'event':ev,'coverage':cat,'quote_markout':value})
        fields=('model_midpoint_bps','model_quote_side_bps','baseline_quote_side_bps','spread_drag_bps','max_quote_age_ms')
        summarise=lambda vals:{f:describe([v[f] for v in vals]) for f in fields}
        summary={'schema':'mxm.private.forward.index.cost.diagnostic.v1','scope':'POST_SELECTION_DEVELOPMENT_ENTIRE_PREDEFINED_ELIGIBLE_FORWARD_INDEX_CLASS;NO_MODEL_OR_THRESHOLD_RESCUE','identities':2,'events':196,'supported_reference_events':159,'unsupported_reference_events':37,'unique_in_domain_boundaries':len(wanted),'unrequested_out_of_domain_boundaries':censored,'new_historical_bid_ask_requests':requests,'reused_boundaries':reused,'access_status':access,'blocker_class':blocker,'coverage':dict(counts),'block_coverage':{str(k):dict(v) for k,v in blocks.items()},'four_blocks':[{'block':w,'response_support':s,**summarise(v)} for (w,s),v in sorted(marks.items())],'ISO_UTC':[{'iso_week':w,'response_support':s,'full_iso_week':w in ('2026-W35','2026-W36','2026-W37'),**summarise(v),'actual_entries':0,'positive_expectancy_certified_entries':0} for (w,s),v in sorted(isomarks.items())],'quote_age_ms':describe(ages),'events_hasMore':hasmore,'current_minimum_ticket_margins_eur':describe([max(float(metadata[s]['buy_margin_eur']),float(metadata[s]['sell_margin_eur'])) for s in ids]),'simultaneous_two_minimum_tickets_current_margin_eur':sum(max(float(metadata[s]['buy_margin_eur']),float(metadata[s]['sell_margin_eur'])) for s in ids),'current_commission_contracts':[{'rate':metadata[s]['commission_rate_normalized'],'unit':metadata[s]['commission_rate_unit'],'minimum':metadata[s]['min_commission_normalized']} for s in sorted(ids)],'commission_point_in_time_history':'UNKNOWN;CURRENT_CAPTURE_NOT_ZERO_SUBSTITUTION','financing_conversion_slippage':'UNKNOWN;QUOTE_SENSITIVITY_MINUS2_5_10BPS;NO_FILL_RECEIPTS','selection_exposure':'Global two-law comparisons and allasset classes viewed before selecting whole forward-index class. Original minimum20identity promotion gate failed and remains failed. Cost results are descriptive and cannot rescue it. Original2identity scientific support and own baseline retained','sources':{'science':sp,'current_cost':cp},'scientific_models_replayed':False,'independent_confirmation':False,'net_certified':False,'HARD21_certified':False,'actual_fills':0,'protected_forward':False,'orders':0,'quote_semantics':'LAST_RETURNED_CAUSAL_BID_ASK_IN60S;PAGE_HASMORE_PRESERVED_NO_EXECUTABLE_FILL_OR_POINT_IN_TIME_FEE_CERTIFICATE'}
        PHASE='ENCRYPTED_DELIVERY';rt.output(head,a,tmp,key,'forwardcost',{'summary':summary,'private_event_quote_intersection':private,'private_new_boundary_receipts':new},summary)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
