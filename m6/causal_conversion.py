"""Deterministic causal quote-currency -> EUR conversion for V2 Discovery.

The frozen data requirements explicitly permit a causal conversion series OR broker-native
conversion evidence. This adapter uses the accepted hash-bound M15 EURUSD/EURJPY series.

A conversion observation is available only after its M15 bar is completed. At cashflow
timestamp T, the adapter may use only the latest completed observation whose completion
timestamp is <= T. Future interpolation and backfill from later observations are forbidden.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Any, Iterable, Mapping, Sequence

M15 = timedelta(minutes=15)


class MissingCausalConversion(ValueError):
    pass


def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class ConversionObservation:
    symbol: str
    bar_open_utc: datetime
    completed_utc: datetime
    close_price: float


@dataclass(frozen=True)
class ConversionResult:
    source_currency: str
    target_currency: str
    amount_source: float
    amount_eur: float
    source_symbol: str | None
    quote_to_eur_rate: float
    source_bar_open_utc: datetime | None
    source_completed_utc: datetime | None
    source_price: float | None
    causal_rule: str


class CausalConversionSeries:
    def __init__(self, symbol: str, observations: Sequence[ConversionObservation]):
        if not observations:
            raise ValueError(f"{symbol}: conversion series is empty")
        ordered = sorted(observations, key=lambda x: x.bar_open_utc)
        last_open = None
        for obs in ordered:
            if obs.symbol != symbol:
                raise ValueError("conversion observation symbol mismatch")
            if obs.completed_utc != obs.bar_open_utc + M15:
                raise ValueError("conversion observations must be completed M15 bars")
            if last_open is not None and obs.bar_open_utc <= last_open:
                raise ValueError("conversion bar timestamps must be strictly increasing")
            if not math.isfinite(obs.close_price) or obs.close_price <= 0:
                raise ValueError("conversion close must be positive and finite")
            last_open = obs.bar_open_utc
        self.symbol = symbol
        self._observations = tuple(ordered)
        self._completion_times = tuple(x.completed_utc for x in ordered)

    @classmethod
    def from_rows(cls, symbol: str, rows: Iterable[Mapping[str, Any]]):
        observations = []
        for row in rows:
            opened = _utc(row["time_utc"])
            observations.append(
                ConversionObservation(
                    symbol=symbol,
                    bar_open_utc=opened,
                    completed_utc=opened + M15,
                    close_price=float(row["close"]),
                )
            )
        return cls(symbol, observations)

    def latest_completed_at_or_before(self, cashflow_timestamp: Any) -> ConversionObservation:
        target = _utc(cashflow_timestamp)
        idx = bisect_right(self._completion_times, target) - 1
        if idx < 0:
            raise MissingCausalConversion(
                f"{self.symbol}: no completed causal M15 observation at or before {target.isoformat()}"
            )
        obs = self._observations[idx]
        if obs.completed_utc > target:
            raise AssertionError("future conversion observation selected")
        return obs


def quote_to_eur_rate(
    source_currency: str,
    cashflow_timestamp: Any,
    *,
    eurusd: CausalConversionSeries | None = None,
    eurjpy: CausalConversionSeries | None = None,
) -> tuple[float, ConversionObservation | None]:
    currency = str(source_currency).upper().strip()
    if currency == "EUR":
        return 1.0, None
    if currency == "USD":
        if eurusd is None or eurusd.symbol != "EURUSD":
            raise MissingCausalConversion("USD->EUR requires the causal EURUSD M15 series")
        obs = eurusd.latest_completed_at_or_before(cashflow_timestamp)
        return 1.0 / obs.close_price, obs
    if currency == "JPY":
        if eurjpy is None or eurjpy.symbol != "EURJPY":
            raise MissingCausalConversion("JPY->EUR requires the causal EURJPY M15 series")
        obs = eurjpy.latest_completed_at_or_before(cashflow_timestamp)
        return 1.0 / obs.close_price, obs
    raise MissingCausalConversion(f"unsupported quote currency for frozen adapter: {currency}")


def convert_to_eur(
    amount: float,
    source_currency: str,
    cashflow_timestamp: Any,
    *,
    eurusd: CausalConversionSeries | None = None,
    eurjpy: CausalConversionSeries | None = None,
) -> ConversionResult:
    amount = float(amount)
    if not math.isfinite(amount):
        raise ValueError("cashflow amount must be finite")
    currency = str(source_currency).upper().strip()
    rate, obs = quote_to_eur_rate(
        currency,
        cashflow_timestamp,
        eurusd=eurusd,
        eurjpy=eurjpy,
    )
    result = amount * rate
    if not math.isfinite(result):
        raise ValueError("converted EUR amount is non-finite")
    return ConversionResult(
        source_currency=currency,
        target_currency="EUR",
        amount_source=amount,
        amount_eur=result,
        source_symbol=obs.symbol if obs else None,
        quote_to_eur_rate=rate,
        source_bar_open_utc=obs.bar_open_utc if obs else None,
        source_completed_utc=obs.completed_utc if obs else None,
        source_price=obs.close_price if obs else None,
        causal_rule=(
            "EUR_IDENTITY"
            if obs is None
            else "LATEST_COMPLETED_M15_AT_OR_BEFORE_CASHFLOW_NO_FUTURE_INTERPOLATION"
        ),
    )
