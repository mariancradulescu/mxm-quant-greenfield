"""Bounded authentic historical quote probe, read-only VIEW account binding.

Deterministic cohort by asset class/week/ordinal, no economic-outcome selection.
No orders, subscriptions, account mutation or fabricated quotes.
"""
import gzip,json,os,pathlib,tempfile,time
from collections import Counter
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.shallow_m5_support_v2_production import authenticate_segment,RateLimiter,SystemicFailure
from m6.ctrader_transport import StdlibCTraderTransport
from m6.ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as enums
from m6.cost_evidence import decode_ctrader_tick_page
e=rt.e
PHASE='GATE'

def select(events,master):
    byid={x['symbol_id']:x for x in master};buckets={}
    for event in sorted(events,key=lambda x:(x['ordinal'],x['decision_timestamp'])):
        if event['response_support_status']!='SUPPORTED':continue
        key=(byid[event['symbol_id']]['asset_class'],event['fixed_week']);bucket=buckets.setdefault(key,[])
        if len(bucket)<2 and event['symbol_id'] not in {x['symbol_id'] for x in bucket}:bucket.append(event)
    return sorted([x for values in buckets.values() for x in values],key=lambda x:(x['fixed_week'],x['ordinal'],x['decision_timestamp']))[:128]

def main():
    global PHASE
    os.umask(0o077);head,auth,master,entries,digits,manifest=rt.gate('quotes')
    with tempfile.TemporaryDirectory(prefix='mxm-authentic-quotes-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);e.w.old.need(fp==e.w.old.FP,'KEY_BINDING')
        rel=e.w.old.api('releases/408254080');assets=e.w.old.api('releases/408254080/assets?per_page=100');asset=next(x for x in assets if x['id']==625914390)
        e.w.old.need(asset['digest']=='sha256:160e2246b28e5789b07a698535b2c735a70ea15bd43f09e0af4df4922241de77','ORIGINAL_COVERAGE_ASSET')
        blob=e.w.old.download(asset['browser_download_url'],asset['size']);e.w.old.need(e.a.sha(blob)==asset['digest'][7:],'ORIGINAL_COVERAGE_BYTES')
        raw=gzip.decompress(e.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp));old=e.w.old.crypto.strict_json(raw);e.w.old.need(e.a.enc(old)==raw,'ORIGINAL_COVERAGE_CANONICAL')
        events=[r['event'] for r in old['private_event_coverage']['records']];selected=select(events,master);quotes={};receipts=[];auth_status='NOT_ATTEMPTED';requests=0
        credentials={name:bool(os.environ.get(name)) for name in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')};transport=None
        PHASE='READ_ONLY_AUTHENTICATION'
        if not all(credentials.values()):auth_status='REQUIRED_EXISTING_CREDENTIAL_ABSENT'
        else:
            try:
                transport=StdlibCTraderTransport();transport.connect()
                account=authenticate_segment(transport,os.environ['CTRADER_CLIENT_ID'],os.environ['CTRADER_CLIENT_SECRET'],os.environ['CTRADER_ACCESS_TOKEN']);auth_status='PASS_EXPLICIT_VIEW_AND_EXISTING_ACCOUNT_FINGERPRINT'
                PHASE='HISTORICAL_QUOTES';limiter=RateLimiter(min_interval=0.25)
                for event in selected:
                    for t in (event['entry_reference_boundary']*1000,event['exit_reference_boundary']*1000):
                        symbol=event['symbol_id'];identity=(symbol,t)
                        if identity in quotes:continue
                        e.w.old.need(e.w.n.START*1000<=t<=e.w.n.END*1000,'HISTORICAL_DOMAIN')
                        sides={};rawpages=[]
                        for name,kind in [('bid',enums.BID),('ask',enums.ASK)]:
                            limiter.before_send();request=m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=symbol,type=kind,fromTimestamp=t-60000,toTimestamp=t)
                            response=transport.request(request,timeout=20);requests+=1
                            if isinstance(response,m.ProtoOAErrorRes):
                                sides[name]={'state':'PROVIDER_ERROR','code':response.errorCode};rawpages.append({'side':name,'error_code':response.errorCode});continue
                            e.w.old.need(isinstance(response,m.ProtoOAGetTickDataRes),'HISTORICAL_RESPONSE_TYPE')
                            encoded=[{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in response.tickData];page=decode_ctrader_tick_page(encoded)
                            e.w.old.need(all(t-60000<=r.timestamp_ms<=t for r in page),'HISTORICAL_TICK_DOMAIN')
                            rawpages.append({'side':name,'encoded_tick_rows':encoded,'hasMore':bool(response.hasMore),'request_from_ms':t-60000,'request_to_ms':t})
                            if not page:sides[name]={'state':'NO_QUOTE_IN_FIXED_60_SECOND_WINDOW'}
                            else:
                                last=page[-1];sides[name]={'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':last.timestamp_ms,'raw_tick':last.raw_tick,'price':round(last.raw_tick/100000,digits[symbol]),'age_ms':t-last.timestamp_ms,'source_has_more':bool(response.hasMore)}
                        valid=all(sides[x].get('state')=='AUTHENTIC_CAUSAL_QUOTE' for x in ('bid','ask')) and 0<sides['bid'].get('price',0)<=sides['ask'].get('price',0)
                        quotes[identity]={'symbol_id':symbol,'boundary_ms':t,'sides':sides,'two_sided_quote_available':valid,'freshness_threshold_applied':False,'historical_fees_verified':False,'fills_observed':False,'raw_pages':rawpages}
                        e.w.old.budget(maxwall=900,maxcpu=600,maxkib=2097152)
            except SystemicFailure as exc:
                # Fixed code class, no access tokens/account data in summary or stdout.
                auth_status=str(exc) if str(exc) in ('TOKEN_INVALID_OR_EXPIRED','ACCOUNT_FINGERPRINT_MISMATCH','SCOPE_NOT_EXPLICIT_VIEW','ACCOUNT_NOT_LIVE','ACCOUNT_AUTH_MISMATCH') else 'AUTHENTICATION_SYSTEMIC_FAILURE'
            except Exception as exc:
                auth_status='RUNTIME_OR_PROVIDER_FAILURE_'+type(exc).__name__
            finally:
                if transport is not None:transport.close()
        counts=Counter();weeks=[Counter() for _ in range(4)]
        for event in selected:
            entry=quotes.get((event['symbol_id'],event['entry_reference_boundary']*1000));exit=quotes.get((event['symbol_id'],event['exit_reference_boundary']*1000))
            n=sum(bool(x and x['two_sided_quote_available']) for x in (entry,exit));category=('NO_MATCHED_BOUNDARY','PARTIAL_BOUNDARY','BOTH_BOUNDARIES')[n]
            counts[category]+=1;weeks[event['fixed_week']][category]+=1
            receipts.append({'event':event,'entry':entry,'exit':exit,'coverage_category':category,'cost_semantics':'SPREAD_STATE_ONLY_NOT_FEES_CONVERSION_OR_FILLS'})
        summary={'schema':'mxm.private.authentic.historical.quote.summary.v1','authentication_status':auth_status,'credential_presence':credentials,'cohort_selection':'FIRST_TWO_DISTINCT_SYMBOL_ORDINALS_WITH_SUPPORTED_EVENT_PER_ASSET_CLASS_AND_FIXED_WEEK;FIRST_EVENT;NO_GROSS_SELECTION','selected_events':len(selected),'selected_identities':len({x['symbol_id'] for x in selected}),'original_emitted':4205,'original_supported':3321,'unselected_supported_events':3321-len(selected),'historical_tick_requests':requests,'request_pacing_seconds':0.25,'coverage_counts':dict(counts),'four_week_counts':[dict(c) for c in weeks],'unique_boundaries':len(quotes),'quotes_with_two_sides':sum(x['two_sided_quote_available'] for x in quotes.values()),'window_seconds':60,'missing_outside_window_preserved':True,'provider_hasmMore_recorded':True,'actual_fills':0,'historical_fees_or_conversion_verified':False,'net_established':False,'protected_forward':False,'orders':0,'authenticated_provider_endpoint':'live.ctraderapi.com:5035','token_refresh_attempted':False}
        PHASE='DELIVERY';rt.output(head,auth,tmp,key,'quotes',{'summary':summary,'private_event_quote_receipts':receipts,'request_boundary_index':list(quotes.values())},summary)

if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
