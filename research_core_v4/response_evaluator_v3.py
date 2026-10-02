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

try:
    from research_core_v4.frozen_v2_semantics import (
        paired_arm_hierarchical_mean,
        select_leaf_index,
    )
except ModuleNotFoundError:
    from frozen_v2_semantics import paired_arm_hierarchical_mean, select_leaf_index

HORIZONS = (3, 6, 12, 48)
VOL_STATES = ("LOW", "HIGH")
DEV_BLOCK_ANCHOR = datetime(2025, 9, 15, tzinfo=timezone.utc)
CONFIRM_BLOCK_ANCHOR = datetime(2025, 1, 6, tzinfo=timezone.utc)
CONTEXTS = ("FX_SPOT", "SPOT_CRYPTO", "US_EQUITY_EXTENDED_HOURS")
DEFAULT_PERMUTATIONS = 1023
DEFAULT_SEED = 20261002

# Process-local capability: issued only to the exact sibling authority-bound runner file.
_EXECUTION_CAPABILITY = object()

def _runner_execution_capability() -> object:
    import inspect
    frame = inspect.currentframe()
    caller = frame.f_back if frame is not None else None
    expected = Path(__file__).resolve().with_name("development_execution_runner_v1.py")
    if caller is None or Path(caller.f_code.co_filename).resolve() != expected:
        raise PermissionError("direct evaluator capability issuance denied; use development_execution_runner_v1.py")
    return _EXECUTION_CAPABILITY


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
        "schema": "mxm.research-core-v4.first-development-response-execution-authority.v3",
        "status": "AUTHORIZED_READY_NOT_EXECUTED",
        "scientific_design": "research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V2.json",
        "real_development_response_execution_authorized": True,
        "confirmation_response_execution_authorized": False,
        "broker_acquisition_authorized": False,
        "quote_revision_v2_execution_authorized": False,
        "protected_forward_opened": False,
        "live_trading_authorized": False,
        "candidate_promotion_authorized": False,
    }
    for k, v in required.items():
        if authority.get(k) != v:
            raise PermissionError(f"real response execution not authorized: {k}")
    scope=authority.get("development_scope",{})
    if scope.get("permutations") != DEFAULT_PERMUTATIONS or scope.get("seed") != DEFAULT_SEED:
        raise PermissionError("frozen seed/permutation scope mismatch")
    if tuple(scope.get("contexts",[])) != CONTEXTS:
        raise PermissionError("frozen context scope mismatch")
    if tuple(scope.get("volatility_states",[])) != VOL_STATES:
        raise PermissionError("frozen volatility-state scope mismatch")
    if tuple(scope.get("response_horizons_m5",[])) != HORIZONS:
        raise PermissionError("frozen horizon scope mismatch")


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


def local_shared_maxT(
    leaves: Sequence[tuple[np.ndarray,np.ndarray]],
    permutations: int=DEFAULT_PERMUTATIONS,
    seed: int=DEFAULT_SEED,
    leaf_meta: Sequence[tuple[str,int]] | None=None,
) -> dict:
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
    if leaf_meta is None:
        leaf_meta=[(VOL_STATES[i//len(HORIZONS)],HORIZONS[i%len(HORIZONS)]) for i in range(len(p))]
    selected=select_leaf_index(p,obs,leaf_meta)
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


def evaluate_real_development(*args, **kwargs):
    raise PermissionError("Direct real-response evaluator execution is disabled. Use the authority-bound development_execution_runner_v1.py.")

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--self-test-summary",action="store_true")
    args=ap.parse_args()
    if args.self_test_summary:
        print(json.dumps({"module":"response_evaluator_v3","real_execution_default":"DENIED","horizons":HORIZONS,"permutations":DEFAULT_PERMUTATIONS}))
        return
    raise SystemExit("Real response execution is intentionally unavailable from CLI at the preoutcome stop boundary.")



# ---- Frozen development/confirmation gate helpers and complete development runner ----

def development_quarter_gate(values_by_week_index: dict[int,float], min_positive:int=3) -> bool:
    groups=[[] for _ in range(4)]
    for w,v in values_by_week_index.items():
        if 0 <= w <= 52: groups[min(3,w*4//53)].append(v)
    return sum(bool(g) and float(np.mean(g))>0 for g in groups) >= min_positive


def confirmation_tertile_gate(values_by_week_index: dict[int,float], min_positive:int=2) -> bool:
    groups=[[],[],[]]
    for w,v in values_by_week_index.items():
        if 0 <= w <= 7: groups[0].append(v)
        elif 8 <= w <= 15: groups[1].append(v)
        elif 16 <= w <= 24: groups[2].append(v)
    return sum(bool(g) and float(np.mean(g))>0 for g in groups) >= min_positive


def sha256_file(path: str|Path) -> str:
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def _filter_interval(bars:Sequence[M5Bar], start:datetime, end:datetime)->list[M5Bar]:
    return [b for b in bars if start <= b.time <= end]


def _responses_for_events(events:Sequence[SignalEvent], close_by_time:dict[datetime,float]):
    norm={};raw={}
    for e in events:
        for h in HORIZONS:
            idx=HORIZONS.index(h)
            if not e.path_available[idx]:continue
            t=e.trigger_time+timedelta(minutes=5*(h-1));c=close_by_time.get(t)
            if c is None:continue
            rr=e.signal_direction*math.log(c/e.m15_close)
            norm[(e.symbol,e.trigger_time,h)]=rr/e.h1_rms24
            raw[(e.symbol,e.trigger_time,h)]=rr*10000.0
    return norm,raw


def _leaf_aggregates(units:Sequence[PairedUnit],context:str,state:str,h:int,anchor:datetime,min_symbols:int):
    lu=[u for u in units if u.context==context and u.vol_state==state and u.horizon==h]
    sw=aggregate_direction_to_symbol_week(lu);cw=aggregate_symbol_to_context_week(sw,min_symbols)
    ids,blocks=two_week_blocks(cw,anchor,context,state,h)
    sym={}
    for (ctx,s,w,st,hh),v in sw.items():
        if ctx==context and st==state and hh==h:sym.setdefault(s,[]).append(v)
    symbol_means={s:float(np.mean(v)) for s,v in sym.items()}
    week_means={week_index(w,anchor):v for (ctx,w,st,hh),v in cw.items() if ctx==context and st==state and hh==h}
    return lu,sw,cw,ids,blocks,symbol_means,week_means


def _development_support_leaf(events,context,state,h,units,blocks):
    ce=[e for e in events if e.context==context];se=[e for e in ce if e.vol_state==state];idx=HORIZONS.index(h)
    cfull=sum(e.arm=="FULL" for e in ce);cbase=sum(e.arm=="BASELINE" for e in ce)
    sfull=sum(e.arm=="FULL" for e in se);sbase=sum(e.arm=="BASELINE" for e in se)
    syms=sorted({e.symbol for e in ce});per={};retention=[]
    for s in syms:
        x=[e for e in ce if e.symbol==s];f=sum(e.arm=="FULL" for e in x);b=sum(e.arm=="BASELINE" for e in x);avail=sum(e.path_available[idx] for e in x)
        per[s]={"full":f,"baseline":b,"retention":avail/len(x) if x else 0};retention.append(per[s]["retention"])
    weeks=len({e.week_key for e in ce})
    passed=(cfull>=240 and cbase>=240 and all(v["full"]>=20 and v["baseline"]>=20 for v in per.values()) and sfull>=80 and sbase>=80 and weeks>=24 and len(blocks)>=12 and all(x>=.80 for x in retention))
    return {"pass":passed,"context_full":cfull,"context_baseline":cbase,"state_full":sfull,"state_baseline":sbase,"distinct_weeks":weeks,"paired_units":len(units),"valid_blocks":len(blocks),"per_symbol":per}


def _diagnostic_group_value(e: SignalEvent, diagnostic: str) -> str:
    if diagnostic=="UTC_HOUR_OF_TRIGGER":
        return f"{e.utc_hour:02d}"
    if diagnostic=="DAY_OF_WEEK":
        return e.day_of_week
    if diagnostic=="DETERMINISTIC_SESSION_LABEL":
        return e.session_label
    if diagnostic=="US_EQUITY_DST_REGIME":
        return e.dst_regime if e.context=="US_EQUITY_EXTENDED_HOURS" and e.dst_regime is not None else "NA"
    raise ValueError(diagnostic)


def _paired_leaf_metrics(events: Sequence[SignalEvent], norm: dict, raw: dict, context: str, state: str, horizon: int, min_symbols: int) -> dict:
    subset=[e for e in events if e.context==context and e.vol_state==state]
    units=construct_paired_units(subset,norm)
    units=[u for u in units if u.horizon==horizon]
    full_paired=paired_arm_hierarchical_mean(units,"FULL",min_symbols)
    base_paired=paired_arm_hierarchical_mean(units,"BASELINE",min_symbols)
    inc_sw=aggregate_direction_to_symbol_week(units)
    inc_cw=aggregate_symbol_to_context_week(inc_sw,min_symbols)
    incremental=float(np.mean(list(inc_cw.values()))) if inc_cw else None

    raw_units=construct_paired_units(subset,raw)
    raw_units=[u for u in raw_units if u.horizon==horizon]
    full_raw_paired=paired_arm_hierarchical_mean(raw_units,"FULL",min_symbols)
    base_raw_paired=paired_arm_hierarchical_mean(raw_units,"BASELINE",min_symbols)
    raw_sw=aggregate_direction_to_symbol_week(raw_units)
    raw_cw=aggregate_symbol_to_context_week(raw_sw,min_symbols)
    inc_raw=float(np.mean(list(raw_cw.values()))) if raw_cw else None
    return {
        "full_paired_hierarchical_normalized_mean":full_paired,
        "baseline_paired_hierarchical_normalized_mean":base_paired,
        "incremental_paired_hierarchical_normalized_mean":incremental,
        "full_paired_hierarchical_raw_bps_mean":full_raw_paired,
        "baseline_paired_hierarchical_raw_bps_mean":base_raw_paired,
        "incremental_paired_hierarchical_raw_bps_mean":inc_raw,
        "paired_units":len(units),
        "valid_context_weeks":len(inc_cw),
    }


def build_nonselection_diagnostics(events: Sequence[SignalEvent], norm: dict, raw: dict) -> dict:
    diagnostics={}
    for diagnostic in ("UTC_HOUR_OF_TRIGGER","DAY_OF_WEEK","DETERMINISTIC_SESSION_LABEL","US_EQUITY_DST_REGIME"):
        rows=[]
        groups=sorted({(e.context,_diagnostic_group_value(e,diagnostic)) for e in events})
        for context,group in groups:
            ge=[e for e in events if e.context==context and _diagnostic_group_value(e,diagnostic)==group]
            for state in VOL_STATES:
                for horizon in HORIZONS:
                    idx=HORIZONS.index(horizon)
                    ss=[e for e in ge if e.vol_state==state]
                    full_count=sum(e.arm=="FULL" and e.path_available[idx] for e in ss)
                    base_count=sum(e.arm=="BASELINE" and e.path_available[idx] for e in ss)
                    metrics=_paired_leaf_metrics(ge,norm,raw,context,state,horizon,1)
                    rows.append({
                        "context":context,"diagnostic_group":group,"vol_state":state,"horizon_m5":horizon,
                        "full_path_available_events":full_count,"baseline_path_available_events":base_count,
                        **metrics,
                    })
        diagnostics[diagnostic]={
            "classification":"NONSELECTION_ONLY",
            "may_change_lead_verdict":False,
            "weighting":"PAIR_WITHIN_GROUP;EQUAL_DIRECTIONS_WITHIN_SYMBOL_WEEK;EQUAL_SYMBOLS_WITHIN_CONTEXT_WEEK;MEAN_VALID_CONTEXT_WEEKS",
            "rows":rows,
        }
    return diagnostics


def _evaluate_prevalidated_development_core(
    *,
    authority: dict,
    design: dict,
    events: Sequence[SignalEvent],
    bars_by_symbol: dict[str,Sequence[M5Bar]],
    source_hashes: dict[str,str],
    permutations: int=DEFAULT_PERMUTATIONS,
    seed: int=DEFAULT_SEED,
    _execution_capability: object | None=None,
) -> dict:
    if _execution_capability is not _EXECUTION_CAPABILITY:
        raise PermissionError("direct prevalidated evaluator execution denied; authority-bound runner capability required")
    # Private-object possession alone is not authority. The immediate caller must be
    # the exact sibling runner frozen by Authority V3. This closes the trivial
    # module-global capability bypass while preserving synthetic helper tests.
    import inspect
    frame=inspect.currentframe();caller=frame.f_back if frame is not None else None
    expected=Path(__file__).resolve().with_name("development_execution_runner_v1.py")
    if caller is None or Path(caller.f_code.co_filename).resolve()!=expected:
        raise PermissionError("direct internal evaluator execution denied; exact authority-bound runner caller required")
    require_real_response_authority(authority)
    if permutations != DEFAULT_PERMUTATIONS or seed != DEFAULT_SEED:
        raise PermissionError("caller override of frozen seed/permutations is forbidden")

    norm={};raw={}
    for sym,bars in bars_by_symbol.items():
        n,r=_responses_for_events([e for e in events if e.symbol==sym],{b.time:b.close for b in bars})
        norm.update(n);raw.update(r)

    units=construct_paired_units(events,norm)
    family=[];contexts=[];leaf_order=[(s,h) for s in VOL_STATES for h in HORIZONS]
    for ci,cfg in enumerate(design["structural_contexts"]):
        ctx=cfg["id"];leaves=[];metrics=[]
        for state,h in leaf_order:
            lu,sw,cw,ids,blocks,smeans,wmeans=_leaf_aggregates(units,ctx,state,h,DEV_BLOCK_ANCHOR,4)
            sup=_development_support_leaf(events,ctx,state,h,lu,blocks)
            leaves.append((ids,blocks) if sup["pass"] else (np.array([],int),np.array([],float)))
            paired_full=paired_arm_hierarchical_mean(lu,"FULL",4)
            paired_base=paired_arm_hierarchical_mean(lu,"BASELINE",4)
            full_raw=[raw[(e.symbol,e.trigger_time,h)] for e in events if e.context==ctx and e.vol_state==state and e.arm=="FULL" and (e.symbol,e.trigger_time,h) in raw]
            base_raw=[raw[(e.symbol,e.trigger_time,h)] for e in events if e.context==ctx and e.vol_state==state and e.arm=="BASELINE" and (e.symbol,e.trigger_time,h) in raw]
            metrics.append({
                "state":state,"horizon_m5":h,"support":sup,"blocks":blocks.tolist(),"block_ids":ids.tolist(),
                "incremental_mean":float(np.mean(blocks)) if len(blocks) else None,
                "symbol_means":smeans,"week_means":wmeans,
                "full_arm_paired_hierarchical_normalized_mean":paired_full,
                "baseline_arm_paired_hierarchical_normalized_mean":paired_base,
                "full_raw_bps_mean_event_weighted_secondary":float(np.mean(full_raw)) if full_raw else None,
                "baseline_raw_bps_mean_event_weighted_secondary":float(np.mean(base_raw)) if base_raw else None,
            })
        test=local_shared_maxT(leaves,permutations,seed+ci,leaf_order)
        family.append(test["family_p"])
        contexts.append({"context":ctx,"local_test":test,"leaves":metrics})

    rejects=holm_reject(family,.05)
    for ci,cx in enumerate(contexts):
        j=cx["local_test"]["selected_index"];m=cx["leaves"][j]
        m["holm_context_reject"]=rejects[ci]
        m["temporal_pass"]=development_quarter_gate({int(k):v for k,v in m["week_means"].items()},3)
        m["breadth_pass"]=breadth_gate(m["symbol_means"],3)
        m["concentration_pass"]=concentration_gate(m["symbol_means"],.50)
        m["full_arm_positive"]=m["full_arm_paired_hierarchical_normalized_mean"] is not None and m["full_arm_paired_hierarchical_normalized_mean"]>0
        cx["development_lead_pass"]=bool(
            m["support"]["pass"] and rejects[ci] and
            m["incremental_mean"] is not None and m["incremental_mean"]>0 and
            m["temporal_pass"] and m["breadth_pass"] and m["concentration_pass"] and m["full_arm_positive"]
        )

    diagnostics=build_nonselection_diagnostics(events,norm,raw)
    return {
        "schema":"mxm.research-core-v4.development-response-result.v2",
        "design":"FIRST_REAL_MARKET_DESIGN_V2",
        "source_hashes":source_hashes,
        "support_skeleton_sha256":skeleton_sha256(events),
        "event_count":len(events),
        "response_value_count":len(norm),
        "family_pvalues":family,
        "holm_reject":rejects,
        "contexts":contexts,
        "nonselection_diagnostics":diagnostics,
        "nonselection_diagnostics_rule":"EXPLANATION_ONLY_NEVER_CHANGES_DEVELOPMENT_LEAD_VERDICT",
        "seed":seed,
        "permutations":permutations,
        "protected_forward_opened":False,
    }


def evaluate_prevalidated_development(*args, **kwargs):
    raise PermissionError("Direct prevalidated real-response execution is disabled. Use the authority-bound development_execution_runner_v1.py.")

def evaluate_development_from_directory(*args,**kwargs):
    raise PermissionError("Direct real-response directory execution is disabled. Use the authority-bound development_execution_runner_v1.py.")

if __name__ == "__main__":
    main()
