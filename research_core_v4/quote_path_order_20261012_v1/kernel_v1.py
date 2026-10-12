"""Preoutcome price/spread order kernel. No authentication, I/O or orders.

Consumes decoded native price/time sides, never execution-flow proxies.
The caller must authenticate encrypted source provenance before calling.
"""
import bisect
import math
from collections import Counter
from datetime import datetime,timezone

def sign(value):
    return (value > 0) - (value < 0)

def side_history(rows, lower_ms, upper_ms):
    seen = {}
    for stamp, price in rows:
        if lower_ms <= stamp <= upper_ms:
            if not math.isfinite(price) or price <= 0:
                return None, 'INVALID_CAUSAL_PRICE'
            if stamp in seen and seen[stamp] != price:
                return None, 'AMBIGUOUS_SIDE_MILLISECOND'
            seen[stamp] = price
    return sorted(seen.items()), None

def feature(bid_rows, ask_rows, entry_second, has_more=False):
    # Entry reference is t; features end at t-1, with no future selection.
    if has_more:
        return {'state': 'INCOMPLETE_PAGE'}
    lower, upper = (entry_second-60)*1000, (entry_second-1)*1000
    bids, reason = side_history(bid_rows, lower, upper)
    if reason:
        return {'state': reason}
    asks, reason = side_history(ask_rows, lower, upper)
    if reason:
        return {'state': reason}
    if not bids or not asks:
        return {'state': 'MISSING_CAUSAL_SIDE'}
    times_b, times_a = [z[0] for z in bids], [z[0] for z in asks]
    path = []
    for sec in range(entry_second-45, entry_second):
        now = sec*1000
        ib, ia = bisect.bisect_right(times_b, now)-1, bisect.bisect_right(times_a, now)-1
        if ib < 0 or ia < 0:
            return {'state': 'MISSING_PATH_STATE'}
        tb, b = bids[ib]; ta, a = asks[ia]
        if now-tb > 5000 or now-ta > 5000 or abs(tb-ta) > 2000:
            return {'state': 'STALE_OR_SKEWED_PATH'}
        if b > a:
            return {'state': 'CROSSED_PATH'}
        path.append(((b+a)/2, 10000*math.log(a/b)))
    x = [10000*math.log(mid/path[0][0]) for mid, _ in path]
    y = [spread-path[0][1] for _, spread in path]
    area = sum(x[i-1]*(y[i]-y[i-1])-y[i-1]*(x[i]-x[i-1]) for i in range(1,len(path)))
    vx = sum((x[i]-x[i-1])**2 for i in range(1,len(x)))
    vy = sum((y[i]-y[i-1])**2 for i in range(1,len(y)))
    tolerance = 64*math.ulp(max(1.,max(map(abs,x)),max(map(abs,y))))
    if vx <= tolerance**2 or vy <= tolerance**2:
        return {'state': 'DEGENERATE_PATH', 'area_bps2': area, 'model_side': 0}
    terms = [x[i-1]*(y[i]-y[i-1])-y[i-1]*(x[i]-x[i-1]) for i in range(1,len(path))]
    if abs(area) <= 64*math.ulp(max(1.,sum(map(abs,terms)))):
        area=0.
    return {'state': 'SUPPORTED_FEATURE', 'area_bps2': area,
            'normalized_area': area/math.sqrt(vx*vy), 'model_side': -sign(area),
            'midpoint_baseline_side': sign(x[-1]),
            'quote_count_baseline_side': sign(len(bids)-len(asks)),
            'snapshots': len(path), 'last_feature_ms': upper,
            'terminal_return_bps': x[-1], 'terminal_spread_change_bps': y[-1]}

def admit(entry, cash=200., open_margin=0., open_risk=0.):
    if not entry.get('eligible') or not all(math.isfinite(entry.get(k,float('nan'))) for k in ('margin_eur','risk_eur','cost_eur')):
        return False
    margin, risk = entry['margin_eur'], entry['risk_eur']
    if min(margin,risk,entry['cost_eur']) < 0:
        return False
    return (open_margin+margin <= min(80., .4*cash)
            and cash-open_margin-margin >= max(120., .6*cash)
            and open_risk+risk <= min(2., .01*cash))

def portfolio(candidates, account):
    """account(event, side) is called only at exit; it may return None.

    One position; same cohort shadow comparators. No outcome-based replacement.
    Risk is a planning proxy, not a guaranteed stop loss.
    """
    cash=200.; peak=cash; drawdown=0.; opened=None; selected=[]; closed=[]
    comparator_totals={'midpoint':0., 'quote_count':0., 'cash':0.}
    comparator_missing=Counter(); halt=None
    def settle(event):
        nonlocal cash,peak,drawdown,halt
        pnl=account(event,event['feature']['model_side'])
        if pnl is None:
            halt='FIRST_SELECTED_UNKNOWN_EXIT'
            return False
        cash+=pnl; peak=max(peak,cash); drawdown=max(drawdown,peak-cash)
        closed.append({'sid':event['sid'],'entry':event['t'],'exit':event['t']+900,'net_eur':pnl})
        for key,field in [('midpoint','midpoint_baseline_side'),('quote_count','quote_count_baseline_side')]:
            d=event['feature'][field]
            z=0. if d==0 else account(event,d)
            if z is None:
                comparator_missing[key]+=1
            else:
                comparator_totals[key]+=z
        return True
    for t in sorted({e['t'] for e in candidates}):
        if opened and opened['t']+900<=t:
            if not settle(opened):
                break
            opened=None
        if opened:
            continue
        group=[e for e in candidates if e['t']==t and e['feature'].get('state')=='SUPPORTED_FEATURE'
               and e['feature'].get('model_side') and admit(e['entry'],cash)]
        group.sort(key=lambda e:(e['entry']['cost_eur'],e['sid']))
        if group:
            opened=group[0]; selected.append({'sid':opened['sid'],'entry':t})
    if opened and not halt:
        settle(opened)
    return {'selected':selected,'closed':closed,'cash_from_known_closes_eur':cash,
            'complete_net_eur':None if halt else cash-200.,'closed_drawdown_eur':drawdown,
            'halt':halt or 'END','shadow_comparator_net_eur':{
                k:(None if halt or comparator_missing[k] else v) for k,v in comparator_totals.items()},
            'comparator_missing':dict(comparator_missing),'HARD21_demonstrated':False,
            'actual_orders':0,'actual_fills':0,'risk_is_planning_proxy':True}

def analyze_saved(full, decode_tick_page, native_accounts):
    """Pure adapter for authenticated existing costfrequency full-result schema.

    No old prediction, training or closed model is called. Cached pre-entry
    economic quantities are retained; fresh NET accounting is hypothetical.
    This function does not decrypt, export or publish raw market values.
    """
    quotes={(int(q['symbol_id']),int(q['boundary_ms'])//1000):q for q in full['raw_quote_receipts']}
    rows={r['sid']:r for r in full['all_identity_status']}
    graph=native_accounts.graph(list(rows.values()))
    unique={}
    for ev in full['events']:
        if ev['h']==15:
            if ev['t']+900 >= 1789603200:
                raise ValueError('PROTECTED_FORWARD_BOUNDARY')
            key=(ev['sid'],ev['t'])
            if key in unique and unique[key]['entry'] != ev['entry']:
                raise ValueError('DUPLICATE_ENTRY_CONFLICT')
            unique[key]=ev
    candidates=[]; states=Counter()
    for (sid,t),ev in sorted(unique.items()):
        q=quotes.get((sid,t)); pages={p['side']:p for p in q.get('pages',[])} if q else {}
        if set(pages)!={'bid','ask'}:
            f={'state':'MISSING_RAW_PAGES'}
        else:
            decoded={s:[(z.timestamp_ms,z.raw_tick/100000) for z in decode_tick_page(pages[s]['encoded'])] for s in ('bid','ask')}
            f=feature(decoded['bid'],decoded['ask'],t,any(p.get('hasMore',True) for p in pages.values()))
        states[f['state']]+=1
        candidates.append({'sid':sid,'t':t,'entry':ev['entry'],'feature':f})
    def account(ev,d):
        row=rows[ev['sid']]; contract=full['catalog']['full'][str(ev['sid'])]
        z=native_accounts.account(d,row,contract,ev['t'],ev['t']+900,.25,quotes,graph,2,.10,False)
        return z['net_eur'] if z is not None else None
    result=portfolio(candidates,account)
    iso=lambda t:datetime.fromtimestamp(t,timezone.utc).strftime('%G-W%V')
    weeks=sorted(set(full.get('summary',{}).get('weeks',[])) | {iso(e['t']) for e in candidates})
    weekly={}
    for week in weeks:
        events=[e for e in candidates if iso(e['t'])==week]
        closes=[e for e in result['closed'] if iso(e['entry'])==week]
        weekly[week]={'saved_boundaries':len(events),
                      'feature_states':dict(Counter(e['feature']['state'] for e in events)),
                      'modeled_entries':sum(iso(e['entry'])==week for e in result['selected']),
                      'known_closed_net_eur':sum(e['net_eur'] for e in closes) if closes else None,
                      'closed_trades_by_exit_week':sum(iso(e['exit'])==week for e in result['closed']),
                      'complete_week_coverage_or_HARD21_certified':False}
    return {'candidate_boundaries':len(candidates),'feature_states':dict(states),
            'portfolio':result,'weekly_support':weekly,'new_broker_requests':0,
            'source_scope':'ALL_EXISTING_AUTHENTIC_COSTFREQUENCY_15MIN_EVENTS_NO_BEST_SYMBOL',
            'economic_terms':'CURRENT_TERMS_AND_SLIPPAGE_FUNDING_SCENARIOS_NOT_ACTUAL_FILLS'}
