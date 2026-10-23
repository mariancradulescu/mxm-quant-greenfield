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

def need(ok, reason):
    if not ok:
        raise ValueError('MXM_WEEK37_ATTRIBUTION_' + reason)

def number(x):
    try: z = D(str(x))
    except (ValueError, InvalidOperation): raise ValueError('MXM_WEEK37_ATTRIBUTION_NON_NUMBER')
    need(z.is_finite(), 'NONFINITE')
    return z

def attribute(report):
    need(report['schema']=='mxm.csharp.native-exposed-quote-to-one-account.v1' and
         report['classification']==EXPECTED and
         report['original_native_run_id']==39917922508 and
         report['quote_events']==685474 and
         report['authenticated_requested_iso_week_input']=='2026-W37' and
         not report['historical_broker_fills_proven'] and
         not report['hard21_proven'] and not report['all_cost_components_verified'] and
         report['new_broker_requests']==report['live_orders']==0,
         'PROVENANCE_AND_LIMITATIONS')
    a=report['account']
    need(number(a['initial_capital_eur'])==D(200) and
         not a['hard21_proven'] and not a['broker_fills_proven'] and
         not a['costs_broker_verified'], 'CONTINUOUS_UNCERTIFIED_ACCOUNT')
    gross = fee = D(0)
    cash = D(200)
    entries=exits=0
    counts=Counter()
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
            cash-=cost
            entries+=1
            counts[stamp.date().isoformat()]+=1
        else:
            realized=number(e['gross_eur'])
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
    cash_end=number(a['final_cash_eur'])
    equity=number(a['marked_equity_eur'])
    need(abs(cash-cash_end)<=D('0.000001'),'FINAL_CASH_MISMATCH')
    floating=equity-cash_end
    realized_net=gross-fee
    full_net=realized_net+floating
    need(abs(full_net-(equity-D(200)))<=D('0.000001'),'NET_EQUITY_IDENTITY')
    need(len(counts)<=7,'DAILY_COUNT')
    return {
      'schema':'mxm.csharp.week37.exploratory-account-loss-attribution.v1',
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
