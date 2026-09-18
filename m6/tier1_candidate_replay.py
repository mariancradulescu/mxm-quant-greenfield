"""Pre-economic deterministic Tier-1 candidate replay for C006/C012.

This module produces signal/entry/exit intents only. It deliberately does not compute PnL,
cost-adjusted returns, outcome status, attempt accounting, or ledger results.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import sqrt
from typing import Any, Mapping, Sequence

from .session_replay import NasdaqCashCalendar, observed_cash_bars, synchronized_observed_cash_bars

C006_HASH="75b5cc238ed6be20e9b36201068143fa20e3c418ddb26fe7835af61039efcc49"
C012_HASH="3be7fad78760ec4f37cf1473bcf2cc9696d591fad01290f2a8812e37865f9845"


def _utc(value:Any)->datetime:
    text=str(value)
    if text.endswith("Z"):
        text=text[:-1]+"+00:00"
    dt=datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _f(row:Mapping[str,Any],key:str)->float:
    return float(row[key])


@dataclass(frozen=True)
class ReplayIntent:
    candidate_id:str
    spec_hash:str
    direction:str
    decision_utc:datetime
    entry_utc:datetime
    entry_price:float
    exit_utc:datetime
    exit_price:float
    evidence:dict[str,float|str]


def _session_groups(rows:Sequence[Mapping[str,Any]],calendar:NasdaqCashCalendar):
    bars=observed_cash_bars(rows,calendar,bar_minutes=15)
    groups=[]
    current_day=None
    current=[]
    from zoneinfo import ZoneInfo
    market_tz=ZoneInfo("America/New_York")
    for row in bars:
        # Group by authoritative local market date without inventing missing bars.
        local_day=_utc(row["time_utc"]).astimezone(market_tz).date()
        if current_day is None or local_day==current_day:
            current_day=local_day
            current.append(row)
        else:
            groups.append((current_day,current))
            current_day=local_day
            current=[row]
    if current:
        groups.append((current_day,current))
    return groups


def _cash_session_stats(groups):
    stats=[]
    prev_close=None
    for day,bars in groups:
        if not bars:
            continue
        opened=_f(bars[0],"open")
        high=max(_f(x,"high") for x in bars)
        low=min(_f(x,"low") for x in bars)
        close=_f(bars[-1],"close")
        tr=None
        tr_pct=None
        if prev_close is not None and prev_close>0:
            tr=max(high-low,abs(high-prev_close),abs(low-prev_close))
            tr_pct=tr/prev_close
        stats.append({
            "day":day,"bars":bars,"open":opened,"high":high,"low":low,"close":close,
            "prior_close":prev_close,"true_range":tr,"true_range_pct":tr_pct,
        })
        prev_close=close
    return stats


def c006_replay_intents(
    us500_rows:Sequence[Mapping[str,Any]],
    calendar:NasdaqCashCalendar,
)->list[ReplayIntent]:
    groups=_session_groups(us500_rows,calendar)
    stats=_cash_session_stats(groups)
    out=[]
    for i,current in enumerate(stats):
        if i<21 or current["prior_close"] is None:
            continue
        prior=stats[i-20:i]
        trp=[x["true_range_pct"] for x in prior]
        if len(trp)!=20 or any(x is None for x in trp):
            continue
        atr20=sum(float(x) for x in trp)/20.0
        if atr20<=0:
            continue
        gap=current["open"]/current["prior_close"]-1.0
        ratio=gap/atr20
        if ratio<=-0.75:
            direction="LONG"
        elif ratio>=0.75:
            direction="SHORT"
        else:
            continue
        bars=current["bars"]
        # Decision is the completion of the first observed cash-session M15 bar.
        decision=_utc(bars[0]["time_utc"])+timedelta(minutes=15)
        # The next bar is the first later executable EVENT. Its OPEN event follows the
        # previous bar CLOSE event at the same boundary timestamp; bar-index ordering,
        # not a later timestamp, preserves the standard next-bar-open causal convention.
        if len(bars)<13:
            continue
        entry_bar=bars[1]
        entry_time=_utc(entry_bar["time_utc"])
        if entry_time!=decision:
            # A real missing bar means there is no synthetic 09:45 entry. Use the first
            # actually observed later bar, but it must occur after the decision boundary.
            if entry_time<decision:
                raise ValueError("entry event precedes decision")
        # 12 executable M15 bars including entry => entry index 1 through index 12.
        exit_bar=bars[12]
        out.append(ReplayIntent(
            candidate_id="V2-C006",spec_hash=C006_HASH,direction=direction,
            decision_utc=decision,entry_utc=entry_time,entry_price=_f(entry_bar,"open"),
            exit_utc=_utc(exit_bar["time_utc"])+timedelta(minutes=15),
            exit_price=_f(exit_bar,"close"),
            evidence={"overnight_gap_pct":gap,"prior_atr20_pct":atr20,"gap_atr_ratio":ratio},
        ))
    return out


def _sample_std(values:Sequence[float])->float:
    if len(values)<2:
        return 0.0
    mean=sum(values)/len(values)
    ss=sum((x-mean)**2 for x in values)
    return sqrt(ss/(len(values)-1))


def c012_replay_intents(
    us500_rows:Sequence[Mapping[str,Any]],
    nas100_rows:Sequence[Mapping[str,Any]],
    calendar:NasdaqCashCalendar,
)->list[ReplayIntent]:
    pairs=synchronized_observed_cash_bars(us500_rows,nas100_rows,calendar,bar_minutes=15)
    if not pairs:
        return []
    leader_ret2=[]
    lagger_ret2=[]
    out=[]
    active_until_index=-1
    for i,(leader,lagger) in enumerate(pairs):
        if i<2:
            leader_ret2.append(float("nan")); lagger_ret2.append(float("nan"))
            continue
        lr=_f(leader,"close")/_f(pairs[i-2][0],"close")-1.0
        rr=_f(lagger,"close")/_f(pairs[i-2][1],"close")-1.0
        leader_ret2.append(lr); lagger_ret2.append(rr)
        valid_l=[x for x in leader_ret2[max(2,i-519):i+1] if x==x]
        valid_r=[x for x in lagger_ret2[max(2,i-519):i+1] if x==x]
        if len(valid_l)<520 or len(valid_r)<520:
            continue
        lstd=_sample_std(valid_l[-520:]); rstd=_sample_std(valid_r[-520:])
        if lstd<=0 or rstd<=0:
            continue
        lz=lr/lstd; rz=rr/rstd
        if i<=active_until_index:
            continue
        direction=None
        if lz>=1.5 and rz<=0.5:
            direction="LONG_NAS100"
        elif lz<=-1.5 and rz>=-0.5:
            direction="SHORT_NAS100"
        if direction is None:
            continue
        entry_index=i+1
        exit_index=entry_index+3
        if exit_index>=len(pairs):
            continue
        decision=_utc(lagger["time_utc"])+timedelta(minutes=15)
        entry_lagger=pairs[entry_index][1]
        exit_lagger=pairs[exit_index][1]
        entry_time=_utc(entry_lagger["time_utc"])
        if entry_time<decision:
            raise ValueError("C012 entry event precedes decision")
        out.append(ReplayIntent(
            candidate_id="V2-C012",spec_hash=C012_HASH,direction=direction,
            decision_utc=decision,entry_utc=entry_time,entry_price=_f(entry_lagger,"open"),
            exit_utc=_utc(exit_lagger["time_utc"])+timedelta(minutes=15),
            exit_price=_f(exit_lagger,"close"),
            evidence={"leader_ret2":lr,"lagger_ret2":rr,"leader_z":lz,"lagger_z":rz},
        ))
        active_until_index=exit_index
    return out
