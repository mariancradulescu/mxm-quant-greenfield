"""Bounded W37 native BID/ASK monetary-spread observation; no predictive trial.

Reads two already authenticated EURUSD/GBPUSD VIEW-only source exports and
their SHA-bound receipts. One simultaneous EUR200 account is NOT simulated:
EUR amount is an illustrative 1,000 base-units instant-spread mark at a
strictly prior observed EURUSD BID; NOT minimum broker size, all-in cost,
fills, PnL, historical arrival order, liquidity or independent confirmation.
"""
from __future__ import annotations
import argparse
import collections
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import heapq
import io
import itertools
import json
from pathlib import Path
from .usd_pair_native_reception import SOURCES, START, END

GRID_MS = 300000
MAX_AGE_MS = 5000
REFERENCE_BASE_UNITS = 1000
SYMBOLS = ("EURUSD", "GBPUSD")

def need(condition, tag):
    if not condition:
        raise ValueError("MXM_W37_GENUINE_COST_" + tag)

def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda:handle.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()

def source_stream(handle, symbol):
    last = -1
    count = 0
    for raw_line in handle:
        row = json.loads(raw_line)
        need(set(row)=={"t","side","raw"}, "EXACT_FIELDS")
        t,side,value = row["t"],row["side"],row["raw"]
        need(type(t) is int and START <= t < END and t >= last, "SOURCE_CHRONOLOGY")
        need(side in ("bid","ask") and type(value) is int and value > 0, "SOURCE_PRICE")
        last=t
        count += 1
        yield (t,symbol,side,value)
    need(count == SOURCES[symbol]["bid"]+SOURCES[symbol]["ask"], "EXACT_SOURCE_ROW_COUNT")

def book_at(book, symbol, t):
    sides = book[symbol]
    if "bid" not in sides or "ask" not in sides: return None,"MISSING"
    b,bt = sides["bid"]; a,at = sides["ask"]
    if b is None or a is None: return None,"CONFLICT"
    if bt >= t or at >= t: return None,"NOT_STRICT_PRIOR"
    if min(t-bt,t-at)<0 or max(t-bt,t-at)>MAX_AGE_MS: return None,"STALE"
    if a<=b: return None,"LOCKED_OR_CROSSED"
    return (b,a),"READY"

def signed_spread_cash(symbol_book, eur_book):
    """USD spread for exactly 1k BASE units, converted using observed EURUSD BID.

    Raw prices share exact native EURUSD/GBPUSD digits=5, transport scale 1e7.
    USD expense / observed EURUSD BID is conservative for USD liabilities.
    The reference units are NOT a broker-verified executable minimum volume.
    """
    bid,ask=symbol_book
    eur_bid,_=eur_book
    need(ask>bid>0 and eur_bid>0,"CASH_CONTRACT")
    eur=(Decimal(REFERENCE_BASE_UNITS)*Decimal(ask-bid)/Decimal(eur_bid))
    pips=Decimal(ask-bid)/Decimal(1000)
    bps=Decimal(20000)*Decimal(ask-bid)/Decimal(ask+bid)
    return eur,pips,bps

def percentile(values,pct):
    need(values and 0<=pct<=100,"PERCENTILE_SOURCE")
    q=sorted(values)
    index=(len(q)-1)*pct/100
    low=int(index);high=min(low+1,len(q)-1)
    return q[low]+(q[high]-q[low])*Decimal(str(index-low))

def monetary_report(eur_path, gbp_path, *, source_prevalidated=False):
    paths={"EURUSD":Path(eur_path),"GBPUSD":Path(gbp_path)}
    for sym,path in paths.items():
        if source_prevalidated:
            receipt=json.loads(Path(str(path)+".receipt.json").read_bytes())
            expected=SOURCES[sym]
            need(receipt["symbol"]==sym and receipt["source_run"]==expected["run"]
                 and receipt["cipher_sha256"]==expected["cipher"]
                 and receipt["private_sha256"]==expected["private"]
                 and receipt["events"]==expected["bid"]+expected["ask"]
                 and digest(path)==receipt["derived_sha256"],"ORIGINAL_BRIDGE_"+sym)
    books={sym:{} for sym in SYMBOLS}
    observed={sym:[] for sym in SYMBOLS}
    reasons={sym:collections.Counter() for sym in SYMBOLS}
    hours={sym:collections.defaultdict(list) for sym in SYMBOLS}
    atomic_conflicts={sym:0 for sym in SYMBOLS}
    event_counts=collections.Counter()
    last_t=-1
    next_sample=START
    with paths["EURUSD"].open("r") as eh,paths["GBPUSD"].open("r") as gh:
        merged=heapq.merge(source_stream(eh,"EURUSD"),source_stream(gh,"GBPUSD"))
        for t,group in itertools.groupby(merged,key=lambda x:x[0]):
            need(t>=last_t,"MERGED_TIME_ORDER");last_t=t
            while next_sample<=t and next_sample<END:
                eur,eur_reason=book_at(books,"EURUSD",next_sample)
                for sym in SYMBOLS:
                    b,reason=book_at(books,sym,next_sample)
                    if b is None:
                        reasons[sym][reason]+=1
                    elif eur is None:
                        reasons[sym]["EURUSD_FX_"+eur_reason]+=1
                    else:
                        cash,pips,bps=signed_spread_cash(b,eur)
                        observed[sym].append((cash,pips,bps))
                        # UTC hours are observation support, NOT activity/fill windows.
                        hours[sym][(next_sample//3600000)%24].append(cash)
                next_sample+=GRID_MS
            # Atomically apply all original events with identical provider timestamp.
            # Multiple distinct values for one (time,symbol,side) invalidate that side.
            by_side=collections.defaultdict(set)
            for _,sym,side,value in group:
                by_side[sym,side].add(value);event_counts[sym]+=1
            for (sym,side),values in by_side.items():
                if len(values)>1:atomic_conflicts[sym]+=1
                books[sym][side]=(next(iter(values)) if len(values)==1 else None,t)
        while next_sample<END:
            eur,eur_reason=book_at(books,"EURUSD",next_sample)
            for sym in SYMBOLS:
                b,reason=book_at(books,sym,next_sample)
                if b is None:reasons[sym][reason]+=1
                elif eur is None:reasons[sym]["EURUSD_FX_"+eur_reason]+=1
                else:
                    cash,pips,bps=signed_spread_cash(b,eur)
                    observed[sym].append((cash,pips,bps))
                    hours[sym][(next_sample//3600000)%24].append(cash)
            next_sample+=GRID_MS
    need(next_sample==END and (END-START)//GRID_MS==2016,"FULL_WEEK_GRID")
    need(all(event_counts[sym]==SOURCES[sym]["bid"]+SOURCES[sym]["ask"]
        for sym in SYMBOLS),"ALL_ORIGINAL_EVENTS_USED")
    def rounded(x):
        return str(x.quantize(Decimal("0.000001"),rounding=ROUND_HALF_UP))
    out={}
    for sym in SYMBOLS:
        vals=observed[sym]
        need(len(vals)+sum(reasons[sym].values())==2016,"NO_SELECTION_BIAS")
        cash=[a for a,_,_ in vals];pips=[a for _,a,_ in vals];bps=[a for _,_,a in vals]
        out[sym]={
            "original_events":event_counts[sym],
            "atomic_same_ms_conflicts":atomic_conflicts[sym],
            "complete_native_strict_prior_samples":len(vals),
            "unavailable":dict(sorted(reasons[sym].items())),
            "observed_1000_units_spread_eur":{
              "median":rounded(percentile(cash,50)) if cash else None,
              "p90":rounded(percentile(cash,90)) if cash else None,
              "max":rounded(max(cash)) if cash else None},
            "observed_spread_pips_median":rounded(percentile(pips,50)) if pips else None,
            "observed_spread_bps_median":rounded(percentile(bps,50)) if bps else None,
            "hour_utc_available_samples":{str(h):len(z) for h,z in sorted(hours[sym].items())},
            "hour_utc_spread_eur_median":{str(h):rounded(percentile(z,50)) for h,z in sorted(hours[sym].items())}}
    return {
        "schema":"mxm.w37.original.bidask.money-spread-support.v1",
        "partition":"EXPOSED_DEVELOPMENT_2026_W37_ONLY",
        "week":["2026-09-07T00:00:00Z","2026-09-14T00:00:00Z"],
        "grid_minutes":5,"grids_in_week":2016,
        "quote_max_age_ms":MAX_AGE_MS,
        "sample_before_same_timestamp_events":True,
        "same_timestamp_updates_atomic":True,
        "simultaneous_symbols":list(SYMBOLS),
        "reference_base_units":REFERENCE_BASE_UNITS,
        "cash_conversion":"actual strict-prior EURUSD BID native raw quote for USD liability; price-scale 1e7",
        "data":out,
        "broker_spread_cost_observed_not_executable":True,
        "historical_arrival_order_proven":False,
        "true_native_minimum_volume_and_commissions_proven":False,
        "all_in_roundtrip_friction_certified":False,
        "other_instruments_research_excluded":False,
        "predictive_tests":0,
        "account_simulations":0,
        "net_eur_alpha":False,
        "HARD21":False,"broker_orders":0,"cloud_activations":0,
        "new_broker_requests":0
    }

def selftest():
    # Exact price-scale/cash sign: 100 raw ticks = 0.1 pip = ~0.009 EUR per 1k.
    a=signed_spread_cash((11000000,11000100),(11000000,11000100))
    need(a[0]==Decimal(100000)/Decimal(11000000) and a[1]==Decimal("0.1"),"MONEY_SCALE")
    b={"EURUSD":{"bid":(11000000,START+GRID_MS-10),"ask":(11000100,START+GRID_MS-10)}}
    got,reason=book_at(b,"EURUSD",START+GRID_MS)
    need(reason=="READY" and got==(11000000,11000100),"STRICT_CAUSAL")
    need(book_at(b,"EURUSD",START+GRID_MS-11)[1]=="NOT_STRICT_PRIOR","FUTURE_OBSERVATION_REJECTED")
    need(book_at(b,"EURUSD",START+GRID_MS+6000)[1]=="STALE","STALE_REJECTED")
    b["EURUSD"]["ask"]=(11000000,START+GRID_MS-10)
    need(book_at(b,"EURUSD",START+GRID_MS)[1]=="LOCKED_OR_CROSSED","LOCKED_REJECTED")
    b["EURUSD"]["ask"]=(None,START+GRID_MS-10)
    need(book_at(b,"EURUSD",START+GRID_MS)[1]=="CONFLICT","SAME_MS_AMBIGUITY")
    need(percentile([Decimal(1),Decimal(2),Decimal(3)],50)==2,"MEDIAN")
    print("MXM_AUTHENTIC_SPREAD_SOURCE_BLIND_CASH_CAUSAL_TESTS_PASS")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=["selftest","original"])
    p.add_argument("--eur",type=Path)
    p.add_argument("--gbp",type=Path)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    selftest()
    if a.mode=="original":
        need(a.eur and a.gbp and a.out,"PRIVATE_ORIGINAL_ARGS_REQUIRED")
        receipt=monetary_report(a.eur,a.gbp,source_prevalidated=True)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        need(not a.out.exists(),"NO_RESULT_OVERWRITE")
        a.out.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
        print("MXM_AUTHENTIC_BIDASK_W37_MONETARY_OBSERVATION "+json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
