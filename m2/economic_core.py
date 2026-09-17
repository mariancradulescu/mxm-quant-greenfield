"""Minimal deterministic economic core for M2 synthetic fixtures only.

This module is deliberately not a discovery engine or strategy engine.  Every
cost/session input used here is fixture-supplied and therefore does not assert
real Pepperstone historical truth.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
from typing import Iterable, Optional, Sequence

D = Decimal


@dataclass(frozen=True)
class Bar:
    index: int
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    session_open: bool = True


@dataclass(frozen=True)
class Event:
    timestamp: datetime
    kind: str
    sequence: int = 0


@dataclass(frozen=True)
class TradeSettlement:
    entry_fill: Decimal
    exit_fill: Decimal
    mid_gross_quote: Decimal
    spread_cost_quote: Decimal
    commission_quote: Decimal
    swap_quote: Decimal
    net_quote: Decimal
    net_account: Decimal
    swap_boundaries: int


_EVENT_PRIORITY = {
    "BROKER_STATE": 0,
    "BAR_CLOSE": 10,
    "EXIT": 20,
    "DECISION": 30,
    "ENTRY": 40,
}


def completed_bar_index(bars: Sequence[Bar], decision_time: datetime) -> Optional[int]:
    """Return the latest bar index whose close is available at decision_time."""
    eligible = [bar.index for bar in bars if bar.close_time <= decision_time]
    return max(eligible) if eligible else None


def decision_time_for_bar(bar: Bar) -> datetime:
    """M2 convention: a completed-bar decision is timestamped at bar close."""
    return bar.close_time


def next_valid_entry_index(bars: Sequence[Bar], decision_bar_index: int) -> Optional[int]:
    """First later listed bar that is executable; no missing bars are fabricated."""
    for bar in bars:
        if bar.index > decision_bar_index and bar.session_open:
            return bar.index
    return None


def normalize_volume(requested: Decimal, minimum: Decimal, step: Decimal, maximum: Optional[Decimal] = None) -> Optional[Decimal]:
    """Floor requested volume to the explicit synthetic step; reject below min."""
    if requested < 0 or minimum <= 0 or step <= 0:
        raise ValueError("requested must be nonnegative and minimum/step positive")
    normalized = (requested / step).to_integral_value(rounding=ROUND_FLOOR) * step
    if maximum is not None:
        normalized = min(normalized, maximum)
        normalized = (normalized / step).to_integral_value(rounding=ROUND_FLOOR) * step
    if normalized < minimum:
        return None
    return normalized


def execution_prices(direction: str, entry_mid: Decimal, exit_mid: Decimal, spread: Decimal):
    """Apply a symmetric explicit synthetic spread around mid at both sides."""
    if spread < 0:
        raise ValueError("spread must be nonnegative")
    half = spread / D("2")
    if direction == "LONG":
        return entry_mid + half, exit_mid - half
    if direction == "SHORT":
        return entry_mid - half, exit_mid + half
    raise ValueError("direction must be LONG or SHORT")


def swap_boundary_count(entry_time: datetime, exit_time: datetime, rollover_times: Iterable[datetime]) -> int:
    """Synthetic boundary rule: charge boundaries with entry < boundary <= exit."""
    if exit_time < entry_time:
        raise ValueError("exit precedes entry")
    return sum(entry_time < t <= exit_time for t in rollover_times)


def convert_quote_to_account(amount_quote: Decimal, quote_to_account_rate: Decimal) -> Decimal:
    if quote_to_account_rate <= 0:
        raise ValueError("conversion rate must be positive")
    return amount_quote * quote_to_account_rate


def settle_round_trip(
    *,
    direction: str,
    volume: Decimal,
    entry_mid: Decimal,
    exit_mid: Decimal,
    spread: Decimal,
    commission_per_unit_per_side_quote: Decimal,
    contract_multiplier: Decimal,
    entry_time: datetime,
    exit_time: datetime,
    rollover_times: Iterable[datetime],
    swap_per_unit_per_boundary_quote: Decimal,
    quote_to_account_rate: Decimal,
) -> TradeSettlement:
    if volume <= 0 or contract_multiplier <= 0:
        raise ValueError("volume and contract_multiplier must be positive")
    sign = D("1") if direction == "LONG" else D("-1") if direction == "SHORT" else None
    if sign is None:
        raise ValueError("direction must be LONG or SHORT")

    entry_fill, exit_fill = execution_prices(direction, entry_mid, exit_mid, spread)
    mid_gross = sign * (exit_mid - entry_mid) * volume * contract_multiplier
    fill_gross = sign * (exit_fill - entry_fill) * volume * contract_multiplier
    spread_cost = mid_gross - fill_gross
    commission = D("2") * volume * commission_per_unit_per_side_quote
    boundaries = swap_boundary_count(entry_time, exit_time, rollover_times)
    swap = D(boundaries) * volume * swap_per_unit_per_boundary_quote
    net_quote = fill_gross - commission + swap
    net_account = convert_quote_to_account(net_quote, quote_to_account_rate)

    return TradeSettlement(
        entry_fill=entry_fill,
        exit_fill=exit_fill,
        mid_gross_quote=mid_gross,
        spread_cost_quote=spread_cost,
        commission_quote=commission,
        swap_quote=swap,
        net_quote=net_quote,
        net_account=net_account,
        swap_boundaries=boundaries,
    )


def hold_exit_index(bars: Sequence[Bar], entry_index: int, maximum_hold_bars: int) -> Optional[int]:
    """Exit at the close of the Nth executable listed bar including entry bar."""
    if maximum_hold_bars <= 0:
        raise ValueError("maximum_hold_bars must be positive")
    held = 0
    seen_entry = False
    for bar in bars:
        if bar.index == entry_index:
            seen_entry = True
        if not seen_entry:
            continue
        if bar.session_open:
            held += 1
            if held == maximum_hold_bars:
                return bar.index
    return None


def order_events(events: Iterable[Event]):
    """Stable deterministic same-timestamp ordering for synthetic replay fixtures."""
    unknown = sorted({event.kind for event in events if event.kind not in _EVENT_PRIORITY})
    if unknown:
        raise ValueError(f"Unknown event kinds: {unknown}")
    return sorted(events, key=lambda event: (event.timestamp, _EVENT_PRIORITY[event.kind], event.sequence))
