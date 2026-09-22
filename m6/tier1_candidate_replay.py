"""Pre-economic deterministic Tier-1 candidate replay for C006/C012.

This module produces signal/entry/exit intents only. It deliberately does not compute PnL,
cost-adjusted returns, outcome status, attempt accounting, or ledger results.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import sqrt
from typing import Any, Mapping, Sequence

from .session_replay import (
    NY,
    NasdaqCashCalendar,
    cash_session_observations,
    exact_session_close_price,
    prior_valid_true_ranges,
    synchronized_observed_cash_bars,
)

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


def c006_replay_intents(
    us500_rows: Sequence[Mapping[str, Any]],
    calendar: NasdaqCashCalendar,
) -> list[ReplayIntent]:
    """Replay frozen C006 only when exact cash-session state is causally knowable.

    Current signal session:
      * exact scheduled 09:30 ET M15 bar must exist;
      * decision is exactly that bar's 09:45 completion.

    Prior close:
      * immediately preceding scheduled cash session must expose its exact final M15 bar
        (15:45 regular / 12:45 early close).

    ATR20:
      * each contributing historical session must have the full official expected M15 grid
        (26 regular / 14 early close);
      * its own immediately preceding scheduled-session exact close must exist;
      * incomplete sessions are skipped and the scan may look farther back for 20 valid
        completed session true-range contributions.
    """
    observations = cash_session_observations(us500_rows, calendar)
    out: list[ReplayIntent] = []
    for day in sorted(observations):
        current = observations[day]
        open_bar = current.exact_open_bar
        if open_bar is None:
            # First observed bar may never substitute for the scheduled cash-session open.
            continue

        prior_session = calendar.previous_session(day)
        if prior_session is None:
            continue
        prior_close = exact_session_close_price(
            observations, prior_session.session_date
        )
        if prior_close is None or prior_close <= 0:
            # Last observed bar may never substitute for the exact scheduled close.
            continue

        trp = prior_valid_true_ranges(
            observations, calendar, day, count=20
        )
        if len(trp) != 20:
            continue
        atr20 = sum(trp) / 20.0
        if atr20 <= 0:
            continue

        cash_open = _f(open_bar, "open")
        gap = cash_open / prior_close - 1.0
        ratio = gap / atr20
        if ratio <= -0.75:
            direction = "LONG"
        elif ratio >= 0.75:
            direction = "SHORT"
        else:
            continue

        decision = current.session.open_utc + timedelta(minutes=15)
        observed = current.ordered_expected_bars()
        executable = [
            row for row in observed
            if _utc(row["time_utc"]) >= decision
        ]
        if len(executable) < 12:
            continue
        entry_bar = executable[0]
        entry_time = _utc(entry_bar["time_utc"])
        if entry_time < decision:
            raise ValueError("C006 entry event precedes frozen 09:45 decision")
        exit_bar = executable[11]
        exit_time = _utc(exit_bar["time_utc"]) + timedelta(minutes=15)
        if exit_time > current.session.close_utc:
            continue

        out.append(ReplayIntent(
            candidate_id="V2-C006",
            spec_hash=C006_HASH,
            direction=direction,
            decision_utc=decision,
            entry_utc=entry_time,
            entry_price=_f(entry_bar, "open"),
            exit_utc=exit_time,
            exit_price=_f(exit_bar, "close"),
            evidence={
                "overnight_gap_pct": gap,
                "prior_atr20_pct": atr20,
                "gap_atr_ratio": ratio,
                "cash_session_open_utc": current.session.open_utc.isoformat(),
                "prior_cash_session_close_utc": prior_session.close_utc.isoformat(),
                "prior_cash_session_close": prior_close,
                "atr20_valid_completed_sessions": "20",
            },
        ))
    return out


def _sample_std(values:Sequence[float])->float:
    if len(values)<2:
        return 0.0
    mean=sum(values)/len(values)
    ss=sum((x-mean)**2 for x in values)
    return sqrt(ss/(len(values)-1))


def _prior_finite_window(values:Sequence[float], current_index:int, count:int)->list[float]:
    """Return exactly prior finite observations; never include the current observation."""
    start=max(0,current_index-count)
    return [x for x in values[start:current_index] if x==x]


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
        # Frozen C012 semantics require the rolling normalization state to use only
        # PRIOR synchronized completed returns. The current return_t is the numerator
        # and must not leak into its own 520-observation scale estimate.
        valid_l=_prior_finite_window(leader_ret2,i,520)
        valid_r=_prior_finite_window(lagger_ret2,i,520)
        if len(valid_l)<520 or len(valid_r)<520:
            continue
        lstd=_sample_std(valid_l); rstd=_sample_std(valid_r)
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
