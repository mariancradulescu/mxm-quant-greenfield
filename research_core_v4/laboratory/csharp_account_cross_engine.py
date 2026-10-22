"""Cash-only parity of C# reference vs existing Python EUR200 continuous-account engine.

Replays C#'s *assumed* quoted execution price ledger as one hypothetical position
at a time, preserving exact side costs and avoiding double-charging slippage.
Not a broker fill, quote freshness, intrabar MTM, spread, free-margin or HARD21 certificate.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

from competition.continuous_account_replay_v2 import CapitalEvent, FEASIBLE, replay_continuous_account

D=Decimal
CANDIDATE="MXM_CSHARP_ORIGINAL_LEDGER_REFERENCE"
SYMBOL="EURUSD"
MAX_CASH_EPS=D("0.0005")


class ParityFailure(ValueError): pass


def need(ok:bool,code:str):
    if not ok: raise ParityFailure("MXM_CSHARP_ACCOUNT_PARITY_"+code)


def time(t):
    return datetime.fromtimestamp(int(t)/1000,tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")


def cash_parity(report:dict)->dict:
    need(report["schema"]=="mxm.csharp.reference-replay.v1","SCHEMA")
    need(report["classification"] in {
        "SYNTHETIC_MATHEMATICAL_ONLY","ARTIFICIAL_SCENARIO_COST_FX_TEST_ONLY",
        "OBSERVED_PEPPERSTONE_QUOTES_ASSUMPTION_SCENARIO_UNCERTIFIED"},"CLASS")
    need(not report["pepperstone_historical_fills_proven"] and
         not report["cTrader_native_backtest"] and
         not report["broker_historical_costs_verified"] and
         not report["economic_identity_opened"] and
         report["full_iso_weeks_evaluated"]==0 and not report["hard21"],"NO_CERTIFICATION")
    need(report["initial_equity_eur"]==200 and
         report["economic_entries"]==report["economic_exits"],"ACCOUNT_CONTRACT")
    assumptions=report["modeled_assumptions"]
    qty=D(str(assumptions["position_units"]))
    fee=D(str(assumptions["commission_eur_per_side"]))
    fx=D(str(assumptions["fx_eur_per_usd"]))
    need(qty>0 and fee>=0 and fx>0 and qty==1000,"MODELED_VOLUME")
    events=[]; open_position=None; sequence=0
    delta_values=[]
    entry_sum=exit_sum=D(0)
    for z in report["ledger"]:
        kind=z["kind"]
        need(kind in {"ENTRY","EXIT"},"LEDGER_EVENT")
        ts=time(z["timestamp_ms"])
        price=D(str(z["price"]))
        need(price>0 and D(str(z["charged_commission_eur"]))==fee,"PRICE_FEE")
        if kind=="ENTRY":
            need(open_position is None and z["units"]==1000 and z["direction"] in (-1,1),"MULTIPLE_OR_INVALID_ENTRY")
            sequence+=1
            ident="p"+str(sequence)
            open_position={"id":ident,"dir":z["direction"],"price":price,"time":z["timestamp_ms"]}
            entry_sum+=1
            events.append(CapitalEvent(timestamp_utc=ts,kind="ENTRY",candidate_id=CANDIDATE,symbol=SYMBOL,position_id=ident,
                direction="LONG" if z["direction"]==1 else "SHORT",direction_feasibility=FEASIBLE,
                volume_cents=100000,min_volume_cents=100000,step_volume_cents=100000,max_volume_cents=100000,
                margin_eur=D(str(z["margin_eur"])),price=price,base_units=qty,quote_to_eur_rate=fx,
                transaction_cost_eur=fee))
        else:
            need(open_position is not None and z["direction"]==open_position["dir"] and
                 z["entry_timestamp_ms"]==open_position["time"],"EXIT_ENTRY_BINDING")
            gross=D(z["direction"])*qty*(price-open_position["price"])*fx
            claimed=D(str(z["gross_price_pnl_eur"]))
            need(abs(gross-claimed)<MAX_CASH_EPS,"GROSS_RECONCILIATION")
            delta_values.append(gross-claimed)
            exit_sum+=1
            events.append(CapitalEvent(timestamp_utc=ts,kind="EXIT",candidate_id=CANDIDATE,symbol=SYMBOL,position_id=open_position["id"],
                price=price,quote_to_eur_rate=fx,transaction_cost_eur=fee))
            open_position=None
    need(open_position is None and int(entry_sum)==int(exit_sum)==report["economic_entries"],
         "TERMINAL_FLAT")
    # Independent Python account contract is re-used verbatim: one continuous
    # EUR200 account, no weekly/monthly cash reset, no fabricated deposits.
    result=replay_continuous_account(events,starting_equity_eur=D("200"),
        account_type="NETTED",total_margin_calculation_type="SUM",same_symbol_overlap_allowed=False)
    need(result.status=="COMPLETE" and result.halt_reason is None,"HALTED")
    need(result.accepted_entries==report["economic_entries"] and result.rejected_entries==0,"ENTRY_RECONCILIATION")
    difference=result.terminal_broker_equity_eur-D(str(report["final_equity_eur"]))
    need(abs(difference)<MAX_CASH_EPS,"CASH_MISMATCH")
    need(result.external_cashflow_net_eur==0 and result.financing_eur==0,"MONEY_SOURCE")
    need(abs(result.transaction_costs_eur-D(2)*fee*D(entry_sum))<MAX_CASH_EPS,
         "COST_DOUBLE_COUNT")
    # May not count the partial observed ISO week toward HARD21.
    need(sum(result.entries_by_iso_week.values())==entry_sum,"WEEK_ENTRY_ACCOUNT")
    return {
        "schema":"mxm.csharp.python-continuous-account-cash-parity.v1",
        "classification":"SAME_LEDGER_INDEPENDENT_ACCOUNT_ENGINE_NOT_INDEPENDENT_MARKET_EVIDENCE",
        "input_classification":report["classification"],
        "shared_initial_capital_eur":200,
        "entry_count":int(entry_sum),"exit_count":int(exit_sum),
        "terminal_csharp_balance_eur":str(report["final_equity_eur"]),
        "terminal_python_account_balance_eur":str(result.terminal_broker_equity_eur),
        "cash_difference_eur":str(difference),
        "max_allowed_rounding_difference_eur":str(MAX_CASH_EPS),
        "explicit_commission_debit_eur":str(result.transaction_costs_eur),
        "embedded_price_slippage_and_spread_not_charged_twice":True,
        "account_cashflow_reset_or_deposit":False,
        "all_mark_to_market_path_parity_proven":False,
        "multi_symbol_portfolio_parity_proven":False,
        "actual_historical_bidask_fills_proven":False,
        "historical_broker_margin_or_fee_authority":False,
        "full_iso_week_coverage":0,"hard21":False,
        "broker_requests":0,"orders":0,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("reference_report")
    parser.add_argument("--out")
    args=parser.parse_args()
    with open(args.reference_report) as f: report=json.load(f)
    receipt=cash_parity(report)
    output=json.dumps(receipt,sort_keys=True,separators=(",",":"))
    if args.out:
        from pathlib import Path
        path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(output+"\n")
    print("MXM_CSHARP_INDEPENDENT_ACCOUNT_CASH_PARITY "+output)


if __name__=="__main__":main()
