"""Deterministic reporting for Stage-B CURRENT broker-configuration realizations.

This module adds no economic decisions. It summarizes the already-frozen CapitalRealization
path so the Stage-B contract reports continuous EUR200 capital, weekly/monthly final equity,
capital occupancy, margin blockers and executed-trade distribution before any protected data.

Historical point-in-time margin remains outside this scenario.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import median
from typing import Any, Iterable

DEVELOPMENT_START_UTC = datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc)
DEVELOPMENT_END_UTC = datetime(2026, 9, 16, 23, 59, 59, 999000, tzinfo=timezone.utc)
RESULT_LABEL = "STAGE_B_CURRENT_CONFIGURATION_SCENARIO"


class CurrentConfigReportingIntegrityError(ValueError):
    pass


def _dt(value: Any) -> datetime:
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise CurrentConfigReportingIntegrityError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _d(value: Any) -> Decimal:
    value = Decimal(str(value))
    if not value.is_finite():
        raise CurrentConfigReportingIntegrityError("non-finite monetary value")
    return value


def _money(value: Decimal) -> float:
    return float(value)


def _next_month_start(value: datetime) -> datetime:
    if value.month == 12:
        return datetime(value.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(value.year, value.month + 1, 1, tzinfo=timezone.utc)


def _closed_events(path: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [dict(x) for x in path if x.get("event") == "TRADE_CLOSED"]
    out.sort(key=lambda x: _dt(x["exit_utc"]))
    return out


def _blocked_events(path: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [dict(x) for x in path if x.get("event") == "MARGIN_BLOCK"]
    out.sort(key=lambda x: _dt(x["entry_utc"]))
    return out


def _equity_series_by_week(
    *,
    starting_equity: Decimal,
    closed: list[dict[str, Any]],
) -> dict[str, float]:
    result: dict[str, float] = {}
    cursor = DEVELOPMENT_START_UTC
    equity = starting_equity
    i = 0
    while cursor <= DEVELOPMENT_END_UTC:
        iso = cursor.isocalendar()
        label = f"{iso.year}-W{iso.week:02d}"
        period_end = min(cursor + timedelta(days=7) - timedelta(microseconds=1), DEVELOPMENT_END_UTC)
        while i < len(closed) and _dt(closed[i]["exit_utc"]) <= period_end:
            equity = _d(closed[i]["equity_eur"])
            i += 1
        result[label] = _money(equity)
        cursor += timedelta(days=7)
    if i != len(closed):
        raise CurrentConfigReportingIntegrityError("closed trade outside DEVELOPMENT weekly domain")
    return result


def _equity_series_by_month(
    *,
    starting_equity: Decimal,
    closed: list[dict[str, Any]],
) -> dict[str, float]:
    result: dict[str, float] = {}
    cursor = datetime(DEVELOPMENT_START_UTC.year, DEVELOPMENT_START_UTC.month, 1, tzinfo=timezone.utc)
    equity = starting_equity
    i = 0
    while cursor <= DEVELOPMENT_END_UTC:
        next_month = _next_month_start(cursor)
        period_start = max(cursor, DEVELOPMENT_START_UTC)
        period_end = min(next_month - timedelta(microseconds=1), DEVELOPMENT_END_UTC)
        if period_start <= period_end:
            while i < len(closed) and _dt(closed[i]["exit_utc"]) <= period_end:
                if _dt(closed[i]["exit_utc"]) >= DEVELOPMENT_START_UTC:
                    equity = _d(closed[i]["equity_eur"])
                i += 1
            result[cursor.strftime("%Y-%m")] = _money(equity)
        cursor = next_month
    if i != len(closed):
        raise CurrentConfigReportingIntegrityError("closed trade outside DEVELOPMENT monthly domain")
    return result


def _distribution_stats(series: dict[str, float]) -> dict[str, float | int]:
    values = list(series.values())
    if not values:
        raise CurrentConfigReportingIntegrityError("empty final-equity distribution")
    return {
        "period_count": len(values),
        "minimum_final_equity_eur": min(values),
        "median_final_equity_eur": float(median(values)),
        "maximum_final_equity_eur": max(values),
        "last_final_equity_eur": values[-1],
    }


def _entry_distributions(closed: list[dict[str, Any]]) -> dict[str, Any]:
    weekly: dict[str, int] = {}
    monthly: dict[str, int] = {}
    yearly: dict[str, int] = {}
    direction: dict[str, int] = {}
    for event in closed:
        entry = _dt(event["entry_utc"])
        iso = entry.isocalendar()
        w = f"{iso.year}-W{iso.week:02d}"
        m = entry.strftime("%Y-%m")
        y = entry.strftime("%Y")
        d = str(event["direction"])
        weekly[w] = weekly.get(w, 0) + 1
        monthly[m] = monthly.get(m, 0) + 1
        yearly[y] = yearly.get(y, 0) + 1
        direction[d] = direction.get(d, 0) + 1
    return {
        "weekly_executed_entries": weekly,
        "monthly_executed_entries": monthly,
        "yearly_executed_entries": yearly,
        "direction_counts": direction,
    }


def summarize_current_config_realization(realization: Any) -> dict[str, Any]:
    path = tuple(dict(x) for x in realization.path)
    if not path or path[0].get("event") != "START":
        raise CurrentConfigReportingIntegrityError("capital path must begin with START")
    if path[0].get("scenario") != RESULT_LABEL:
        raise CurrentConfigReportingIntegrityError("wrong scenario label")
    if any(x.get("historical_margin_claim") is not False for x in path):
        raise CurrentConfigReportingIntegrityError("historical margin claim present in current scenario")

    starting = _d(realization.starting_capital_eur)
    final = _d(realization.final_equity_eur)
    if starting != Decimal("200"):
        raise CurrentConfigReportingIntegrityError("starting capital must be EUR200")

    closed = _closed_events(path)
    blocked = _blocked_events(path)
    if len(closed) != int(realization.executed_trades):
        raise CurrentConfigReportingIntegrityError("executed trade count/path mismatch")
    if len(blocked) != int(realization.margin_blocked_trades):
        raise CurrentConfigReportingIntegrityError("margin block count/path mismatch")
    if len(closed) + len(blocked) != len(path) - 1:
        raise CurrentConfigReportingIntegrityError("unexpected event type in capital path")

    close_equities = [starting] + [_d(x["equity_eur"]) for x in closed]
    if close_equities[-1] != final:
        raise CurrentConfigReportingIntegrityError("final equity/path mismatch")

    peak = close_equities[0]
    max_drawdown = Decimal("0")
    for equity in close_equities:
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_drawdown:
            max_drawdown = dd

    occupied_minutes = Decimal("0")
    margin_time_eur_minutes = Decimal("0")
    required_margins: list[Decimal] = []
    last_exit: datetime | None = None
    for event in closed:
        entry = _dt(event["entry_utc"])
        exit_ = _dt(event["exit_utc"])
        if entry < DEVELOPMENT_START_UTC or exit_ > DEVELOPMENT_END_UTC:
            raise CurrentConfigReportingIntegrityError("executed trade outside DEVELOPMENT")
        if exit_ <= entry:
            raise CurrentConfigReportingIntegrityError("non-positive occupancy interval")
        if last_exit is not None and entry < last_exit:
            raise CurrentConfigReportingIntegrityError("overlapping executed positions")
        last_exit = exit_
        minutes = Decimal(str((exit_ - entry).total_seconds())) / Decimal("60")
        margin = _d(event["required_margin_eur"])
        occupied_minutes += minutes
        margin_time_eur_minutes += margin * minutes
        required_margins.append(margin)

    development_minutes = (
        Decimal(str((DEVELOPMENT_END_UTC - DEVELOPMENT_START_UTC).total_seconds()))
        / Decimal("60")
    )
    occupancy_ratio = (
        occupied_minutes / development_minutes
        if development_minutes > 0
        else Decimal("0")
    )
    avg_margin_time_weighted = (
        margin_time_eur_minutes / development_minutes
        if development_minutes > 0
        else Decimal("0")
    )

    weekly = _equity_series_by_week(starting_equity=starting, closed=closed)
    monthly = _equity_series_by_month(starting_equity=starting, closed=closed)
    distributions = _entry_distributions(closed)

    min_equity = min(close_equities)
    full_sequence_executed = len(blocked) == 0
    capital_positive = min_equity > 0
    if full_sequence_executed and capital_positive:
        feasibility_status = "SURVIVES_CURRENT_CONFIG_EUR200"
        conclusion = (
            "SURVIVES EUR200 CAPITAL REALIZATION UNDER VERIFIED CURRENT "
            "PEPPERSTONE CONFIGURATION APPLIED TO DEVELOPMENT SEQUENCE"
        )
    elif blocked:
        feasibility_status = "CURRENT_CONFIG_MARGIN_BLOCKED"
        conclusion = (
            "DOES NOT EXECUTE THE FULL DEVELOPMENT SEQUENCE AT EUR200 UNDER "
            "VERIFIED CURRENT PEPPERSTONE CONFIGURATION"
        )
    else:
        feasibility_status = "CURRENT_CONFIG_CAPITAL_EXHAUSTED"
        conclusion = (
            "DOES NOT MAINTAIN POSITIVE EUR200 CAPITAL THROUGH THE FULL DEVELOPMENT "
            "SEQUENCE UNDER VERIFIED CURRENT PEPPERSTONE CONFIGURATION"
        )

    return {
        "label": RESULT_LABEL,
        "candidate_id": realization.candidate_id,
        "historical_margin_claim": False,
        "historical_certification_effect": "NONE",
        "feasibility_status": feasibility_status,
        "conclusion": conclusion,
        "continuous_capital": {
            "starting_capital_eur": _money(starting),
            "final_equity_eur": _money(final),
            "minimum_closed_equity_eur": _money(min_equity),
            "maximum_closed_equity_eur": _money(max(close_equities)),
            "maximum_drawdown_eur": _money(max_drawdown),
            "path_event_count_excluding_start": len(path) - 1,
            "full_development_sequence_executed": full_sequence_executed,
        },
        "weekly_final_equity_eur": weekly,
        "weekly_final_equity_distribution": _distribution_stats(weekly),
        "monthly_final_equity_eur": monthly,
        "monthly_final_equity_distribution": _distribution_stats(monthly),
        "capital_occupancy": {
            "development_minutes": float(development_minutes),
            "occupied_minutes": float(occupied_minutes),
            "time_occupancy_ratio": float(occupancy_ratio),
            "time_weighted_margin_eur_over_development": float(avg_margin_time_weighted),
            "maximum_required_margin_eur": (
                _money(max(required_margins)) if required_margins else 0.0
            ),
            "maximum_required_margin_pct_starting_capital": (
                float(max(required_margins) / starting)
                if required_margins
                else 0.0
            ),
        },
        "margin_blockers": {
            "count": len(blocked),
            "events": blocked,
        },
        "executed_trade_distribution": {
            "executed_trades": len(closed),
            "margin_blocked_intents": len(blocked),
            **distributions,
        },
        "capital_path": list(path),
    }
