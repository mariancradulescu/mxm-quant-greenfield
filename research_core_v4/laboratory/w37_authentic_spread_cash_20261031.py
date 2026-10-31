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
from datetime import datetime, timezone
import json
from pathlib import Path
from .usd_pair_native_reception import SOURCES, START, END

GRID_MS = 300000
MAX_AGE_MS = 5000
REFERENCE_BASE_UNITS = 1000
SYMBOLS = ("EURUSD", "GBPUSD")
NATIVE_HISTORICAL_PRICE_SCALE = 100000
FX_PIP_POSITION = 4
RAW_UNITS_PER_PIP = NATIVE_HISTORICAL_PRICE_SCALE // 10**FX_PIP_POSITION

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

    Raw prices share native EURUSD/GBPUSD digits=5; historical scale 1e5.
    Cash ratio cancels the common native price-scale exactly.
    USD expense / observed EURUSD BID is conservative for USD liabilities.
    The reference units are NOT a broker-verified executable minimum volume.
    """
    bid,ask=symbol_book
    eur_bid,_=eur_book
    need(ask>bid>0 and eur_bid>0,"CASH_CONTRACT")
    eur=(Decimal(REFERENCE_BASE_UNITS)*Decimal(ask-bid)/Decimal(eur_bid))
    pips=Decimal(ask-bid)/Decimal(RAW_UNITS_PER_PIP)
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
        "schema":"mxm.w37.original.bidask.money-spread-support.v2-corrected-pips", 
        "supersedes_original_receipt": {"original_run":41227762678,"original_artifact_id":13052347106,
            "original_code_blob_sha1":"4f915a8c19bc5358925a7516d5010f00bf71029e",
            "original_receipt_frozen_unchanged":True,"pip_units_only_correction":True},
        "historical_raw_price_scale":NATIVE_HISTORICAL_PRICE_SCALE,
        "pip_position":FX_PIP_POSITION,
        "raw_units_per_pip":RAW_UNITS_PER_PIP,
        "partition":"EXPOSED_DEVELOPMENT_2026_W37_ONLY",
        "week":["2026-09-07T00:00:00Z","2026-09-14T00:00:00Z"],
        "grid_minutes":5,"grids_in_week":2016,
        "quote_max_age_ms":MAX_AGE_MS,
        "sample_before_same_timestamp_events":True,
        "same_timestamp_updates_atomic":True,
        "simultaneous_symbols":list(SYMBOLS),
        "reference_base_units":REFERENCE_BASE_UNITS,
        "cash_conversion":"actual strict-prior EURUSD BID native raw quote for USD liability; historical raw price-scale 1e5 cancels in raw ratio",
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
    # Official Open API: raw/100000; pipPosition=4 => 10 raw units = 1 pip.
    need(RAW_UNITS_PER_PIP==10,"OFFICIAL_PIP_SCALE")
    a=signed_spread_cash((110000,110010),(110000,110010))
    need(a[0]==Decimal(10000)/Decimal(110000) and a[1]==Decimal("1"),"MONEY_SCALE")
    b={"EURUSD":{"bid":(110000,START+GRID_MS-10),"ask":(110010,START+GRID_MS-10)}}
    got,reason=book_at(b,"EURUSD",START+GRID_MS)
    need(reason=="READY" and got==(110000,110010),"STRICT_CAUSAL")
    need(book_at(b,"EURUSD",START+GRID_MS-11)[1]=="NOT_STRICT_PRIOR","FUTURE_OBSERVATION_REJECTED")
    need(book_at(b,"EURUSD",START+GRID_MS+6000)[1]=="STALE","STALE_REJECTED")
    b["EURUSD"]["ask"]=(110000,START+GRID_MS-10)
    need(book_at(b,"EURUSD",START+GRID_MS)[1]=="LOCKED_OR_CROSSED","LOCKED_REJECTED")
    b["EURUSD"]["ask"]=(None,START+GRID_MS-10)
    need(book_at(b,"EURUSD",START+GRID_MS)[1]=="CONFLICT","SAME_MS_AMBIGUITY")
    need(percentile([Decimal(1),Decimal(2),Decimal(3)],50)==2,"MEDIAN")
    small=signed_spread_cash((110000,110001),(110000,110001))
    need(small[1]==Decimal("0.1") and small[0]==Decimal(1000)/Decimal(110000),"ONE_RAW_UNIT_IS_TENTH_PIP")
    need(small[2]==Decimal(20000)/Decimal(220001),"BPS_UNCHANGED")
    need(signed_spread_cash((110000,110020),(110000,110001))[1]==Decimal("2"),"TWO_PIPS")
    print("MXM_AUTHENTIC_SPREAD_SOURCE_BLIND_CASH_CAUSAL_TESTS_PASS")


# The immutable original public result from Actions #41227762678 is an input
# invariant, NOT overwritten. Only pips, semantic scale labels and diagnostics
# may differ in v2; EUR, bps and the original 2016-slot reason counts must match.
ORIGINAL_PUBLIC_AGGREGATES = {
    "EURUSD": {
        "eur":{"median":"0.008607","p90":"0.025872","max":"1.058128"},
        "bps":"0.086068","valid":305,"corrected_pips":"0.100000",
        "unavailable":{"LOCKED_OR_CROSSED":836,"MISSING":1,"STALE":874}},
    "GBPUSD": {
        "eur":{"median":"0.017211","p90":"0.043021","max":"1.419440"},
        "bps":"0.147848","valid":255,"corrected_pips":"0.200000",
        "unavailable":{"EURUSD_FX_LOCKED_OR_CROSSED":699,"EURUSD_FX_STALE":197,
                       "LOCKED_OR_CROSSED":173,"MISSING":1,"STALE":691}}
}

def coverage_diagnostics(eur_path,gbp_path):
    """Diagnose missingness with the SAME original 5-second strict-prior rule.

    Exposes only aggregate counts, not reconstructed raw quote prices or stamps.
    A bid/ask inversion between different side timestamps is NOT proof of a
    simultaneously crossed broker book or actual historical arrival order.
    """
    paths={"EURUSD":Path(eur_path),"GBPUSD":Path(gbp_path)}
    book={sym:{} for sym in SYMBOLS}
    totals={sym:collections.Counter() for sym in SYMBOLS}
    weekday={sym:collections.defaultdict(collections.Counter) for sym in SYMBOLS}
    byhour={sym:collections.defaultdict(collections.Counter) for sym in SYMBOLS}
    status={sym:collections.Counter() for sym in SYMBOLS}
    lag={sym:collections.Counter() for sym in SYMBOLS}
    age={sym:collections.Counter() for sym in SYMBOLS}
    conflicts=collections.Counter()
    next_sample=START

    def sample(t):
        fx,fx_reason=book_at(book,"EURUSD",t)
        day=str(datetime.fromtimestamp(t/1000,timezone.utc).weekday())
        hour=str(datetime.fromtimestamp(t/1000,timezone.utc).hour)
        for sym in SYMBOLS:
            pair,why=book_at(book,sym,t)
            code=why if pair is None else ("EURUSD_FX_"+fx_reason if fx is None else "READY")
            totals[sym][code]+=1
            weekday[sym][day][code]+=1
            byhour[sym][hour][code]+=1
            if "bid" in book[sym] and "ask" in book[sym]:
                bid,bt=book[sym]["bid"];ask,at=book[sym]["ask"]
                if bid is not None and ask is not None:
                    skew=abs(bt-at)
                    lag[sym]["same_side_timestamp" if skew==0 else
                             "side_timestamp_skew_1_to_100ms" if skew<=100 else
                             "side_timestamp_skew_101_to_1000ms" if skew<=1000 else
                             "side_timestamp_skew_over_1000ms"]+=1
                    oldest=t-min(bt,at)
                    age[sym]["age_0_to_5000ms" if oldest<=5000 else
                             "age_5001_to_60000ms" if oldest<=60000 else
                             "age_over_60000ms"]+=1
                    if why=="LOCKED_OR_CROSSED":
                        status[sym]["equal_bid_ask" if ask==bid else "ask_below_bid"]+=1
                        status[sym]["same_timestamp" if at==bt else "asynchronous_side_timestamp"]+=1
                        status[sym]["side_skew_over_1000ms" if skew>1000 else "side_skew_at_most_1000ms"]+=1

    with paths["EURUSD"].open() as eh,paths["GBPUSD"].open() as gh:
        ordered=heapq.merge(source_stream(eh,"EURUSD"),source_stream(gh,"GBPUSD"))
        for t,group in itertools.groupby(ordered,key=lambda x:x[0]):
            while next_sample<=t and next_sample<END:
                sample(next_sample);next_sample+=GRID_MS
            byside=collections.defaultdict(set)
            for _,sym,side,raw in group: byside[sym,side].add(raw)
            for (sym,side),values in byside.items():
                if len(values)>1:conflicts[sym]+=1
                book[sym][side]=(next(iter(values)) if len(values)==1 else None,t)
        while next_sample<END:
            sample(next_sample);next_sample+=GRID_MS

    result={}
    for sym in SYMBOLS:
        need(sum(totals[sym].values())==2016,"DIAGNOSTIC_WEEK_COMPLETENESS_"+sym)
        need(sum(sum(v.values()) for v in weekday[sym].values())==2016,"DIAGNOSTIC_DAYS_"+sym)
        need(sum(sum(v.values()) for v in byhour[sym].values())==2016,"DIAGNOSTIC_HOURS_"+sym)
        need(conflicts[sym]==0,"NATIVE_ATOMIC_SOURCE_CONFLICT_REAPPEARED_"+sym)
        need(status[sym]["equal_bid_ask"]+status[sym]["ask_below_bid"]==
             totals[sym]["LOCKED_OR_CROSSED"],"CROSSING_CLASSIFICATION_"+sym)
        result[sym]={
           "reasons":dict(totals[sym]),
           "weekday_utc_reasons":{str(k):dict(v) for k,v in sorted(weekday[sym].items())},
           "hour_utc_reasons":{str(k):dict(v) for k,v in sorted(byhour[sym].items(),key=lambda z:int(z[0]))},
           "book_shape_within_fresh_5s":dict(status[sym]),
           "last_side_timestamp_lag_all_recorded_grid":dict(lag[sym]),
           "oldest_side_age_all_recorded_grid":dict(age[sym]),
           "same_ms_atomic_conflicts":conflicts[sym],
           "conclusions": {
              "locked_or_crossed_are_merged_in_original":True,
              "nonzero_side_skew_is_not_same_timestamp_broker_cross":True,
              "staleness_censored_not_free_spread":True,
              "no_broker_arrival_order_or_execution_certified":True}
        }
    return result

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
        receipt["coverage_diagnostics"]=coverage_diagnostics(a.eur,a.gbp)
        for symbol,legacy in ORIGINAL_PUBLIC_AGGREGATES.items():
            row=receipt["data"][symbol]
            need(row["observed_1000_units_spread_eur"]==legacy["eur"] and
                 row["observed_spread_bps_median"]==legacy["bps"] and
                 row["complete_native_strict_prior_samples"]==legacy["valid"] and
                 row["unavailable"]==legacy["unavailable"] and
                 row["observed_spread_pips_median"]==legacy["corrected_pips"],"ORIGINAL_CASH_BPS_AND_COVERAGE_UNCHANGED_"+symbol)
            need(receipt["coverage_diagnostics"][symbol]["reasons"]==
                 {"READY":legacy["valid"],**legacy["unavailable"]},"DIAGNOSTIC_REASON_PARITY_"+symbol)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        need(not a.out.exists(),"NO_RESULT_OVERWRITE")
        a.out.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
        print("MXM_AUTHENTIC_BIDASK_W37_MONETARY_OBSERVATION "+json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
