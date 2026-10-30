"""MXM B-E: one-time upper-bound cost-vs-HARD21 feasibility on authenticated
PRIVATE original-derived annual H1 tape. No strategy, no alpha and no broker
cost/fill claim. An all-knowing hindsight oracle is a deliberately UNTRADABLE
upper bound, not a signal or a backtest. Every available symbol is considered
for every predetermined 07..15 UTC weekday hour; no optimized roster, model,
training, winner-only dates, broker orders or new source requests.

For each slot select max absolute next-hour signed bps movement over available
symbol outcomes (oracle sees the future). A single position is hypothetically
opened 5 minutes after hour end and closed 60 minutes after hour end; consecutive
hourly slots do not overlap. Stress friction = c bps per entry-exit episode.
Upper-bound portfolio with >=21 entries in a week is max over k>=21 of the
cumulative top-k oracle slot net results. If fewer than 21 observable slots,
week fails support. Can NOT translate sums into EUR P&L or native fills.
No individual source market prices, returns, dates or trading decisions are
published; public weekly UTC counts and aggregated oracle envelopes only.
"""
from __future__ import annotations
import argparse,collections,datetime as dt,hashlib,json,math,pathlib,statistics

EXPECTED_SHA='7157db48811ed1f1e4583ab567c6e04c876a4c4738c4bd242f182632fff54ebb'
START=dt.datetime(2025,9,29,tzinfo=dt.timezone.utc)
END=dt.datetime(2026,6,1,tzinfo=dt.timezone.utc)
EXPECTED_SYMBOLS=('AUDJPY','CHFJPY','EURAUD','EURCHF','EURGBP','EURJPY','GBPJPY','NZDUSD')
COSTS=(0,2,5,10,20,40)

def weekstamp(t): return f'{t.isocalendar().year}-W{t.isocalendar().week:02d}'

def calculate(slot_moves:list[float], cost:float)->dict:
    # Largest absolute future gross move per permissible slot is a PERFECT-DIRECTION
    # hindsight upper bound, even before broker lot/margin/fee feasibility.
    ranks=sorted((v-cost for v in slot_moves),reverse=True)
    pos=sum(x>0 for x in ranks)
    if len(ranks)<21:
        return {'capacity_21':False,'profitable_slots':pos,'max_net_sum_bps_ge21':None,'oracle_entries_at_max':None}
    sums=[];v=0
    for i, net in enumerate(ranks,1):
        v+=net
        if i>=21:sums.append((v,i))
    upper,k=max(sums,key=lambda x:x[0])
    return {'capacity_21':True,'profitable_slots':pos,'max_net_sum_bps_ge21':round(upper,5),'oracle_entries_at_max':k}

def selftest():
    assert weekstamp(START)=='2025-W40'
    assert weekstamp(END-dt.timedelta(days=1))=='2026-W22'
    assert calculate([10]*25,5)['max_net_sum_bps_ge21']==125
    assert calculate([1]*25,5)['max_net_sum_bps_ge21']==-84
    assert calculate([1]*20,0)['capacity_21'] is False
    assert calculate([40,35]+[0]*19,10)['max_net_sum_bps_ge21']==-135
    print('MXM_ECONOMIC_CAPACITY_SOURCE_BLIND_SELFTEST_PASS')

def evaluate(source:pathlib.Path):
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED_SHA:raise ValueError('SOURCE_PRIVATE_HASH_MISMATCH')
    tape=json.loads(raw)
    if tuple(sorted(tape['symbols']))!=EXPECTED_SYMBOLS:raise ValueError('ROSTER_MISMATCH')
    if len(tape['bars'])!=32607:raise ValueError('AUTHENTIC_H1_CARDINALITY_MISMATCH')
    lookup=tape['outcome_lookup_PRIVATE_NOT_NATIVE_INPUT']
    spans=collections.defaultdict(dict)
    # The original exact tuple of 8 broker IDs was preselected for a different
    # closed experiment; no claim is made about other 137 annual symbols.
    for k,px in lookup.items():
        symbol,stamp=k.split('|',1)
        if symbol not in EXPECTED_SYMBOLS:raise ValueError('UNEXPECTED_SYMBOL')
        at=dt.datetime.fromisoformat(stamp.replace('Z','+00:00'))
        if not (START<=at<END and at.weekday()<5 and 7<=at.hour<=15):continue
        enter=float(px['entry']);exit=float(px['exit'])
        if not all(map(math.isfinite,(enter,exit))) or min(enter,exit)<=0:raise ValueError('INVALID_FUTURE_PRICE')
        if symbol in spans[at]:raise ValueError('DUPLICATED_PRICE')
        spans[at][symbol]=abs(10000*(exit/enter-1))
    weeks=[]
    t=START
    while t<END:
        key=weekstamp(t);slots=[];number_available=collections.Counter()
        for day in range(5):
            for hour in range(7,16):
                stamp=t+dt.timedelta(days=day,hours=hour)
                observed=spans.get(stamp,{})
                if observed:
                    slots.append(max(observed.values()))
                    number_available[len(observed)]+=1
        row={'iso_week':key,'slots_scheduled':45,'slots_with_any_observed_future':len(slots),
             'observations_in_slots':sum(n*c for n,c in number_available.items()),
             'slots_with_all_8_observed':number_available[8],
             'oracle_aggregate_max_gross_bps_sum':round(sum(slots),5),
             'oracle_median_slot_max_abs_bps':round(statistics.median(slots),5) if slots else None,
             'cost_scenarios':{str(c):calculate(slots,c) for c in COSTS}}
        weeks.append(row)
        t+=dt.timedelta(days=7)
    if len(weeks)!=35:raise ValueError('COMPLETE_WEEK_CONTRACT')
    summary={}
    for cost in COSTS:
        detail=[w['cost_scenarios'][str(cost)] for w in weeks]
        summary[str(cost)]={
         'weeks_with_21_or_more_available_slots':sum(x['capacity_21'] for x in detail),
         'weeks_with_at_least_21_oracle_cost_positive_slots':sum(x['profitable_slots']>=21 for x in detail),
         'weeks_with_positive_optimal_hindsight_ge21_upper_bound':sum(x['max_net_sum_bps_ge21'] is not None and x['max_net_sum_bps_ge21']>0 for x in detail),
         'mean_oracle_cost_positive_slots_per_week':round(sum(x['profitable_slots'] for x in detail)/35,3),
         'total_optimal_hindsight_ge21_bps_sum':round(sum(x['max_net_sum_bps_ge21'] or 0 for x in detail),5),
        }
    return {'schema':'mxm.source-limited.h1-hindsight-capacity-envelope.v1',
      'date_utc':'2026-10-30','partition':'EXPOSED_DEVELOPMENT_ONLY',
      'source_original_derived_sha256':EXPECTED_SHA,
      'provenance':'PRIMARY145 original M5 ZIPs sha 09d999... / 37a47...; eight previously retained Forex IDs, not entire universe',
      'scope':'8 fixed FX series, hourly next-open price episodes, 2025-W40..2026-W22',
      'oracle_uses_future_to_choose_pair_and_direction':True,
      'is_executable_alpha':False,'can_certify_broker_HARD21':False,
      'is_EUR200_account_PnL':False,'real_historical_Pepperstone_costs':False,
      'native_cloud_received':False,'orders':0,
      'only_one_hypothetical_trade_per_hour':True,
      'weekly_slots':45,'weeks':35,'eligible_slot_weeks':sum(w['slots_with_any_observed_future']>=21 for w in weeks),
      'source_future_outcome_pairs':len(lookup),
      'scenarios_roundtrip_bps_hypothetical':list(COSTS),
      'economics_upper_envelopes':summary,
      'weekly_aggregate_envelopes':weeks,
      'interpretation':'Future-seeing oracle upper bounds cannot show forecast skill. A positive bound never proves profitable strategy; negative bound prevents one in this exact market/exit/fee hypothetical. No broader market impossibility.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['selftest','analyze']);ap.add_argument('--source',type=pathlib.Path);ap.add_argument('--output',type=pathlib.Path);args=ap.parse_args()
    selftest()
    if args.mode=='analyze':
      if not(args.source and args.output):raise ValueError('EXPLICIT_PRIVATE_SOURCE_AND_PUBLIC_OUTPUT_REQUIRED')
      value=evaluate(args.source)
      args.output.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
      print(json.dumps({k:value[k] for k in ['source_original_derived_sha256','weeks','eligible_slot_weeks','source_future_outcome_pairs','economics_upper_envelopes']},indent=2))
if __name__=='__main__':main()
