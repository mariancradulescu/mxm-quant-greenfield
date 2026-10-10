"""Entry-only economic capacity. No directional fit, outcome or return selection."""
import math,itertools
from collections import Counter
from datetime import datetime,timezone
SIDS=(1,2,250);START=1787184000;END=1789603200
PRECISION_N=math.ceil(1.96**2*.25/.10**2)
def iso(t):return datetime.fromtimestamp(t,timezone.utc).strftime('%G-W%V')
def grid():return [START+d*86400+h*3600+900 for d in range(28) if datetime.fromtimestamp(START+d*86400,timezone.utc).weekday()<5 for h in (9,13)]
def stats(values):
    x=sorted(float(v) for v in values if v is not None)
    return {'n':len(x),'min':min(x) if x else None,'median':x[len(x)//2] if x else None,'max':max(x) if x else None,'mean':sum(x)/len(x) if x else None}
def point(q):
    if q is None:return None
    s=q['sides']
    if any(s.get(k,{}).get('state')!='AUTHENTIC_CAUSAL_QUOTE' or s[k].get('source_has_more',True) or s[k].get('age_ms',float('inf'))>5000 for k in ('bid','ask')):return None
    if abs(s['bid']['timestamp_ms']-s['ask']['timestamp_ms'])>2000:return None
    b,a=s['bid']['price'],s['ask']['price']
    return {'bid':b,'ask':a} if 0<b<=a else None
def pnl_convert(usd,fx):return usd/(fx['ask'] if usd>=0 else fx['bid'])
def commission_eur(full,assets,units,price,fx):
    keys=('preciseTradingCommissionRate','preciseMinCommission','commissionType','minCommissionType','lotSize')
    if any(k not in full for k in keys):return None
    rate=int(full['preciseTradingCommissionRate']);kind=int(full['commissionType']);lots=units*100/int(full['lotSize']) if int(full['lotSize'])>0 else None
    if rate==0:usd=0.
    elif kind==1:usd=rate/1e8*units*price/1e6
    elif kind in (2,4) and lots is not None:usd=rate/1e8*lots
    elif kind==3:usd=rate/1e5/100*units*price
    else:return None
    floor=int(full['preciseMinCommission'])/1e8
    if floor==0:floor_eur=0.
    elif int(full['minCommissionType'])==2:floor_eur=floor/fx['bid']
    elif int(full['minCommissionType'])==1:
        name=assets.get(str(full.get('minCommissionAsset')))
        if name=='EUR':floor_eur=floor
        elif name=='USD':floor_eur=floor/fx['bid']
        else:return None
    else:return None
    return max(usd/fx['bid'],floor_eur)
def accounting(direction,units,entry,exit_price,fx0,fx1,full,assets,slip_bps,funding_eur):
    """Explicit current-terms scenario. caller supplies prices; not real fills."""
    sign=1 if direction=='long' else -1;factor=slip_bps/10000
    p0=entry*(1+sign*factor);p1=exit_price*(1-sign*factor)
    pnl_usd=sign*units*(p1-p0);pnl_eur=pnl_convert(pnl_usd,fx1)
    c0=commission_eur(full,assets,units,p0,fx0);c1=commission_eur(full,assets,units,p1,fx1)
    if c0 is None or c1 is None or 'pnlConversionFeeRate' not in full:return None
    fraction=int(full['pnlConversionFeeRate'])/10000
    conversion_fee=abs(pnl_eur)*fraction
    return {'pnl_usd':pnl_usd,'quote_pnl_eur':pnl_eur,'entry_commission_eur':c0,'exit_commission_eur':c1,'pnl_conversion_fee_eur':conversion_fee,'funding_stress_eur':funding_eur,'scenario_net_eur':pnl_eur-c0-c1-conversion_fee-funding_eur,'slippage_bps_per_side':slip_bps,'historical_fill_or_charge_certified':False}
def hurdle(direction,u,q,fx,full,assets,slip,funding):
    """Hypothetical exit price, entry FX held fixed. No future price is accessed."""
    entry=q['ask'] if direction=='long' else q['bid'];base=q['bid'] if direction=='long' else q['ask'];sgn=1 if direction=='long' else -1
    flat=accounting(direction,u,entry,base,fx,fx,full,assets,slip,funding)
    if flat is None:return None
    lo=0.;hi=base*.9
    def value(move):return accounting(direction,u,entry,base+sgn*move,fx,fx,full,assets,slip,funding)['scenario_net_eur']
    if value(hi)<=0:return None
    for _ in range(64):
        mid=(lo+hi)/2
        if value(mid)>=0:hi=mid
        else:lo=mid
    return {'unchanged_quote_roundtrip_cost_eur':-flat['scenario_net_eur'],'breakeven_quote_price_move':hi,'breakeven_bps_from_current_exit_side':10000*hi/base,'entry_fx_held_constant':True,'slippage_bps_per_side':slip,'funding_stress_eur':funding,'entry_commission_eur':flat['entry_commission_eur'],'exit_commission_eur':flat['exit_commission_eur'],'conversion_fee_eur':flat['pnl_conversion_fee_eur']}
def entry_row(sid,t,bars,quotes,meta,native):
    r={'sid':sid,'entry':t,'iso_week':iso(t),'block':(t-START)//604800,'eligible':False,'reason':'UNRESOLVED'}
    prior=[bars[sid].get(t-600-i*300) for i in range(12)];q=point(quotes.get((sid,t)));fx=point(quotes.get((1,t)))
    if any(x is None for x in prior):return r|{'reason':'ENTRY_M5_GAP'}
    if q is None:return r|{'reason':'ENTRY_QUOTE_UNDER_FIXED_RULES'}
    if fx is None:return r|{'reason':'ENTRY_FX_UNDER_FIXED_RULES'}
    row=meta[sid];full=native['full'][str(sid)];u=int(row['min_volume_cents'])/100;step=int(row.get('step_volume_cents') or 0)/100
    if u<=0 or step<=0 or int(full.get('lotSize') or 0)<=0:return r|{'reason':'CURRENT_VOLUME_LATTICE_UNKNOWN'}
    if not all(float(x['tick_volume'])>0 for x in prior):return r|{'reason':'ENTRY_ZERO_ACTIVITY'}
    width=max(float(x['high']) for x in prior)-min(float(x['low']) for x in prior);range_eur=u*width/fx['bid'];margin=max(float(row['buy_margin_eur']),float(row['sell_margin_eur']))
    mid=(q['bid']+q['ask'])/2;h={}
    for side in ('long','short'):
        for slip in (0,1,2):
            for funding in (0,.10,.50,1.):h[f'{side}|{slip}|{funding}']=hurdle(side,u,q,fx,full,{str(a['assetId']):a['name'] for a in native['assets']},slip,funding)
    if any(x is None for x in h.values()):return r|{'reason':'CURRENT_COST_UNRESOLVED','hurdles':h}
    overhead=max(h[f'{side}|2|0.1']['unchanged_quote_roundtrip_cost_eur'] for side in ('long','short'))
    risk=range_eur+overhead
    largest_hurdle=max(h[f'{side}|2|0.1']['breakeven_quote_price_move'] for side in ('long','short'))
    # Range exceeds cost hurdle = opportunity scale proxy, never future return filter.
    reason='ELIGIBLE_CURRENT_TERMS_SCENARIO' if margin<=50 and risk<=2 and width>largest_hurdle else 'CURRENT_MARGIN_GT50' if margin>50 else 'ENTRY_RANGE_PLUS_STRESS_GT2' if risk>2 else 'PRE_ENTRY_RANGE_NOT_ABOVE_COST_HURDLE'
    r.update(eligible=reason=='ELIGIBLE_CURRENT_TERMS_SCENARIO',reason=reason,minimum_units=u,minimum_lots=u*100/int(full['lotSize']),volume_step_units=step,current_worst_margin_eur=margin,current_free_capital_eur=200-margin,entry_notional_eur=u*mid/fx['bid'],pre_entry_range_eur=range_eur,pre_entry_range_plus_stress_eur=risk,planned_loss_budget_eur=1.,hurdles=h,native_features={'lagged_h1_log_body':math.log(float(prior[0]['close'])/float(prior[-1]['open'])),'native_tick_volume_sum':sum(float(x['tick_volume']) for x in prior),'range':width},decisions=['LONG_AT_ASK','SHORT_AT_BID','ABSTAIN'],not_a_direction_signal=True,entry_only=True,actual_live_eligibility_certified=False)
    return r

def capacity(rows):
    cap=[]
    for t in grid():
        rr=[r for r in rows if r['entry']==t and r['eligible']];subsets=[ss for n in range(len(rr)+1) for ss in itertools.combinations(rr,n)]
        margin=max((len(ss) for ss in subsets if sum(x['current_worst_margin_eur'] for x in ss)<=50),default=0)
        bounded=max((len(ss) for ss in subsets if sum(x['current_worst_margin_eur'] for x in ss)<=50 and sum(x['planned_loss_budget_eur']+max(x['hurdles'][f'{s}|2|0.1']['unchanged_quote_roundtrip_cost_eur'] for s in ('long','short')) for x in ss)<=2),default=0)
        cap.append({'entry':t,'iso_week':iso(t),'entry_eligible_legs':len(rr),'maximum_legs_margin_reserve_only':margin,'maximum_legs_margin_and2eur_planned_loss_plus_cost':bounded,'no_subset_selected_for_trading':True})
    weeks={w:{'scheduled_distinct_times':sum(x['iso_week']==w for x in cap),'scenario_distinct_feasible_times':sum(x['iso_week']==w and x['maximum_legs_margin_and2eur_planned_loss_plus_cost']>0 for x in cap),'scenario_max_legs_upper_bound':sum(x['maximum_legs_margin_and2eur_planned_loss_plus_cost'] for x in cap if x['iso_week']==w),'margin_only_max_legs_upper_bound':sum(x['maximum_legs_margin_reserve_only'] for x in cap if x['iso_week']==w)} for w in sorted({x['iso_week'] for x in cap})}
    return cap,weeks

def run(old,cost,archive):
    from datetime import datetime
    stamp=lambda s:int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())
    bars={int(s):{stamp(r['time_utc']):r for r in rs} for s,rs in old['private_m5_rows'].items()};quotes={(q['symbol_id'],q['boundary_ms']//1000):q for q in old['private_quote_receipts']};meta={int(r['symbol_id']):r for r in cost['metadata_rows']};native=cost['current_native_evidence']['private_native_evidence']
    rows=[entry_row(s,t,bars,quotes,meta,native) for s in SIDS for t in grid()];cap,weekly=capacity(rows)
    per=[];evaluability=[]
    for sid in SIDS:
        rr=[x for x in rows if x['sid']==sid];n=sum(x['eligible'] for x in rr);parts=[]
        for label,select in [(f'block{b}',lambda x,b=b:x['block']==b) for b in range(4)]+[(w,lambda x,w=w:x['iso_week']==w) for w in ('2026-W35','2026-W36','2026-W37')]:
            p=[x for x in rr if select(x)];parts.append({'partition':label,'scheduled':len(p),'entry_scenario_eligible':sum(x['eligible'] for x in p),'reasons':dict(Counter(x['reason'] for x in p))})
        per.append({'sid':sid,'symbol':meta[sid]['broker_symbol'],'scheduled_entries':len(rr),'entry_scenario_eligible':n,'partitions':parts,'current_worst_margin_eur':max(float(meta[sid]['buy_margin_eur']),float(meta[sid]['sell_margin_eur'])),'minimum_volume_cents':int(meta[sid]['min_volume_cents']),'minimum_units':int(meta[sid]['min_volume_cents'])/100,'range_eur':stats(x.get('pre_entry_range_eur') for x in rr),'notional_eur':stats(x.get('entry_notional_eur') for x in rr),'cost_2bps_each_side_funding010':stats(max(x['hurdles'][f'{s}|2|0.1']['unchanged_quote_roundtrip_cost_eur'] for s in ('long','short')) for x in rr if x.get('hurdles') and all(v is not None for v in x['hurdles'].values())),'breakeven_bps_2bps_each_side_funding010':stats(max(x['hurdles'][f'{s}|2|0.1']['breakeven_bps_from_current_exit_side'] for s in ('long','short')) for x in rr if x.get('hurdles') and all(v is not None for v in x['hurdles'].values())),'precision_gate':{'planned_optimistic_iid_N_minimum':PRECISION_N,'available_max_N':40,'pass':n>=PRECISION_N,'actual_effective_N_not_estimated':True}})
        for horizon in (3600,14400):
            eligible=[r for r in rr if r['eligible']];missing=[]
            for x in eligible:
                q1=point(quotes.get((sid,x['entry']+horizon)));f1=point(quotes.get((1,x['entry']+horizon)))
                if q1 is None or f1 is None:missing.append({'entry':x['entry'],'instrument_exit_missing_under_fixed_rules':q1 is None,'fx_exit_missing_under_fixed_rules':f1 is None})
            evaluability.append({'sid':sid,'horizon':horizon,'entry_scenario_eligible':len(eligible),'exit_evaluable':len(eligible)-len(missing),'exit_censored':len(missing),'missing':missing,'exit_presence_changes_entry':False,'returns_computed':False})
    # A separate audit invariant: removing every non-entry observation leaves entry rows unchanged.
    entry_keys={(sid,t) for sid in SIDS for t in grid()};filtered={k:v for k,v in quotes.items() if k in entry_keys};again=[entry_row(s,t,bars,filtered,meta,native) for s in SIDS for t in grid()]
    if rows!=again:raise RuntimeError('FUTURE_QUOTE_INFLUENCES_ENTRY')
    return {'schema':'mxm.private.native.economic.frontier.v2','entry_universe':per,'portfolio_capacity':weekly,'retrospective_evaluability':evaluability,'extension':archive,'support_gate':'FAIL_40_MAX_VS97_OPTIMISTIC_MIN;NO_DIRECTIONAL_EXECUTION','decision':'NO_NEW_DIRECTIONAL_EXACT;CURRENT_GRID_HARD21_UNSUPPORTED;OLDER_M5_EXTENSION_AUTHENTIC_BUT_NO_MATCHING_LIVE_QUOTES','causal_exit_invariance':'PASS','directional_experiments':0,'directional_returns_computed':0,'quote_accounting_and_break_even_scenarios_computed':True,'financing':'UNKNOWN_ACTUAL;0/.10/.50/1EUR_STRESS_NOT_HISTORICAL_ZERO','conversion_fee':'ABSOLUTE_PNL_CURRENT_RATE_SCENARIO_NOT_HISTORICAL_BROKER_CHARGE','current_terms':'CURRENT_SNAPSHOT_CONSTANTS;NOT_KNOWN_HISTORICAL_CONTRACT','native_cloud_feasibility':'M5_OHLC_TICK_VOLUME_PRICE_AND_METADATA_ARITHMETIC;NO_RUNTIME_PROOF','private_entry_rows':rows,'private_capacity_rows':cap,'no_returns_or_winner_selection':True}
