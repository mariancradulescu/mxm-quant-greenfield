"""Independent accounting attribution of an existing modeled EUR200 full-week C# run.

Reads only a *result* of a fixed DEVELOPMENT model. No source requests, strategy
selection, candidate admission, changed execution assumptions or broker fills.
The round-trip spread and slippage are embedded in modeled execution prices and
MUST NOT be subtracted again from this accounting decomposition.
"""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal as D, InvalidOperation
from pathlib import Path

EXPECTED = 'PINNED_PEPPERSTONE_WEEK37_SINGLE_SYMBOL_MODELED_TERMS_DEVELOPMENT_EXPOSED'
EXPECTED_PRODUCT_STOP12 = 'PINNED_PEPPERSTONE_WEEK37_PRODUCT_DEFAULT_STOP12_MODELED_TERMS_DEVELOPMENT_EXPOSED'

def need(ok, reason):
    if not ok:
        raise ValueError('MXM_WEEK37_ATTRIBUTION_' + reason)

def number(x):
    try: z = D(str(x))
    except (ValueError, InvalidOperation): raise ValueError('MXM_WEEK37_ATTRIBUTION_NON_NUMBER')
    need(z.is_finite(), 'NONFINITE')
    return z

def attribute(report):
    product_stop12=report['classification']==EXPECTED_PRODUCT_STOP12
    need(report['schema']=='mxm.csharp.native-exposed-quote-to-one-account.v1' and
         report['classification'] in (EXPECTED,EXPECTED_PRODUCT_STOP12) and
         report['original_native_run_id']==39917922508 and
         report['quote_events']==685474 and
         report['authenticated_requested_iso_week_input']=='2026-W37' and
         not report['historical_broker_fills_proven'] and
         not report['hard21_proven'] and not report['all_cost_components_verified'] and
         report['new_broker_requests']==report['live_orders']==0,
         'PROVENANCE_AND_LIMITATIONS')
    policy=report['modeled_parameters']
    if product_stop12:
        need(policy['product_default_stop12'] is True and
             policy['product_stop_pips']==12 and
             number(policy['product_stop_distance_quote'])==D('0.0012'),
             'PRODUCT_STOP12_NO_REFIT')
    a=report['account']
    need(number(a['initial_capital_eur'])==D(200) and
         not a['hard21_proven'] and not a['broker_fills_proven'] and
         not a['costs_broker_verified'], 'CONTINUOUS_UNCERTIFIED_ACCOUNT')
    gross = fee = D(0)
    cash = D(200)
    entries=exits=0
    counts=Counter()
    # Single-position lifecycle audit of the SAME modeled ledger, not a new
    # strategy trial or a claim of broker execution. Never infer profitability
    # from a missing exit, overbooked entry, or incompatible direction.
    active_entry=None
    exit_counts=Counter()
    exit_nets=Counter()
    holding_minutes=[]
    previous=None
    for e in a['ledger']:
        need(e['kind'] in ('ENTRY','EXIT') and
             e['symbol']=='EURUSD' and e['direction'] in (-1,1),
             'LEDGER_EVENT')
        raw=e['utc']
        need(type(raw) is str,'TIME_TYPE')
        stamp=datetime.fromisoformat(raw.replace('Z','+00:00'))
        need(stamp.tzinfo is not None and stamp.utcoffset().total_seconds()==0 and
             datetime(2026,9,7,tzinfo=timezone.utc)<=stamp<
             datetime(2026,9,14,tzinfo=timezone.utc),'OUT_OF_WEEK_EVENT')
        need(previous is None or stamp>=previous,'LEDGER_ORDER')
        previous=stamp
        cost=number(e['commission_eur'])
        need(cost>=0,'NEGATIVE_COMMISSION')
        fee+=cost
        if e['kind']=='ENTRY':
            need(number(e['gross_eur'])==0,'ENTRY_HAS_GROSS')
            need(active_entry is None,'OVERLAPPING_ACCOUNT_POSITIONS')
            active_entry=(stamp,e['direction'],cost)
            cash-=cost
            entries+=1
            counts[stamp.date().isoformat()]+=1
        else:
            need(active_entry is not None and
                 active_entry[1]==e['direction'],'UNPAIRED_OR_WRONG_DIRECTION_EXIT')
            duration=D(str((stamp-active_entry[0]).total_seconds()))/D(60)
            need(duration>0,'NONCAUSAL_HOLDING_TIME')
            reason=e.get('reason')
            need(reason is None or reason in
                 ('REVERSAL','OBSERVED_QUOTE_STOP','NEUTRAL_FLAT','HORIZON12'),
                 'UNKNOWN_EXIT_REASON')
            label=reason or 'UNLABELED'
            realized=number(e['gross_eur'])
            exit_counts[label]+=1
            exit_nets[label]+=realized-cost-active_entry[2]
            holding_minutes.append(duration)
            active_entry=None
            gross+=realized
            cash+=realized-cost
            exits+=1
        need(abs(cash-number(e['cash_eur']))<=D('0.000001'),'CASH_LEDGER_MISMATCH')
    need(entries==a['accepted_entries'] and exits==a['executed_exits'] and
         entries-exits==a['open_positions'] and
         entries==a['entries_by_iso_week'].get('2026-W37',0) and
         entries==report['modeled_entries_in_requested_iso_week'] and
         (entries>=21)==report['modeled_21_entry_threshold_met'],
         'ENTRY_EXIT_AND_WEEK_COUNTS')
    need((active_entry is not None)==(a['open_positions']==1),
         'OPEN_POSITION_LIFECYCLE_MISMATCH')
    need(sum(exit_counts.values())==exits,'EXIT_REASON_RECOUNT')
    open_entry_fee=active_entry[2] if active_entry is not None else D(0)
    need(abs(sum(exit_nets.values(),D(0))-open_entry_fee-(gross-fee))
         <=D('0.000001'),'CLOSED_TRADE_FEE_AND_OPEN_ENTRY_IDENTITY')
    cash_end=number(a['final_cash_eur'])
    equity=number(a['marked_equity_eur'])
    need(abs(cash-cash_end)<=D('0.000001'),'FINAL_CASH_MISMATCH')
    floating=equity-cash_end
    realized_net=gross-fee
    full_net=realized_net+floating
    need(abs(full_net-(equity-D(200)))<=D('0.000001'),'NET_EQUITY_IDENTITY')
    need(len(counts)<=7,'DAILY_COUNT')
    same_ledger_without_commissions=gross+floating
    ordered_durations=sorted(holding_minutes)
    middle=len(ordered_durations)//2
    median_duration=(ordered_durations[middle] if len(ordered_durations)%2
      else (ordered_durations[middle-1]+ordered_durations[middle])/D(2)
      ) if ordered_durations else None
    return {
      'schema':'mxm.csharp.week37.exploratory-account-loss-attribution.v1',
      'model_variant':'PRODUCT_DEFAULT_STOP12' if product_stop12 else 'LEGACY_NO_STOP',
      'classification':'SAME_AUTHENTIC_WEEK_UNCERTIFIED_COUNTERFACTUAL_NO_NEW_STRATEGY_TRIAL',
      'input_source_run':39917922508,'iso_week':'2026-W37',
      'initial_cash_eur':'200',
      'modeled_entries':entries,'modeled_exits':exits,
      'modeled_open_positions':a['open_positions'],
      'modeled_entry_counts_by_utc_date':dict(sorted(counts.items())),
      'realized_gross_pnl_eur':str(gross),
      'modeled_total_commissions_eur':str(fee),
      'realized_net_cash_pnl_eur':str(realized_net),
      'unrealized_liquidation_mark_pnl_eur':str(floating),
      'final_modeled_cash_eur':str(cash_end),
      'final_modeled_bidask_equity_eur':str(equity),
      'net_modeled_marked_equity_pnl_eur':str(full_net),
      'modeled_max_drawdown_eur':str(number(a['max_drawdown_eur'])),
      'closed_positions_by_exit_reason':dict(sorted(exit_counts.items())),
      'closed_position_net_pnl_by_exit_reason_eur':
        {k:str(v) for k,v in sorted(exit_nets.items())},
      'closed_position_holding_minutes_min':
        str(ordered_durations[0]) if ordered_durations else None,
      'closed_position_holding_minutes_median':
        str(median_duration) if median_duration is not None else None,
      'closed_position_holding_minutes_max':
        str(ordered_durations[-1]) if ordered_durations else None,
      'open_entry_commission_eur':str(open_entry_fee),
      'static_zero_commission_same_ledger_pnl_eur':
        str(same_ledger_without_commissions),
      'unchanged_ledger_remains_negative_even_at_zero_commission':
        same_ledger_without_commissions<0,
      'static_zero_commission_is_not_a_new_account_replay':True,
      'spread_and_slippage_already_in_modeled_prices':True,
      'gross_pnl_is_after_spread_and_slippage_not_precost_midprice_alpha':True,
      'commissions_snapshot_not_dated_historical':True,
      'financing_margin_fills_execution_unverified':True,
      'historical_total_costs_proven':False,
      'actual_broker_trade_count':0,'hard21_proven':False,
      'scientific_confirmation':False,'economic_edge_proven':False,
      'new_strategy_trials':0,'new_broker_requests':0,'real_orders':0}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('report')
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    r=json.loads(Path(args.report).read_text(),parse_float=D)
    result=attribute(r)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print('MXM_WEEK37_ACCOUNT_ATTRIBUTION_DEVELOPMENT_ONLY '+json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
