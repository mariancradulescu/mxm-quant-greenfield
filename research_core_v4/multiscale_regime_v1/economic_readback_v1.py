"""Read existing new results only. No model replay. Native identity and portfolio audit."""
import json,os,tempfile,pathlib,math
from collections import Counter,defaultdict
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.owner_recovery_v1.readback_v1 import describe,iso
from research_core_v4.multiscale_regime_v1.kernel_v1 import NAMES,merge,n
from research_core_v4.multiscale_regime_v1.cost_universe_v1 import eligibility,aggregate
e=rt.e;P='research_core_v4/multiscale_regime_v1/';PHASE='GATE'
CLASS_PRODUCTS={'Commodities (Cash)':'CASH_COMMODITY_CFD','Currency Index (Spot)':'CURRENCY_INDEX_CFD','Forwards - Commodities':'FORWARD_OR_FUTURES_STYLE_CFD','Forwards - Indices':'FORWARD_OR_FUTURES_STYLE_CFD','Forwards - Treasuries':'FORWARD_OR_FUTURES_STYLE_CFD'}
def gate():
    head=os.environ['GITHUB_SHA'];e.w.v2.runtime(head);a=json.loads((e.a.ROOT/(P+'ECONOMIC_READBACK_EXECUTION_V1.json')).read_text())
    e.w.old.need(a['orders'] is False and a['protected_forward'] is False and a['scientific_replay'] is False,'ECONOMIC_SCOPE')
    e.w.old.need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-new-economic-readback-v1.yml@refs/heads/'+e.w.old.BRANCH,'ECONOMIC_WORKFLOW')
    e.a.ancestor(a['base_head'],head)
    for p,h in a['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'ECONOMIC_SOURCE')
    original=json.loads((e.a.ROOT/(e.P+'EXACT_COVERAGE_PREARM_V1.json')).read_text())
    for p,h in original['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'ORIGINAL_SOURCE')
    e.w.old.need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'ECONOMIC_EXPIRED')
    claim='mxm-new-economic-'+a['invocation_id'];e.w.old.need(not e.w.v2.existing_ref(claim),'ECONOMIC_CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+claim,'sha':head})
    return head,a
def correlation(xs,ys):
    if len(xs)<2:return None
    ax=sum(xs)/len(xs);ay=sum(ys)/len(ys);vx=sum((x-ax)**2 for x in xs);vy=sum((y-ay)**2 for y in ys)
    return sum((x-ax)*(y-ay) for x,y in zip(xs,ys))/math.sqrt(vx*vy) if vx*vy>0 else None
def pair_audit(results,ids,metadata):
    pairs={};maps=[]
    for name in NAMES:
        maps.append({(r['symbol_id'],tr['action']):tr for r in results[name] if r['symbol_id'] in ids for tr in r['trials']})
    common=sorted(set(maps[0])&set(maps[1]));gross=[[],[]];agree=0;labels=0
    for k in common:
        a,b=(m[k] for m in maps);d1=(a['model']>0)-(a['model']<0);d2=(b['model']>0)-(b['model']<0);agree+=int(d1==d2)
        if a['y'] is not None and b['y'] is not None:
            e.w.old.need(a['y']==b['y'],'PAIRED_RESPONSE_DRIFT');labels+=1;gross[0].append(d1*a['y']);gross[1].append(d2*b['y'])
    byclock=defaultdict(list);weeks=defaultdict(Counter)
    for k in sorted(set(maps[0])|set(maps[1])):
        sid,t=k;members=[m[k] for m in maps if k in m];directions={(tr['model']>0)-(tr['model']<0) for tr in members};r=metadata[sid]
        margin=max(float(r['buy_margin_eur'] if d>0 else r['sell_margin_eur']) for d in directions if d) if directions!={0} else 0
        byclock[t].append({'margin':margin,'sid':sid,'directions':directions,'class':r['asset_class']});weeks[iso(t)]['distinct_symbol_clock_predictions']+=1;weeks[iso(t)]['mechanism_conflicts']+=int(len(directions-{0})>1)
    clocks=[]
    for t,v in sorted(byclock.items()):
        ordered=sorted(x['margin'] for x in v if x['margin']>0);used=0;bound=0
        for mar in ordered:
            if used+mar<=150:used+=mar;bound+=1
            else:break
        weeks[iso(t)]['optimistic_margin_only_capacity_upper_bound']+=bound
        clocks.append({'action':t,'distinct_symbol_candidates':len(v),'margin_sum_eur':sum(x['margin'] for x in v),'optimistic_margin_only_capacity':bound,'same_class_max':max(Counter(x['class'] for x in v).values())})
    return {'overlap_symbol_clocks':len(common),'supported_overlap':labels,'same_direction_count':agree,'same_direction_fraction':agree/len(common) if common else None,'paired_gross_reference_correlation':correlation(*gross),'union_symbol_clocks':len(set(maps[0])|set(maps[1])),'simultaneous_union_minimum_margin_eur':describe([c['margin_sum_eur'] for c in clocks]),'clocks_exceed150eur':sum(c['margin_sum_eur']>150 for c in clocks),'ISO_UTC':[{ 'iso_week':w,**v,'full_iso_week':w in ('2026-W35','2026-W36','2026-W37'),'certified_positive_expectancy_entries':0,'actual_entries':0} for w,v in sorted(weeks.items())],'capacity_semantics':'OPTIMISTIC_UPPER_BOUND_ONLY;SORTED_MARGINS_COMPUTE_BOUND_NOT_TRADING_SELECTION;50EUR_BUFFER;NO_FEES_RISK_CORRELATED_LOSS_OR_FILLS','different_mechanism_same_symbol':'ONE_SYMBOL_CLOCK_UNION_NO_DOUBLE_COUNTING;CONFLICTS_PRESERVED_NOT_RESOLVED','private_clock_capital_diagnostics':clocks}
def promising(results,ids,metadata):
    selected=[];diagnostics={}
    for name,rr in results.items():
        rr=[r for r in rr if r['symbol_id'] in ids];classes=sorted({metadata[r['symbol_id']]['asset_class'] for r in rr})
        for c in classes+['ALL_STRUCTURALLY_ELIGIBLE']:
            sub=rr if c=='ALL_STRUCTURALLY_ELIGIBLE' else [r for r in rr if metadata[r['symbol_id']]['asset_class']==c];w=merge(sub);iw=merge(sub,'iso_utc')
            good=len(sub)>=20 and sum(b['supported'] for b in w)>=100 and all(b['model_gross_bps'] is not None and b['model_gross_bps']>0 for b in w) and sum(b['MSE_improvement_bps2'] is not None and b['MSE_improvement_bps2']>0 for b in w)>=3 and sum(b['baseline_squared_error_sum']-b['model_squared_error_sum'] for b in w)>0 and all(b['model_gross_bps'] is not None and b['model_gross_bps']>0 for b in iw if b['iso_week'] in ('2026-W35','2026-W36','2026-W37'))
            diagnostics[name+'|'+c]={'identities':len(sub),'four_blocks':w,'ISO_UTC':iw,'economic_pilot_gate':bool(good)}
            if good:selected.append((name,c,sub))
    # Fixed ordinal/time sample within qualifying whole classes; no y-based event selection.
    wanted=[]
    for name,c,rr in sorted(selected,key=lambda z:(z[0],z[1])):
        for block in range(4):
            trials=sorted([(r['symbol_id'],tr) for r in rr for tr in r['trials'] if tr['clock']//168==block and tr['model']!=0],key=lambda z:(z[0],z[1]['action']))
            for sid,tr in trials[:2]:wanted.append({'mechanism':name,'class':c,'sid':sid,**tr})
    return wanted[:128],diagnostics
def pilot(wanted,key,fp,tmp,head,a):
    if not wanted:return {'status':'NO_PROSPECTIVE_COHORT_PASSED_COST_PILOT_GATE','requests':0,'events':0},[]
    from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import authenticate_segment,RateLimiter,StdlibCTraderTransport,m,enums,decode_ctrader_tick_page
    from m6.ctrader_capture import require_read_only_request
    old=json.loads((e.a.ROOT/'research_core_v4/synchronized_breadth_v1/EXECUTION_V1.json').read_text());full,_=load_asset(key,fp,tmp,old['fullcost_source']);qm={(q['symbol_id'],q['boundary_ms']):q for q in full['private_boundary_receipts']};digits=e.w.old.verify_science()[2]
    requests=0;transport=StdlibCTraderTransport();quotes=[];status='AUTHENTIC_CURRENT_VIEW_HISTORICAL_PILOT';reason=None
    try:
        transport.connect();account=authenticate_segment(transport,*[os.environ[k] for k in ('CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')]);limiter=RateLimiter(min_interval=.25)
        for sid,t in sorted({(tr['sid'],tr[k]*1000) for tr in wanted for k in ('action','exit')}):
            if (sid,t) in qm:continue
            e.w.old.need(n.START*1000<=t<=n.END*1000,'PILOT_DOMAIN');sides={};pages=[]
            for name,kind in [('bid',enums.BID),('ask',enums.ASK)]:
                e.w.old.need(requests<512,'PILOT_BUDGET');limiter.before_send();req=m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=sid,type=kind,fromTimestamp=t-60000,toTimestamp=t);require_read_only_request(type(req).__name__);r=transport.request(req,timeout=20);requests+=1
                if isinstance(r,m.ProtoOAErrorRes):sides[name]={'state':'PROVIDER_ERROR','code':r.errorCode};continue
                e.w.old.need(isinstance(r,m.ProtoOAGetTickDataRes),'PILOT_RESPONSE');enc=[{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in r.tickData];page=decode_ctrader_tick_page(enc);e.w.old.need(all(t-60000<=x.timestamp_ms<=t for x in page),'PILOT_QUOTE_DOMAIN');pages.append({'side':name,'hasMore':bool(r.hasMore),'encoded_tick_rows':enc})
                if not page:sides[name]={'state':'NONE_IN60S'}
                else:
                    last=page[-1];sides[name]={'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':last.timestamp_ms,'age_ms':t-last.timestamp_ms,'price':round(last.raw_tick/100000,digits[sid]),'source_has_more':bool(r.hasMore)}
            valid=all(sides[s].get('state')=='AUTHENTIC_CAUSAL_QUOTE' for s in ('bid','ask')) and 0<sides['bid'].get('price',0)<=sides['ask'].get('price',0)
            q={'symbol_id':sid,'boundary_ms':t,'sides':sides,'two_sided_quote_available':valid,'raw_pages':pages};qm[sid,t]=q;quotes.append(q)
    except Exception as exc:status='PILOT_ACCESS_OR_TRANSPORT_BLOCKED';reason=type(exc).__name__
    finally:transport.close()
    coverage=Counter();marks=defaultdict(list);private=[]
    for tr in wanted:
        qq=[qm.get((tr['sid'],tr[k]*1000)) for k in ('action','exit')];matches=[q is not None and q['two_sided_quote_available'] for q in qq];cat='BOTH' if all(matches) else 'PARTIAL' if any(matches) else 'NONE';coverage[cat]+=1
        if tr['y'] is None:coverage['LABEL_GAP']+=1
        if not all(matches):continue
        a0=qq[0]['sides']['ask']['price'];b0=qq[0]['sides']['bid']['price'];a1=qq[1]['sides']['ask']['price'];b1=qq[1]['sides']['bid']['price'];side=(tr['model']>0)-(tr['model']<0);age=max(s['age_ms'] for q in qq for s in q['sides'].values());quote=10000*math.log(b1/a0) if side>0 else 10000*math.log(b0/a1);mid=side*10000*math.log((b1+a1)/(b0+a0))
        v={'midpoint_bps':mid,'quote_side_bps':quote,'spread_drag_bps':mid-quote,'max_age_ms':age,'has_more':any(s.get('source_has_more',False) for q in qq for s in q['sides'].values())};marks[tr['mechanism']+'|'+tr['class']+'|'+str(tr['clock']//168)].append(v);private.append({'event':tr,'quote_markout':v})
    return {'status':status,'blocker_class':reason,'events':len(wanted),'requests':requests,'coverage':dict(coverage),'by_mechanism_class_block':{k:{f:describe([v[f] for v in vals]) for f in ('midpoint_bps','quote_side_bps','spread_drag_bps','max_age_ms')} for k,vals in marks.items()},'provider_has_more_events':sum(v['has_more'] for vals in marks.values() for v in vals),'executed_fills':0,'net_expectancy':None,'selection_exposure':'DEVELOPMENT_WHOLE_CLASS_GATE_AND_FIXED_FIRST_TWO_SYMBOL_CLOCKS_PER_BLOCK;NOT_REPRESENTATIVE_UNIVERSE_SAMPLE_OR_CONFIRMATION'},quotes+private
def main():
    global PHASE
    os.umask(0o077);head,a=gate();master,*_=e.w.old.verify_science()
    with tempfile.TemporaryDirectory(prefix='mxm-economic-readback-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);e.w.old.need(fp==e.w.old.FP,'ECONOMIC_KEY')
        PHASE='AUTHENTIC_EXISTING_READBACK';cost,cp=load_asset(key,fp,tmp,a['cost_source']);science,sp=load_asset(key,fp,tmp,a['science_source']);att,_=load_asset(key,fp,tmp,a['science_attestation'])
        e.w.old.need(att['primary']['canonical_sha256']==e.a.sha(e.a.enc(science)) and att['primary']['ciphertext_sha256']==sp['ciphertext_sha256'],'SCIENCE_ATTESTATION')
        metadata={int(r['symbol_id']):dict(r) for r in cost['metadata_rows']};mismatches=[];changed=[]
        for r in metadata.values():
            old=r['product_type'];r['product_type']=CLASS_PRODUCTS.get(r['asset_class'],old)
            if old!=r['product_type']:changed.append(r['symbol_id'])
        ids=set();rows=[]
        for m in master:
            r=metadata.get(m['symbol_id']);valid=r is not None and r['broker_symbol']==m['symbol'] and r['asset_class']==m['asset_class']
            if not valid:mismatches.append(m['symbol_id'])
            if valid and eligibility(r)[0]:ids.add(m['symbol_id'])
        results=science['all_identity_trials_and_denominators'];fields=science['trial_fields']
        for rr in results.values():
            for r in rr:r['trials']=[dict(zip(fields,tr)) for tr in r['trials']]
        PHASE='PORTFOLIO_ECONOMIC_AUDIT';pair=pair_audit(results,ids,metadata);clocks=pair.pop('private_clock_capital_diagnostics');wanted,diag=promising(results,ids,metadata)
        PHASE='CONDITIONAL_NEW_QUOTE_PILOT';quotes,pilotprivate=pilot(wanted,key,fp,tmp,head,a)
        summary={'schema':'mxm.private.multiscale.regime.economic.readback.v1','source_provenance':{'cost':cp,'science':sp},'scientific_models_replayed':False,'native_identity_matches':1576-len(mismatches),'native_identity_mismatches':len(mismatches),'normalized_known_legitimate_class_mapping_changes':len(changed),'mapping_is_return_selected':False,'prospective_identity_matched_margin_eligible':len(ids),'full_current_universe_economic_classes':aggregate(list(metadata.values()),master),'paired_mechanism_portfolio':pair,'identity_matched_economic_cohort_diagnostics':diag,'new_bounded_quote_pilot':quotes,'historical_point_in_time_terms':False,'certified_positive_net':False,'HARD21_certified':False,'executed_fills':0,'protected_forward':False,'orders':0,'science_initial_output_preserved':True,'readback_is_independent_empirical_replication':False}
        PHASE='ENCRYPTED_AGGREGATE_DELIVERY';rt.output(head,a,tmp,key,'economicreadback',{'summary':summary,'private_identity_mismatches':mismatches,'private_class_mapping_changes':changed,'private_capital_clocks':clocks,'private_conditional_quote_pilot':pilotprivate},summary)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
