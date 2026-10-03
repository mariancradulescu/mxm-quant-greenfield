"""Prospective quote-sequence preparation. No broker, response or execution entry point.

Only causal feature mechanics, requested-window metadata and support counts live
here. Real quotes have not been supplied to these helpers. Their synthetic proof
does not certify historical data availability, signal support or market power.
"""
from __future__ import annotations
import bisect
import math
import statistics
from datetime import datetime, timezone, timedelta


def validate_side(rows):
    last_ms = None
    last_tie = -1
    for ms, tick, tie in rows:
        if any(type(v) is not int for v in (ms, tick, tie)) or ms < 0 or tick <= 0:
            raise ValueError("invalid lossless integer quote row")
        expected = last_tie + 1 if ms == last_ms else 0
        if last_ms is not None and ms < last_ms or tie != expected:
            raise ValueError("chronology or equal-timestamp tie order")
        last_ms, last_tie = ms, tie


def feature_at(bids, asks, t_ms, lookback_seconds):
    """Features use completed information <=t only; t-L excluded from counts.

    Integer prices share the broker's 1e5 scaling, which cancels in ratios.
    Per-side tie order is retained. No cross-side order, volume or order-flow
    inference is invented from historical top-of-book price events.
    """
    if type(t_ms) is not int or t_ms % 1000 or lookback_seconds not in (10, 30):
        raise ValueError("frozen second clock/lookback")
    validate_side(bids); validate_side(asks)
    # Millisecond timestamps cannot establish an undocumented intra-ms order.
    # Preserve every raw row but censor a feature whose information window has
    # distinct prices at the same side timestamp; do not reorder to get a signal.
    for rows in (bids, asks):
        recent=[r for r in rows if t_ms-62000<=r[0]<=t_ms]
        if any(a[0]==b[0] and a[1]!=b[1] for a,b in zip(recent,recent[1:])):
            return None
    bt=[r[0] for r in bids]; at=[r[0] for r in asks]
    def snap(ms):
        bi=bisect.bisect_right(bt, ms)-1; ai=bisect.bisect_right(at, ms)-1
        if bi < 0 or ai < 0: return None
        b=bids[bi]; a=asks[ai]
        if ms-b[0] > 2000 or ms-a[0] > 2000 or a[1] < b[1]: return None
        return ((b[1]+a[1])/2, math.log(a[1]/b[1])*10000)
    current=snap(t_ms); past=snap(t_ms-lookback_seconds*1000)
    baseline=[snap(t_ms-i*1000) for i in range(1,61)]
    valid=[v[1] for v in baseline if v is not None]
    if current is None or past is None or len(valid)<45: return None
    med=statistics.median(valid)
    if med<=0: return None
    up=down=0; boundary=t_ms-lookback_seconds*1000
    for rows, times in ((bids,bt),(asks,at)):
        lo=bisect.bisect_right(times,boundary);hi=bisect.bisect_right(times,t_ms)
        for i in range(max(1,lo),hi):
            delta=rows[i][1]-rows[i-1][1]
            up+=delta>0;down+=delta<0
    if up+down<6: return None
    imbalance=(up-down)/(up+down)
    displacement=abs(math.log(current[0]/past[0])*10000)/med
    return {"t_ms":t_ms,"lookback_seconds":lookback_seconds,
            "directional_revision_count":up+down,"up_count":up,"down_count":down,
            "signed_revision_imbalance":imbalance,"baseline_valid_snapshots":len(valid),
            "median_spread_baseline_bps":med,"spread_filter_pass":current[1]<=med,
            "net_mid_displacement_units":displacement,
            "signal_thresholds":{str(th):abs(imbalance)>=th and displacement<=.75 and current[1]<=med for th in (.6,.8)}}


def request_manifest(design):
    rows=[];cutoff=datetime.fromisoformat(design["protected_forward_start_utc"].replace("Z","+00:00"))
    for s in design["signal_symbols"]:
        for day in sorted(design["calendar"]["dates_utc"]):
            for wi,(start,end) in enumerate(design["calendar"]["windows_utc"]):
                first=datetime.fromisoformat(day+"T"+start+"+00:00")-timedelta(seconds=120)
                last=datetime.fromisoformat(day+"T"+end+"+00:00")+timedelta(seconds=105)
                if last>=cutoff or first>=last or (last-first).total_seconds()>604800:
                    raise ValueError("protected boundary or oversized historical request")
                for side in ("BID","ASK"):
                    rows.append({"symbol":s["symbol"],"symbol_id":s["symbol_id"],"date_utc":day,
                        "window_index":wi,"side":side,"from_ms":int(first.timestamp()*1000),
                        "to_ms":int(last.timestamp()*1000),"empty_window_must_be_recorded":True})
    if len({(r['symbol_id'],r['date_utc'],r['window_index'],r['side']) for r in rows})!=len(rows):
        raise ValueError("duplicate request identity")
    return rows


def support_summary(events):
    """Endpoint completeness booleans only; never price differences or responses.

    Caller must provide the complete attempted-event ledger, not completed-only
    rows. Retention is completed/attempted. Do not supply market data in this task.
    """
    if any(type(e['complete']) is not bool or e['window_index'] not in range(3) for e in events):
        raise ValueError("support ledger schema")
    complete=[e for e in events if e['complete']]
    counts=[sum(e['window_index']==w for e in complete) for w in range(3)]
    dates={e['date_utc'] for e in complete}
    weeks={datetime.fromisoformat(d).date().isocalendar()[:2] for d in dates}
    retention=len(complete)/len(events) if events else 0
    return {"completed_events":len(complete),"attempted_events":len(events),
        "distinct_dates":len(dates),"distinct_iso_weeks":len(weeks),"per_window":counts,
        "retention":retention,"pass":len(complete)>=100 and len(dates)>=18 and len(weeks)>=10
            and retention>=.8 and min(counts)>=15}


def deny_response(*args,**kwargs):
    raise PermissionError("No real response or broker acquisition authority installed for next wave")


def verify_complete_partition(frm_ms,to_ms,leaves):
    """Audit sanitized interval metadata, not quote values or broker requests."""
    cursor=frm_ms
    for lo,hi,has_more in sorted(leaves):
        if lo!=cursor or hi<lo or hi>to_ms or has_more:
            raise ValueError("lossless pagination incomplete, overlap, gap or truncation")
        cursor=hi+1
    if cursor!=to_ms+1:raise ValueError("request coverage incomplete")
    return True
