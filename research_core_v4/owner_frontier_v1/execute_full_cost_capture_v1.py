"""Complete bounded 4205-event authentic quote-state cost intersection.

Reuses all persisted pilot boundary receipts. Quote-side markouts are measured
top-of-book price references before unknown fees/slippage/financing, never fills.
"""
import gzip,json,math,os,pathlib,tempfile,time
from collections import Counter
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import authenticate_segment,RateLimiter,StdlibCTraderTransport,m,enums,decode_ctrader_tick_page
e=rt.e
PHASE='GATE'

def load_asset(key,fp,tmp,release_id,asset_id,digest):
    assets=e.w.old.api('releases/'+str(release_id)+'/assets?per_page=100');asset=next(x for x in assets if x['id']==asset_id)
    e.w.old.need(asset['digest']=='sha256:'+digest,'EXACT_ASSET_BINDING');blob=e.w.old.download(asset['browser_download_url'],asset['size']);e.w.old.need(e.a.sha(blob)==digest,'EXACT_ASSET_BYTES')
    raw=gzip.decompress(e.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp));value=e.w.old.crypto.strict_json(raw);e.w.old.need(e.a.enc(value)==raw,'EXACT_ASSET_CANONICAL');return value

def gate():
    head=os.environ['GITHUB_SHA'];e.w.v2.runtime(head);auth=json.loads((e.a.ROOT/(rt.P+'OWNER_FULL_COST_CAPTURE_V1.json')).read_text())
    e.w.old.need(auth['authority']=='EXPLICIT_OWNER_NECESSARY_READ_ONLY_HISTORICAL_DATA_COLLECTION' and auth['scope']['events']==4205 and auth['scope']['historical_domain_only'] is True and auth['scope']['orders'] is False and auth['independent_acceptance_claimed'] is False,'FULL_CAPTURE_OWNER_SCOPE')
    e.a.ancestor(auth['base_head'],head)
    for p,h in auth['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'FULL_CAPTURE_SOURCE_DRIFT')
    old=json.loads((e.a.ROOT/(e.P+'EXACT_COVERAGE_PREARM_V1.json')).read_text())
    for p,h in old['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'ORIGINAL_FROZEN_SOURCE_DRIFT')
    claim='mxm-owner-full-cost-capture-'+auth['invocation_id'];e.w.old.need(not e.w.v2.existing_ref(claim),'FULL_CAPTURE_CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+claim,'sha':head})
    return head,auth,e.w.old.verify_science()[0]

def markout(event,entry,exit):
    if not all(x and x['two_sided_quote_available'] for x in (entry,exit)):return None
    b0,a0=entry['sides']['bid']['price'],entry['sides']['ask']['price'];b1,a1=exit['sides']['bid']['price'],exit['sides']['ask']['price'];d=event['direction']
    gross=d*10000*math.log((b1+a1)/(b0+a0));side=10000*math.log(b1/a0 if d==1 else b0/a1);drag=gross-side
    e.w.old.need(all(math.isfinite(x) for x in (gross,side,drag)) and drag>=-1e-8,'QUOTE_MARKOUT_VALIDITY')
    return {'midpoint_reference_directional_bps':gross,'quote_side_markout_before_other_friction_bps':side,'two_boundary_spread_drag_bps':drag,'actual_fill':False,'all_other_friction':'UNKNOWN_NOT_ZERO'}

def main():
    global PHASE
    os.umask(0o077);head,auth,master=gate();digits=e.w.old.verify_science()[2]
    with tempfile.TemporaryDirectory(prefix='mxm-full-cost-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);e.w.old.need(fp==e.w.old.FP,'KEY_BINDING')
        original=load_asset(key,fp,tmp,408254080,625914390,'160e2246b28e5789b07a698535b2c735a70ea15bd43f09e0af4df4922241de77')
        pilot=load_asset(key,fp,tmp,408264664,625943478,'f7d5fe373f437a5412390ba73e92d9e4d979755da6ca605f011beee87f5f6566')
        events=[r['event'] for r in original['private_event_coverage']['records']];e.w.old.need(len(events)==4205 and pilot['summary']['historical_tick_requests']==512,'ORIGINAL_COUNTS')
        quotes={(x['symbol_id'],x['boundary_ms']):x for x in pilot['request_boundary_index']};reused=len(quotes)
        wanted=sorted({(ev['symbol_id'],t*1000) for ev in events for t in (ev['entry_reference_boundary'],ev['exit_reference_boundary'])},key=lambda x:(x[1],x[0]))
        e.w.old.need(len(wanted)<=8410 and all(e.w.n.START*1000<=t<=e.w.n.END*1000 for _,t in wanted),'BOUNDARY_DOMAIN')
        PHASE='AUTHENTICATION';transport=StdlibCTraderTransport();transport.connect()
        account=authenticate_segment(transport,os.environ['CTRADER_CLIENT_ID'],os.environ['CTRADER_CLIENT_SECRET'],os.environ['CTRADER_ACCESS_TOKEN'])
        requests=0;limiter=RateLimiter(min_interval=0.25)
        checkpoint=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real')
        checkpoint.release=e.w.old.api('releases',{'tag_name':'mxm-owner-fullcost-checkpoints-'+auth['invocation_id'][:12]+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted historical capture checkpoints','prerelease':True,'body':'Encrypted private acquisition recovery receipts only; no scientific results in public output.'})
        def persist_checkpoint(label):
            checkpoint.encrypted({'schema':'mxm.private.historical.capture.checkpoint.v1','source_head':head,'new_requests':requests,'quotes':list(quotes.values())},'capture-'+label+'.mxmenc')
        try:
            PHASE='AUTHENTIC_HISTORICAL_CAPTURE'
            for index,(symbol,t) in enumerate(wanted):
                if (symbol,t) in quotes:continue
                sides={};rawpages=[]
                for name,kind in [('bid',enums.BID),('ask',enums.ASK)]:
                    limiter.before_send();response=transport.request(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=symbol,type=kind,fromTimestamp=t-60000,toTimestamp=t),timeout=20);requests+=1
                    e.w.old.need(requests<=16820,'REQUEST_BUDGET')
                    if isinstance(response,m.ProtoOAErrorRes):
                        sides[name]={'state':'PROVIDER_ERROR','code':response.errorCode};rawpages.append({'side':name,'error_code':response.errorCode});continue
                    e.w.old.need(isinstance(response,m.ProtoOAGetTickDataRes),'HISTORICAL_RESPONSE_TYPE')
                    encoded=[{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in response.tickData];page=decode_ctrader_tick_page(encoded);e.w.old.need(all(t-60000<=x.timestamp_ms<=t for x in page),'HISTORICAL_TICK_DOMAIN')
                    rawpages.append({'side':name,'encoded_tick_rows':encoded,'hasMore':bool(response.hasMore),'request_from_ms':t-60000,'request_to_ms':t})
                    if not page:sides[name]={'state':'NO_QUOTE_IN_FIXED_60_SECOND_WINDOW'}
                    else:
                        last=page[-1];sides[name]={'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':last.timestamp_ms,'raw_tick':last.raw_tick,'price':round(last.raw_tick/100000,digits[symbol]),'age_ms':t-last.timestamp_ms,'source_has_more':bool(response.hasMore)}
                valid=all(sides[x].get('state')=='AUTHENTIC_CAUSAL_QUOTE' for x in ('bid','ask')) and 0<sides['bid'].get('price',0)<=sides['ask'].get('price',0)
                quotes[(symbol,t)]={'symbol_id':symbol,'boundary_ms':t,'sides':sides,'two_sided_quote_available':valid,'freshness_threshold_applied':False,'historical_fees_verified':False,'fills_observed':False,'raw_pages':rawpages}
                if requests%512==0:
                    persist_checkpoint(str(requests));print('PRIVATE_AUTHENTIC_CAPTURE_CONTINUES',flush=True)
                e.w.old.budget(maxwall=6600,maxcpu=1800,maxkib=2097152)
        except Exception:
            persist_checkpoint('interrupted-'+str(requests));raise
        finally:transport.close()
        persist_checkpoint('complete-'+str(requests))
        PHASE='EXACT_INTERSECTION';records=[];counts=Counter();weekcounts=[Counter() for _ in range(4)];aggregates={}
        for event in events:
            ent=quotes[(event['symbol_id'],event['entry_reference_boundary']*1000)];ex=quotes[(event['symbol_id'],event['exit_reference_boundary']*1000)]
            category=('NO_MATCHED_BOUNDARY','PARTIAL_BOUNDARY','BOTH_BOUNDARIES')[int(ent['two_sided_quote_available'])+int(ex['two_sided_quote_available'])];counts[category]+=1;weekcounts[event['fixed_week']][category]+=1
            value=markout(event,ent,ex);record={'event':event,'coverage':category,'quote_markout':value};records.append(record)
            k=(event['fixed_week'],event['response_support_status']);s=aggregates.setdefault(k,{'events':0,'both_boundaries':0,'midpoint_reference_sum_bps':0.,'quote_side_markout_sum_bps':0.,'spread_drag_sum_bps':0.,'positive_quote_side_markouts':0})
            s['events']+=1
            if value is not None:
                s['both_boundaries']+=1;s['midpoint_reference_sum_bps']+=value['midpoint_reference_directional_bps'];s['quote_side_markout_sum_bps']+=value['quote_side_markout_before_other_friction_bps'];s['spread_drag_sum_bps']+=value['two_boundary_spread_drag_bps'];s['positive_quote_side_markouts']+=int(value['quote_side_markout_before_other_friction_bps']>0)
        summary={'schema':'mxm.private.full.authentic.cost.intersection.v1','scope_events':4205,'supported_events':3321,'label_gap_events':884,'all_four_weeks_complete':True,'all_unique_boundaries_attempted':len(quotes)==len(wanted),'unique_boundaries':len(wanted),'reused_pilot_boundaries':reused,'new_historical_tick_requests':requests,'prior_pilot_historical_tick_requests':512,'coverage_counts':dict(counts),'four_week_counts':[dict(x) for x in weekcounts],'quote_markouts_by_fixed_week_and_support':[{'fixed_week':k[0],'response_support':k[1],**v,'mean_quote_side_markout_bps':v['quote_side_markout_sum_bps']/v['both_boundaries'] if v['both_boundaries'] else None,'mean_spread_drag_bps':v['spread_drag_sum_bps']/v['both_boundaries'] if v['both_boundaries'] else None} for k,v in sorted(aggregates.items())],'authentication':'PASS_EXISTING_EXPLICIT_VIEW_ACCOUNT_FINGERPRINT','original_scientific_response_recomputed':False,'quote_references_are_fills':False,'fees_conversion_slippage_financing':'UNRESOLVED_NOT_ZERO','net_edge_established':False,'protected_forward':False,'orders':0,'request_interval_seconds':0.25,'causal_quote_window_seconds':60,'missing_older_than_window_preserved':True,'all1576_identity_four_week_counts':[{'ordinal':i+1,'symbol_id':m['symbol_id'],'weeks':[{cat:sum(r['event']['ordinal']==i+1 and r['event']['fixed_week']==w and r['coverage']==cat for r in records) for cat in ('BOTH_BOUNDARIES','PARTIAL_BOUNDARY','NO_MATCHED_BOUNDARY')} for w in range(4)]} for i,m in enumerate(master)]}
        PHASE='ENCRYPTED_DELIVERY';rt.output(head,auth,tmp,key,'fullcost',{'summary':summary,'private_event_coverage':records,'private_boundary_receipts':list(quotes.values())},summary)

if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
