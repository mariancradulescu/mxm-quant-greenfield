"""Literal Stage-A cash-session/event replay primitives.

The official Nasdaq reference calendar defines the decision domain. Accepted broker
observations define actual availability. Calendar membership never fabricates a bar.

C006 additionally requires exact session-boundary observations and a complete expected
M15 grid for any session used in its ATR20 state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
import json
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
M15 = timedelta(minutes=15)


@dataclass(frozen=True)
class CashSession:
    session_date: date
    open_utc: datetime
    close_utc: datetime
    early_close: bool

    @property
    def expected_m15_count(self) -> int:
        return int((self.close_utc - self.open_utc) / M15)

    @property
    def final_m15_open_utc(self) -> datetime:
        return self.close_utc - M15


@dataclass(frozen=True)
class CashSessionObservation:
    session: CashSession
    expected_opens: tuple[datetime, ...]
    bars_by_open: Mapping[datetime, Mapping[str, Any]]

    @property
    def exact_open_bar(self) -> Mapping[str, Any] | None:
        return self.bars_by_open.get(self.session.open_utc)

    @property
    def exact_final_bar(self) -> Mapping[str, Any] | None:
        return self.bars_by_open.get(self.session.final_m15_open_utc)

    @property
    def exact_close_price(self) -> float | None:
        bar = self.exact_final_bar
        return None if bar is None else float(bar["close"])

    @property
    def complete_grid(self) -> bool:
        return all(stamp in self.bars_by_open for stamp in self.expected_opens)

    @property
    def observed_expected_count(self) -> int:
        return sum(stamp in self.bars_by_open for stamp in self.expected_opens)

    def ordered_expected_bars(self) -> list[Mapping[str, Any]]:
        return [self.bars_by_open[x] for x in self.expected_opens if x in self.bars_by_open]


class NasdaqCashCalendar:
    def __init__(self, closures: Iterable[str], early_closes: Iterable[str]):
        self.closures = {date.fromisoformat(x) for x in closures}
        self.early_closes = {date.fromisoformat(x) for x in early_closes}
        if self.closures & self.early_closes:
            raise ValueError("calendar date cannot be both closed and early-close")

    @classmethod
    def from_artifact(cls, path: Path | str):
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(value["closures"], value["early_closes"])

    def session(self, day: date) -> CashSession | None:
        if day.weekday() >= 5 or day in self.closures:
            return None
        close = dtime(13, 0) if day in self.early_closes else dtime(16, 0)
        opened = datetime.combine(day, dtime(9, 30), NY).astimezone(timezone.utc)
        closed = datetime.combine(day, close, NY).astimezone(timezone.utc)
        return CashSession(day, opened, closed, day in self.early_closes)

    def previous_session(self, day: date) -> CashSession | None:
        cursor = day - timedelta(days=1)
        for _ in range(14):
            session = self.session(cursor)
            if session is not None:
                return session
            cursor -= timedelta(days=1)
        return None

    def expected_m15_opens(self, day: date) -> tuple[datetime, ...]:
        session = self.session(day)
        if session is None:
            return ()
        out = []
        cursor = session.open_utc
        while cursor < session.close_utc:
            out.append(cursor)
            cursor += M15
        if len(out) != session.expected_m15_count:
            raise AssertionError("cash-session M15 grid construction mismatch")
        if session.early_close and len(out) != 14:
            raise AssertionError("early-close session must contain 14 expected M15 bars")
        if not session.early_close and len(out) != 26:
            raise AssertionError("regular session must contain 26 expected M15 bars")
        return tuple(out)

    def contains_bar_open(self, opened: datetime, bar_minutes: int = 15) -> bool:
        opened = opened.astimezone(timezone.utc)
        local_day = opened.astimezone(NY).date()
        session = self.session(local_day)
        if session is None:
            return False
        completed = opened + timedelta(minutes=bar_minutes)
        return opened >= session.open_utc and completed <= session.close_utc


def _parse_utc(value: Any) -> datetime:
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("broker event timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def observed_cash_bars(
    rows: Sequence[Mapping[str, Any]],
    calendar: NasdaqCashCalendar,
    *,
    bar_minutes: int = 15,
) -> list[Mapping[str, Any]]:
    """Filter only existing observations into known cash sessions; never synthesize."""
    out = []
    last = None
    for row in rows:
        opened = _parse_utc(row["time_utc"])
        if last is not None and opened <= last:
            raise ValueError("broker bars must be strictly chronological")
        last = opened
        if calendar.contains_bar_open(opened, bar_minutes):
            out.append(row)
    return out


def cash_session_observations(
    rows: Sequence[Mapping[str, Any]],
    calendar: NasdaqCashCalendar,
) -> dict[date, CashSessionObservation]:
    """Return exact expected-grid observations for each scheduled session touched by rows.

    Off-grid observations are never promoted into expected M15 slots.
    """
    filtered = observed_cash_bars(rows, calendar, bar_minutes=15)
    by_day: dict[date, dict[datetime, Mapping[str, Any]]] = {}
    for row in filtered:
        opened = _parse_utc(row["time_utc"])
        day = opened.astimezone(NY).date()
        expected = set(calendar.expected_m15_opens(day))
        if opened in expected:
            by_day.setdefault(day, {})[opened] = row

    if not rows:
        return {}
    all_times = [_parse_utc(row["time_utc"]) for row in rows]
    start_day = min(all_times).astimezone(NY).date()
    end_day = max(all_times).astimezone(NY).date()
    out: dict[date, CashSessionObservation] = {}
    cursor = start_day
    while cursor <= end_day:
        session = calendar.session(cursor)
        if session is not None:
            out[cursor] = CashSessionObservation(
                session=session,
                expected_opens=calendar.expected_m15_opens(cursor),
                bars_by_open=by_day.get(cursor, {}),
            )
        cursor += timedelta(days=1)
    return out


def exact_session_open_bar(
    observations: Mapping[date, CashSessionObservation],
    day: date,
) -> Mapping[str, Any] | None:
    obs = observations.get(day)
    return None if obs is None else obs.exact_open_bar


def exact_session_close_price(
    observations: Mapping[date, CashSessionObservation],
    day: date,
) -> float | None:
    obs = observations.get(day)
    return None if obs is None else obs.exact_close_price


def full_session_true_range_pct(
    observations: Mapping[date, CashSessionObservation],
    calendar: NasdaqCashCalendar,
    day: date,
) -> float | None:
    """C006 true-range contribution for one fully observed cash session.

    The session itself must have the entire official M15 grid. The immediately preceding
    scheduled cash session must expose its exact final M15 close. An incomplete session
    or unavailable prior close is not silently substituted by another observed bar.
    """
    obs = observations.get(day)
    if obs is None or not obs.complete_grid:
        return None
    prior = calendar.previous_session(day)
    if prior is None:
        return None
    prior_close = exact_session_close_price(observations, prior.session_date)
    if prior_close is None or prior_close <= 0:
        return None
    bars = obs.ordered_expected_bars()
    high = max(float(x["high"]) for x in bars)
    low = min(float(x["low"]) for x in bars)
    tr = max(high - low, abs(high - prior_close), abs(low - prior_close))
    return tr / prior_close


def prior_valid_true_ranges(
    observations: Mapping[date, CashSessionObservation],
    calendar: NasdaqCashCalendar,
    before_day: date,
    *,
    count: int = 20,
) -> list[float]:
    """Look backward for exactly count valid completed C006 session TR contributions."""
    values: list[float] = []
    cursor_session = calendar.previous_session(before_day)
    oldest = min(observations) if observations else before_day
    while cursor_session is not None and len(values) < count:
        value = full_session_true_range_pct(
            observations, calendar, cursor_session.session_date
        )
        if value is not None:
            values.append(value)
        cursor_session = calendar.previous_session(cursor_session.session_date)
        if cursor_session is not None and cursor_session.session_date < oldest:
            break
    values.reverse()
    return values


def synchronized_observed_cash_bars(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
    calendar: NasdaqCashCalendar,
    *,
    bar_minutes: int = 15,
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Strict same-observed-timestamp intersection inside the reference session."""
    l = observed_cash_bars(left, calendar, bar_minutes=bar_minutes)
    r = observed_cash_bars(right, calendar, bar_minutes=bar_minutes)
    by_r = {_parse_utc(x["time_utc"]): x for x in r}
    out = []
    for a in l:
        stamp = _parse_utc(a["time_utc"])
        b = by_r.get(stamp)
        if b is not None:
            out.append((a, b))
    return out


def first_later_observed_open(
    rows: Sequence[Mapping[str, Any]],
    decision_timestamp: Any,
) -> Mapping[str, Any] | None:
    decision = _parse_utc(decision_timestamp)
    for row in rows:
        if _parse_utc(row["time_utc"]) > decision:
            return row
    return None


def first_completed_cash_bar_by_session(
    rows: Sequence[Mapping[str, Any]],
    calendar: NasdaqCashCalendar,
    *,
    bar_minutes: int = 15,
) -> dict[str, Mapping[str, Any]]:
    filtered = observed_cash_bars(rows, calendar, bar_minutes=bar_minutes)
    out = {}
    for row in filtered:
        opened = _parse_utc(row["time_utc"])
        key = opened.astimezone(NY).date().isoformat()
        out.setdefault(key, row)
    return out
