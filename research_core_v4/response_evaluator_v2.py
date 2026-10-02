from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

import numpy as np

HORIZONS = (3, 6, 12, 48)
VOL_STATES = ("LOW", "HIGH")
DEV_BLOCK_ANCHOR = datetime(2025, 9, 15, tzinfo=timezone.utc)
CONFIRM_BLOCK_ANCHOR = datetime(2025, 1, 6, tzinfo=timezone.utc)
CONTEXTS = ("FX_SPOT", "SPOT_CRYPTO", "US_EQUITY_EXTENDED_HOURS")
DEFAULT_PERMUTATIONS = 1023
DEFAULT_SEED = 20261002


@dataclass(frozen=True)
class M5Bar:
    time: datetime
    close: float


@dataclass(frozen=True)
class CompletedBucket:
    start: datetime
    end: datetime
    close: float


@dataclass(frozen=True)
class SignalEvent:
    context: str
    symbol: str
    symbol_id: int
    trigger_time: datetime
    signal_direction: int
    vol_state: str
    arm: str
    m15_close: float
    h1_rms24: float
    week_key: str
    path_available: tuple[bool, bool, bool, bool]
    utc_hour: int
    day_of_week: str
    session_label: str
    dst_regime: str | None


@dataclass(frozen=True)
class PairedUnit:
    context: str
    symbol: str
    week_key: str
    signal_direction: int
    vol_state: str
    horizon: int
    full_mean: float
    baseline_mean: float

    @property
    def contrast(self) -> float:
        return self.full_mean - self.baseline_mean


def parse_utc(value: str) -> datetime:
    v = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def read_m5_csv(path: str | Path) -> list[M5Bar]:
    rows: list[M5Bar] = []
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"time_utc", "close"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"missing columns {required} in {path}")
        for row in reader:
            rows.append(M5Bar(parse_utc(row["time_utc"]), float(row["close"])))
    rows.sort(key=lambda x: x.time)
    if any(rows[i].time >= rows[i + 1].time for i in range(len(rows) - 1)):
        raise ValueError("M5 timestamps must be strictly increasing")
    return rows


def _epoch_minutes(dt: datetime) -> int:
    return int(dt.timestamp() // 60)


def completed_buckets(bars: Sequence[M5Bar], minutes: int) -> list[CompletedBucket]:
    if minutes % 5:
        raise ValueError("bucket minutes must be multiple of 5")
    n = minutes // 5
    by_time = {b.time: b.close for b in bars}
    result: list[CompletedBucket] = []
    for b in bars:
        if _epoch_minutes(b.time) % minutes != 0:
            continue
        expected = [b.time + timedelta(minutes=5 * i) for i in range(n)]
        if all(t in by_time for t in expected):
            result.append(CompletedBucket(b.time, b.time + timedelta(minutes=minutes), by_time[expected[-1]]))
    return result


def directional_state(buckets: Sequence[CompletedBucket], lookback: int) -> dict[datetime, int]:
    by_end = {b.end: b for b in buckets}
    step = buckets[0].end - buckets[0].start if buckets else timedelta(0)
    out: dict[datetime, int] = {}
    for b in buckets:
        prev_end = b.end - step * lookback
        if prev_end not in by_end:
            continue
        if any((b.end - step * k) not in by_end for k in range(lookback + 1)):
            continue
        prev = by_end[prev_end]
        r = math.log(b.close / prev.close)
        out[b.end] = 1 if r > 0 else (-1 if r < 0 else 0)
    return out


def h1_return_series(buckets: Sequence[CompletedBucket]) -> dict[datetime, float]:
    by_end = {b.end: b for b in buckets}
    out: dict[datetime, float] = {}
    one = timedelta(hours=1)
    for b in buckets:
        prev = by_end.get(b.end - one)
        if prev is not None:
            out[b.end] = math.log(b.close / prev.close)
    return out


def preentry_volatility_state(h1_buckets: Sequence[CompletedBucket]) -> dict[datetime, tuple[str, float]]:
    returns = h1_return_series(h1_buckets)
    ends = sorted(returns)
    rv4: dict[datetime, float] = {}
    for e in ends:
        seq = [e - timedelta(hours=k) for k in range(4)]
        if all(x in returns for x in seq):
            rv4[e] = sum(returns[x] ** 2 for x in seq)
    rv_ends = sorted(rv4)
    out: dict[datetime, tuple[str, float]] = {}
    for i, e in enumerate(rv_ends):
        prior = [rv4[x] for x in rv_ends[:i]][-40:]
        if len(prior) < 40:
            continue
        state = "HIGH" if rv4[e] > median(prior) else "LOW"
        r24_ends = [e - timedelta(hours=k) for k in range(24)]
        if not all(x in returns for x in r24_ends):
            continue
        rms24 = math.sqrt(sum(returns[x] ** 2 for x in r24_ends) / 24.0)
        if rms24 > 0:
            out[e] = (state, rms24)
    return out


def latest_at_or_before(keys: Sequence[datetime], target: datetime) -> datetime | None:
    i = bisect.bisect_right(keys, target) - 1
    return keys[i] if i >= 0 else None


def iso_week_key(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso.year:04d}-W{iso.week:02d}"


def session_diagnostics(context: str, trigger: datetime) -> tuple[str, str | None]:
    if context != "US_EQUITY_EXTENDED_HOURS":
        h = trigger.hour
        if 0 <= h < 7:
            return "ASIA_UTC", None
        if 7 <= h < 13:
            return "EUROPE_UTC", None
        if 13 <= h < 21:
            return "US_UTC", None
        return "LATE_UTC", None
    ny = trigger.astimezone(ZoneInfo("America/New_York"))
    dst = "DST" if ny.dst() and ny.dst() != timedelta(0) else "STANDARD"
    mins = ny.hour * 60 + ny.minute
    if 4 * 60 <= mins < 9 * 60 + 30:
        label = "PREMARKET"
    elif 9 * 60 + 30 <= mins < 16 * 60:
        label = "REGULAR"
    elif 16 * 60 <= mins < 20 * 60:
        label = "POSTMARKET"
    else:
        label = "OVERNIGHT"
    return label, dst


def build_signal_support(bars: Sequence[M5Bar], context: str, symbol: str, symbol_id: int) -> list[SignalEvent]:
    m15 = completed_buckets(bars, 15)
    h1 = completed_buckets(bars, 60)
    h4 = completed_buckets(bars, 240)
    m15_state = directional_state(m15, 4)
    h1_state = directional_state(h1, 4)
    h4_state = directional_state(h4, 3)
    vol = preentry_volatility_state(h1)
    m15_by_end = {b.end: b for b in m15}
    m5_times = {b.time for b in bars}
    h1_keys = sorted(set(h1_state) & set(vol))
    h4_keys = sorted(h4_state)
    events: list[SignalEvent] = []
    for e in sorted(m15_state):
        prev = e - timedelta(minutes=15)
        if prev not in m15_state:
            continue
        d = m15_state[e]
        if d == 0 or d == m15_state[prev]:
            continue
        h1e = latest_at_or_before(h1_keys, e)
        h4e = latest_at_or_before(h4_keys, e)
        if h1e is None or h4e is None:
            continue
        state, rms24 = vol[h1e]
        arm = "FULL" if h1_state[h1e] == d and h4_state[h4e] == d else "BASELINE"
        avail = tuple(all(e + timedelta(minutes=5 * i) in m5_times for i in range(h)) for h in HORIZONS)
        sess, dst = session_diagnostics(context, e)
        events.append(SignalEvent(
            context=context, symbol=symbol, symbol_id=symbol_id, trigger_time=e,
            signal_direction=d, vol_state=state, arm=arm,
            m15_close=m15_by_end[e].close, h1_rms24=rms24,
            week_key=iso_week_key(e), path_available=avail,
            utc_hour=e.hour, day_of_week=e.strftime("%A"), session_label=sess, dst_regime=dst,
        ))
    return events


def skeleton_canonical_line(e: SignalEvent) -> str:
    a = ",".join("1" if x else "0" for x in e.path_available)
    return "|".join([
        e.context,e.symbol,str(e.symbol_id),e.trigger_time.isoformat().replace("+00:00","Z"),
        str(e.signal_direction),e.vol_state,e.arm,e.week_key,a,str(e.utc_hour),e.day_of_week,e.session_label,e.dst_regime or "NA"
    ])


def skeleton_sha256(events: Iterable[SignalEvent]) -> str:
    h = hashlib.sha256()
    for line in sorted(skeleton_canonical_line(e) for e in events):
        h.update((line + "\n").encode("utf-8"))
    return h.hexdigest()


def require_real_response_authority(authority: dict) -> None:
    required = {
        "status": "AUTHORIZED_READY_NOT_EXECUTED",
        "scientific_design": "research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V2.json",
        "real_development_response_execution_authorized": True,
    }
    for k, v in required.items():
        if authority.get(k) != v:
            raise PermissionError(f"real response execution not authorized: {k}")
    if authority.get("protected_forward_opened") is not False:
        raise PermissionError("protected forward boundary not closed")


def response_for_event(e: SignalEvent, horizon: int, close_by_time: dict[datetime, float]) -> float | None:
    if horizon not in HORIZONS:
        raise ValueError("invalid frozen horizon")
    idx = HORIZONS.index(horizon)
    if not e.path_available[idx]:
        return None
    t = e.trigger_time + timedelta(minutes=5 * (horizon - 1))
    c = close_by_time.get(t)
    if c is None:
        return None
    return e.signal_direction * math.log(c / e.m15_close) / e.h1_rms24


def construct_paired_units(events: Sequence[SignalEvent], responses: dict[tuple[str, datetime, int], float]) -> list[PairedUnit]:
    grouped: dict[tuple, dict[str, list[float]]] = {}
    for e in events:
        for h in HORIZONS:
            key_resp = (e.symbol, e.trigger_time, h)
            if key_resp not in responses:
                continue
            k = (e.context,e.symbol,e.week_key,e.signal_direction,e.vol_state,h)
            grouped.setdefault(k,{"FULL":[],"BASELINE":[]})[e.arm].append(responses[key_resp])
    out=[]
    for k,arms in grouped.items():
        if arms["FULL"] and arms["BASELINE"]:
            out.append(PairedUnit(*k,float(np.mean(arms["FULL"])),float(np.mean(arms["BASELINE"]))))
    return out


def aggregate_direction_to_symbol_week(units: Sequence[PairedUnit]) -> dict[tuple, float]:
    g: dict[tuple,list[float]]={}
    for u in units:
        k=(u.context,u.symbol,u.week_key,u.vol_state,u.horizon)
        g.setdefault(k,[]).append(u.contrast)
    return {k:float(np.mean(v)) for k,v in g.items()}


def aggregate_symbol_to_context_week(symbol_week: dict[tuple,float], min_symbols: int) -> dict[tuple,float]:
    g: dict[tuple,list[float]]={}
    for (ctx,sym,wk,state,h),v in symbol_week.items():
        g.setdefault((ctx,wk,state,h),[]).append(v)
    return {k:float(np.mean(v)) for k,v in g.items() if len(v)>=min_symbols}


def week_index(week_key: str, anchor: datetime) -> int:
    year=int(week_key[:4]); week=int(week_key[-2:])
    monday=datetime.fromisocalendar(year,week,1).replace(tzinfo=timezone.utc)
    return (monday-anchor).days//7


def two_week_blocks(context_week: dict[tuple,float], anchor: datetime, context: str, state: str, horizon: int) -> tuple[np.ndarray,np.ndarray]:
    w={week_index(wk,anchor):v for (ctx,wk,st,h),v in context_week.items() if ctx==context and st==state and h==horizon}
    ids=[]; vals=[]
    if not w:
        return np.array([],int),np.array([],float)
    max_i=max(w)
    for bi in range(max_i//2+1):
        a,b=2*bi,2*bi+1
        if a in w and b in w:
            ids.append(bi); vals.append((w[a]+w[b])/2.0)
    return np.asarray(ids,int),np.asarray(vals,float)


def studentized_mean(x: np.ndarray) -> float:
    x=np.asarray(x,float)
    if len(x)<2:
        return float("nan")
    sd=x.std(ddof=1)
    return 0.0 if sd==0 and x.mean()==0 else (float("inf") if sd==0 and x.mean()>0 else float(x.mean()/(sd/math.sqrt(len(x)))))


def _permutation_t(x: np.ndarray, signs: np.ndarray) -> np.ndarray:
    n=len(x)
    pm=signs@x/n
    ss=float(np.dot(x,x))
    var=np.maximum((ss-n*pm*pm)/(n-1),1e-15)
    return pm/np.sqrt(var/n)


def local_shared_maxT(leaves: Sequence[tuple[np.ndarray,np.ndarray]], permutations: int=DEFAULT_PERMUTATIONS, seed: int=DEFAULT_SEED) -> dict:
    if not leaves:
        raise ValueError("no leaves")
    max_block=max((int(ids.max()) for ids,_ in leaves if len(ids)),default=-1)
    rng=np.random.default_rng(seed)
    shared=rng.choice(np.array([-1.0,1.0]),size=(permutations,max_block+1))
    obs=[]; perm_t=[]
    for ids,x in leaves:
        if len(x)<2:
            obs.append(float("nan")); perm_t.append(np.full(permutations,-np.inf)); continue
        obs.append(studentized_mean(x))
        perm_t.append(_permutation_t(x,shared[:,ids]))
    mx=np.max(np.stack(perm_t,axis=1),axis=1)
    p=[]
    for t in obs:
        p.append(1.0 if not np.isfinite(t) else float((1+np.sum(mx>=t))/(permutations+1)))
    selected=min(range(len(p)),key=lambda i:(p[i],-obs[i] if np.isfinite(obs[i]) else float("inf"),i))
    return {"observed_t":obs,"adjusted_p":p,"family_p":p[selected],"selected_index":selected}


def holm_reject(pvalues: Sequence[float], alpha: float=0.05) -> list[bool]:
    p=np.asarray(pvalues,float); m=len(p); order=np.argsort(p); out=np.zeros(m,bool)
    for rank,idx in enumerate(order):
        if p[idx] <= alpha/(m-rank):
            out[idx]=True
        else:
            break
    return out.tolist()


def chronological_gate(values_by_week: dict[int,float], parts: int, min_positive: int) -> bool:
    if not values_by_week:
        return False
    keys=sorted(values_by_week)
    n=len(keys)
    positive=0
    for part in range(parts):
        lo=part*n//parts; hi=(part+1)*n//parts
        vals=[values_by_week[k] for k in keys[lo:hi]]
        if vals and float(np.mean(vals))>0:
            positive+=1
    return positive>=min_positive


def breadth_gate(symbol_means: dict[str,float], minimum_positive: int) -> bool:
    return sum(v>0 for v in symbol_means.values()) >= minimum_positive


def concentration_gate(symbol_means: dict[str,float], maximum_share: float=0.50) -> bool:
    vals=np.abs(np.asarray(list(symbol_means.values()),float))
    if not len(vals) or vals.sum()==0:
        return False
    return float(vals.max()/vals.sum()) <= maximum_share


def support_fail_closed(*, full_events:int, baseline_events:int, paired_units:int, blocks:int, min_full:int, min_baseline:int, min_paired:int, min_blocks:int) -> bool:
    return full_events>=min_full and baseline_events>=min_baseline and paired_units>=min_paired and blocks>=min_blocks


def confirmation_single_leaf_test(block_ids: np.ndarray, block_values: np.ndarray, permutations: int=DEFAULT_PERMUTATIONS, seed:int=DEFAULT_SEED) -> float:
    if len(block_values)<2:
        return 1.0
    rng=np.random.default_rng(seed)
    maxid=int(block_ids.max())
    signs=rng.choice(np.array([-1.0,1.0]),size=(permutations,maxid+1))[:,block_ids]
    obs=studentized_mean(block_values)
    pt=_permutation_t(block_values,signs)
    return float((1+np.sum(pt>=obs))/(permutations+1))


def evaluate_real_development(*, authority: dict, events: Sequence[SignalEvent], bars_by_symbol: dict[str,Sequence[M5Bar]]) -> dict:
    require_real_response_authority(authority)
    responses: dict[tuple[str,datetime,int],float]={}
    for sym,bars in bars_by_symbol.items():
        close={b.time:b.close for b in bars}
        for e in events:
            if e.symbol!=sym:
                continue
            for h in HORIZONS:
                r=response_for_event(e,h,close)
                if r is not None:
                    responses[(sym,e.trigger_time,h)]=r
    return {"response_count":len(responses),"paired_units":len(construct_paired_units(events,responses))}


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--self-test-summary",action="store_true")
    args=ap.parse_args()
    if args.self_test_summary:
        print(json.dumps({"module":"response_evaluator_v2","real_execution_default":"DENIED","horizons":HORIZONS,"permutations":DEFAULT_PERMUTATIONS}))
        return
    raise SystemExit("Real response execution is intentionally unavailable from CLI at the preoutcome stop boundary.")


if __name__ == "__main__":
    main()
