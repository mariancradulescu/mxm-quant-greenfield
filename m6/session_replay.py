"""Literal Stage-A cash-session/event replay primitives.

The exchange calendar defines the candidate decision domain. Broker observations define
actual availability. Calendar membership never fabricates a broker bar/event.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
import json
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

NY=ZoneInfo("America/New_York")


@dataclass(frozen=True)
class CashSession:
    session_date: date
    open_utc: datetime
    close_utc: datetime
    early_close: bool


class NasdaqCashCalendar:
    def __init__(self, closures: Iterable[str], early_closes: Iterable[str]):
        self.closures={date.fromisoformat(x) for x in closures}
        self.early_closes={date.fromisoformat(x) for x in early_closes}
        if self.closures & self.early_closes:
            raise ValueError("calendar date cannot be both closed and early-close")

    @classmethod
    def from_artifact(cls,path:Path|str):
        value=json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(value["closures"],value["early_closes"])

    def session(self,day:date)->CashSession|None:
        if day.weekday()>=5 or day in self.closures:
            return None
        close=dtime(13,0) if day in self.early_closes else dtime(16,0)
        opened=datetime.combine(day,dtime(9,30),NY).astimezone(timezone.utc)
        closed=datetime.combine(day,close,NY).astimezone(timezone.utc)
        return CashSession(day,opened,closed,day in self.early_closes)

    def contains_bar_open(self,opened:datetime,bar_minutes:int=15)->bool:
        opened=opened.astimezone(timezone.utc)
        local_day=opened.astimezone(NY).date()
        session=self.session(local_day)
        if session is None:
            return False
        completed=opened+timedelta(minutes=bar_minutes)
        return opened>=session.open_utc and completed<=session.close_utc


def _parse_utc(value:Any)->datetime:
    text=str(value)
    if text.endswith("Z"):
        text=text[:-1]+"+00:00"
    dt=datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("broker event timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def observed_cash_bars(
    rows:Sequence[Mapping[str,Any]],
    calendar:NasdaqCashCalendar,
    *,
    bar_minutes:int=15,
)->list[Mapping[str,Any]]:
    """Filter only existing observations into known cash sessions; never synthesize."""
    out=[]
    last=None
    for row in rows:
        opened=_parse_utc(row["time_utc"])
        if last is not None and opened<=last:
            raise ValueError("broker bars must be strictly chronological")
        last=opened
        if calendar.contains_bar_open(opened,bar_minutes):
            out.append(row)
    return out


def synchronized_observed_cash_bars(
    left:Sequence[Mapping[str,Any]],
    right:Sequence[Mapping[str,Any]],
    calendar:NasdaqCashCalendar,
    *,
    bar_minutes:int=15,
)->list[tuple[Mapping[str,Any],Mapping[str,Any]]]:
    """Strict same-observed-timestamp intersection inside the reference session."""
    l=observed_cash_bars(left,calendar,bar_minutes=bar_minutes)
    r=observed_cash_bars(right,calendar,bar_minutes=bar_minutes)
    by_r={_parse_utc(x["time_utc"]):x for x in r}
    out=[]
    for a in l:
        stamp=_parse_utc(a["time_utc"])
        b=by_r.get(stamp)
        if b is not None:
            out.append((a,b))
    return out


def first_later_observed_open(
    rows:Sequence[Mapping[str,Any]],
    decision_timestamp:Any,
)->Mapping[str,Any]|None:
    decision=_parse_utc(decision_timestamp)
    for row in rows:
        if _parse_utc(row["time_utc"])>decision:
            return row
    return None


def first_completed_cash_bar_by_session(
    rows:Sequence[Mapping[str,Any]],
    calendar:NasdaqCashCalendar,
    *,
    bar_minutes:int=15,
)->dict[str,Mapping[str,Any]]:
    filtered=observed_cash_bars(rows,calendar,bar_minutes=bar_minutes)
    out={}
    for row in filtered:
        opened=_parse_utc(row["time_utc"])
        key=opened.astimezone(NY).date().isoformat()
        out.setdefault(key,row)
    return out
