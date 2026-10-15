"""Minimum native ticket frontier. No new predictor, outcome selection or broker IO."""
import math,statistics,bisect
from collections import Counter,defaultdict
from functools import lru_cache
HORIZONS=(900,3600,14400)
SLIPS=(0,1,2,5)
MODES=('STRICT5S','STATE300S')
WEEKS=('2026-W35','2026-W36','2026-W37')

def distribution(values):
    v=sorted(x for x in values if x is not None and math.isfinite(x))
    return {'n':len(v),'min':v[0] if v else None,'p25':v[int((len(v)-1)*.25)] if v else None,'median':statistics.median(v) if v else None,'p75':v[int((len(v)-1)*.75)] if v else None,'p95':v[int((len(v)-1)*.95)] if v else None,'max':v[-1] if v else None}

def clocks(db,sid):
    v=set()
    for lo,hi,z in db.execute("SELECT a,b,z FROM span WHERE s=? AND k IN ('bid','ask')",(sid,)):
        if ar.category(z)!='CONFIRMED_COMPLETE':continue
        lo=max(ar.START,(lo+999)//1000);hi=min(ar.END-1,hi//1000)
        v.update(range(((lo+299)//300)*300,hi+1,300))
    return sorted(v)

def core_entry(row,f,t,mode,qp,g):
    strict=mode=='STRICT5S';q=qp(row['sid'],t,strict)
    if not q.get('valid'):return {'state':'ENTRY_BID_ASK_NA'}
    paths,ids=original.needed_routes(row,f,g)
    if any(p is None for p in paths):return {'state':'FX_ROUTE_NA'}
    qs=quote_map({row['sid']}|ids,(t,),strict,qp)
    u=int(f['minVolume'])/100
    if int(round(row['min_units']*100))!=int(f['minVolume']) or int(f['stepVolume'])<=0 or int(f['maxVolume'])<int(f['minVolume']):return {'state':'NATIVE_VOLUME_LATTICE_NA'}
    notional=fx.convert(-u*q['mid'],row['quote'],'EUR',t,qs,g)
    spread=fx.convert(-u*(q['ask']-q['bid']),row['quote'],'EUR',t,qs,g)
    fees=[fx.commission(row,f,u,q[p],t,qs,g) for p in ('bid','ask')]
    if notional is None or spread is None or any(x is None for x in fees):return {'state':'ENTRY_FX_OR_PRECISE_FEE_NA'}
    notional=-notional
    if not notional>0:return {'state':'ENTRY_NOTIONAL_NA'}
    rate=int(f['pnlConversionFeeRate'])/10000 if row['quote']!='EUR' else 0
    if not 0<=rate<1:return {'state':'PNL_FEE_SCHEMA_NA'}
    return {'state':'CURRENT_TERMS_ENTRY_COST_REFERENCE','minimum_units':u,'step_units':int(f['stepVolume'])/100,'notional_eur':notional,'spread_eur':-spread,'commission_roundtrip_eur_reference':sum(fees),'pnl_fee_rate':rate,'margin_eur_current':row['margin_eur'],'quote_age_ms':q['age_ms'],'side_skew_ms':q['side_skew_ms'],'ids':sorted({row['sid']}|ids)}

def quote_map(ids,times,strict,qp):
    result={}
    for sid in ids:
        for t in times:
            z=qp(sid,t,strict)
            if z.get('valid'):result[sid,t]={'symbol_id':sid,'boundary_ms':t*1000,'state_expiry_ms':5000 if strict else 300000,'sides':{k:{'state':'AUTHENTIC_CAUSAL_QUOTE_RECONSTRUCTED_STATE','price':z[k],'timestamp_ms':z[k+'_time_ms'],'age_ms':t*1000-z[k+'_time_ms']} for k in ('bid','ask')}}
    return result

def continuous_exit_support(db,ev,qp):
    t=ev['t'];exit=t+ev['h'];strict=ev['mode']=='STRICT5S'
    # Only read quote availability/cost support; no signed future return or predictor.
    qs=quote_map(ev['ids'],(exit,),strict,qp)
    endpoint=all(fx.point(qs.get((sid,exit))) is not None for sid in ev['ids'])
    full_path=endpoint and all(not ar.missing(db,sid,k,t*1000,exit*1000) for sid in ev['ids'] for k in ('bid','ask'))
    return endpoint,full_path

def capacity_plan(events,h,slip,mode,causal_censor=False):
    """Fixed-equity reference capacity. Simultaneous tickets; no profit or direction."""
    active=[];accepted=[];halt=None;peak_risk=peak_margin=0.;groups=defaultdict(list)
    for e in events:
        if e['h']==h and e['mode']==mode and e['scenarios'][str(slip)]['feasible']:groups[e['t']].append(e)
    for t,cohort in sorted(groups.items()):
        matured=sorted([e for e in active if e['t']+h<=t],key=lambda e:(e['t']+h,e['sid']))
        if causal_censor and any(not e['endpoint_cost_support'] for e in matured):halt='FIRST_SCHEDULED_SELECTED_EXIT_SUPPORT_NA_NO_REPLACEMENT';break
        active=[e for e in active if e['t']+h>t]
        for e in sorted(cohort,key=lambda e:(e['scenarios'][str(slip)]['cost_eur'],e['sid'])):
            a=e['scenarios'][str(slip)];risk=sum(x['scenarios'][str(slip)]['risk_eur'] for x in active)+a['risk_eur'];margin=sum(x['margin_eur_current'] for x in active)+e['margin_eur_current']
            if risk>2 or margin>80 or 200-margin<120:continue
            active.append(e);accepted.append(e);peak_risk=max(peak_risk,risk);peak_margin=max(peak_margin,margin)
    if causal_censor and not halt and any(not e['endpoint_cost_support'] for e in active):halt='FINAL_SELECTED_EXIT_SUPPORT_NA_NO_REPLACEMENT'
    return {'admitted_ticket_opportunities':len(accepted),'by_ISO_week':dict(Counter(e['iso'] for e in accepted)),'peak_reference_risk_eur':peak_risk,'peak_reference_margin_eur':peak_margin,'maximum_simultaneous':max_concurrent(accepted,h),'halt':halt,'fixed_equity_reference_eur':200,'HARD21':False,'actual_entries':0,'semantics':'SIMULTANEOUS_MINIMUM_TICKET_COST_RISK_CAPACITY_NOT_STRATEGY_NOT_EXECUTABLE_CERTIFICATION;NO_PNL_CASH_RESET_OR_PROFIT_RANK;UNKNOWN_INTRATRADE_EQUITY_AND_STOP_GAP_LOSS','hypothetical_week_counts_not_HARD21':True,'schedule_classification':'GREEDY_FEASIBLE_REFERENCE_SCHEDULE','optimal_upper_bound':None}

def max_concurrent(events,h):
    changes=sorted([(e['t'],1) for e in events]+[(e['t']+h,-1) for e in events]);n=peak=0
    for t,d in changes:n+=d;peak=max(peak,n)
    return peak

def evaluate(db,st):
    global fx,original,ar,support
    from research_core_v4.full_native_frontier_20261014_v1 import accounting_v1 as fx,runner_v1 as original
    from research_core_v4.critical_frontier_repair_20261014_v2 import archive_v2 as ar,runner_v2 as support
    rows={int(s):r for s,r in st['rows'].items()};g=fx.graph(list(rows.values()));qp=lru_cache(maxsize=400000)(lambda sid,t,strict=False:support.covered_qpoint(db,sid,t,strict))
    counts=Counter();events=[];manifest=[];barrier=defaultdict(Counter);byclass=defaultdict(list)
    statuses={x['sid']:x for x in st['original_statuses']};eligible=set(st['eligible']);all_clocks=len(range(ar.START,ar.END,300))
    for ix,(sid,row) in enumerate(sorted(rows.items())):
        rec={'sid':sid,'symbol':row['symbol'],'class':row['class'],'accepted_structural_eligible':sid in eligible,'original_structural_reasons':statuses[sid]['structural_reasons'],'counts':{}}
        if sid not in eligible:
            rec['state']='ACCEPTED_STRUCTURAL_EXCLUSION_OR_METADATA_NA';manifest.append(rec);continue
        f=st['catalog']['full'].get(str(sid));local=Counter({'calendar_clocks':all_clocks});candidate=clocks(db,sid);local['entry_interval_clocks']=len(candidate);local['unsampled_or_unconfirmed_entry']=all_clocks-len(candidate);bars=original.bars_for(db,sid)
        for t in candidate:
            tt=list(range(t-3900,t-300,300))
            if any(b not in bars for b in tt):local['prior_closed_M5_gap']+=1;continue
            if ar.missing(db,sid,'M5',(t-3900)*1000,(t-300)*1000-1):local['prior_closed_M5_interval_unconfirmed']+=1;continue
            local['causal_risk_feature_support']+=1
            ranges=[10000*(bars[b][1]-bars[b][2])/bars[b][3] for b in tt];tail=max(ranges);mean=statistics.mean(ranges);gap=max([5.]+[abs(10000*math.log(bars[b][0]/bars[a][3])) for a,b in zip(tt,tt[1:])])
            for mode in MODES:
                en=core_entry(row,f,t,mode,qp,g) if f else {'state':'CONTRACT_NA'}
                local[mode+'_'+en['state']]+=1
                if en['state']!='CURRENT_TERMS_ENTRY_COST_REFERENCE':continue
                for h in HORIZONS:
                    if t+h>=ar.END:local['end_of_domain_censor']+=1;continue
                    ev={**en,'sid':sid,'symbol':row['symbol'],'class':row['class'],'t':t,'iso':original.k.iso(t),'h':h,'mode':mode,'prior_tail_bps':tail,'prior_mean_range_bps':mean,'prior_gap_stress_bps':gap,'scenarios':{}}
                    horizon_scale=math.sqrt(h/300);fund=.10*h/86400
                    for slip in SLIPS:
                        cost=(en['spread_eur']+en['commission_roundtrip_eur_reference']+fund)/(1-en['pnl_fee_rate'])+en['notional_eur']*2*slip/10000
                        stress=max(tail*horizon_scale,gap);risk=cost+en['notional_eur']*stress/10000;scale=en['notional_eur']*mean*horizon_scale/10000
                        failures=[]
                        if risk>2:failures.append('RISK')
                        if en['margin_eur_current']>80:failures.append('MARGIN')
                        if cost>scale:failures.append('COST_VS_PRIOR_RANGE')
                        ev['scenarios'][str(slip)]={'cost_eur':cost,'break_even_bps':cost/en['notional_eur']*10000,'funding_stress_eur':fund,'risk_eur':risk,'prior_scale_eur':scale,'feasible':not failures,'barriers':failures}
                        barrier[(mode,h,slip)].update(failures or ['EXANTE_FEASIBLE'])
                    ev['endpoint_cost_support'],ev['continuous_bilateral_path_support']=continuous_exit_support(db,ev,qp)
                    # Optimistic quoted-width capture ceiling only. Unknown fills, latency
                    # and passive execution costs are NOT silently zero in actual NET.
                    ev['passive_quoted_width_minus_current_fee_and_funding_ceiling_eur']=en['spread_eur']-en['commission_roundtrip_eur_reference']-fund
                    ev['two_pending_leg_capital_reference_pass']=2*ev['scenarios']['2']['risk_eur']<=2 and 2*en['margin_eur_current']<=80
                    events.append(ev);byclass[row['class']].append(ev)
        rec['counts']=dict(local);rec['state']='ENTRY_ECONOMIC_FIELDS_OBSERVED' if any(local[m+'_CURRENT_TERMS_ENTRY_COST_REFERENCE'] for m in MODES) else 'ENTRY_OR_PRIOR_SUPPORT_NA';manifest.append(rec);counts.update(local)
        if ix%256==0:print(__import__('json').dumps({'phase':'COST_RISK_FREQUENCY_FRONTIER','catalog_classified':ix+1,'priced_references':len(events),'broker_requests':0}),flush=True)
    summaries={}
    for mode in MODES:
        for h in HORIZONS:
            cohort=[e for e in events if e['mode']==mode and e['h']==h]
            for slip in SLIPS:
                admitted=[e for e in cohort if e['scenarios'][str(slip)]['feasible']];key=f'{mode}_H{h}_S{slip}'
                summaries[key]={'cohort':len(cohort),'entry_risk_cost_feasible':len(admitted),'paired_endpoint_support':sum(e['endpoint_cost_support'] for e in admitted),'continuous_bilateral_path_support':sum(e['continuous_bilateral_path_support'] for e in admitted),'barriers':dict(barrier[(mode,h,slip)]),'cost_eur':distribution([e['scenarios'][str(slip)]['cost_eur'] for e in cohort]),'break_even_bps':distribution([e['scenarios'][str(slip)]['break_even_bps'] for e in cohort]),'risk_eur':distribution([e['scenarios'][str(slip)]['risk_eur'] for e in cohort]),'margin_eur':distribution([e['margin_eur_current'] for e in cohort]),'weekly':{w:{'entry_feasible':sum(e['iso']==w for e in admitted),'endpoint_supported':sum(e['iso']==w and e['endpoint_cost_support'] for e in admitted),'path_supported':sum(e['iso']==w and e['continuous_bilateral_path_support'] for e in admitted)} for w in WEEKS},'greedy_feasible_reference_schedule':capacity_plan(events,h,slip,mode),'chronological_censor_guard_capacity':capacity_plan(events,h,slip,mode,True)}
    selected=[e for e in events if e['mode']=='STRICT5S' and e['h']==900 and e['scenarios']['2']['feasible']]
    class_summary={c:{'entry_feasible':len(v),'cost_eur':distribution([e['scenarios']['2']['cost_eur'] for e in v]),'risk_eur':distribution([e['scenarios']['2']['risk_eur'] for e in v]),'minimum_ticket_units':distribution([e['minimum_units'] for e in v])} for c,v in group(selected,'class').items()}
    passive=[e for e in selected if e['two_pending_leg_capital_reference_pass']]
    candidate_economics={'passive_quote_reference_contexts':len(passive),'quoted_width_ceiling_positive':sum(e['passive_quoted_width_minus_current_fee_and_funding_ceiling_eur']>0 for e in passive),'ceiling_eur':distribution([e['passive_quoted_width_minus_current_fee_and_funding_ceiling_eur'] for e in passive]),'native_passive_fill_and_receipt_history_in_bound_schema':0,'ceiling_not_expected_profit':True,'historical_session_closure_authority':st.get('historical_session_closure_authority','UNAVAILABLE'),'accepted_development_L2_rows_in_snapshot':0}
    return {'counts':dict(counts),'catalog':len(rows),'eligible':len(eligible),'structural_manifest':manifest,'cases':summaries,'class_primary':class_summary,'candidate_economics':candidate_economics,'events':events,'actual_orders':0,'HARD21':False,'historical_cost_terms':'N_A;CURRENT_PRECISE_BROKER_TERMS_PLUS_SEPARATE_SCENARIOS;QUOTE_REFERENCES_NOT_FILLS','risk_semantics':'CAUSAL_PRIOR12_M5_MAX_RANGE_SQRT_HORIZON_AND_OBSERVED_GAP_STRESS_PLUS_COST;NOT_GUARANTEED_LOSS_BOUND','native_vs_proxy':'STRICT5S_AND2S_SKEW_SEPARATE_FROM300S_CARRIED_QUOTE_REFERENCE;NEITHER_IS_FILL_CERTIFICATION','full_ticket_cost_semantics':'ENTRY_ROUNDTRIP_REFERENCE_USING_BOTH_CURRENT_FEES_SPREAD_SIGNED_FX_PNL_FEE_ENVELOPE_SLIPPAGE_AND_FUNDING_STRESS;FUTURE_ACTUAL_TERMS_NA'}

def group(items,key):
    result=defaultdict(list)
    for item in items:result[item[key]].append(item)
    return result
